"""Process-local dependency instrumentation; never an operating-system sandbox."""
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone, date
from functools import wraps
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import builtins
import io
import socket
import threading
import subprocess

from tools.e3.preflight import GateError, contained, digest, require_gate
from tools.e3.fixtures import fixture_bytes
from tools.e3.ledger import Ledger

_ACTIVE = threading.Lock()


def instant(text):
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        raise GateError('Clock must be timezone aware')
    return value


class ScriptClock:
    def __init__(self, phases):
        self.phases = {k: [instant(v) for v in values] for k, values in phases.items()}
        self.used = {k: 0 for k in phases}

    def read(self, phase):
        position = self.used.get(phase, 0)
        if phase not in self.phases or position >= len(self.phases[phase]):
            raise GateError('Unexpected/exhausted clock phase: ' + phase)
        self.used[phase] += 1
        return self.phases[phase][position]


def forbidden(*args, **kwargs):
    raise GateError('Live transport/process operation forbidden')


@contextmanager
def dependency_context(*, root, scenario, ledger, locations, cycle_date, clocks,
                       faults=None, allowed_db=None):
    """Offline-testable core. Operational entry points MUST require_gate first.

    Builtin write guards are defense in depth. OS mounts/ACLs are mandatory;
    native syscalls and privileged users cannot be confined by this context.
    """
    import requests
    import scripts.extract_weather as ex
    import scripts.weather_daily as daily
    import scripts.weather_slots as slots
    from scripts.weather_window import build_cycle_window
    root = Path(root).resolve()
    if not root.is_dir():
        raise GateError('Scenario root must already exist')
    faults = faults or {}
    if not set(faults) <= {'locations', 'after_publish'}:
        raise GateError('Unknown fault plan')
    original_quality = daily._quality
    original_evaluate = daily.evaluate_for_consumption
    clock = ScriptClock(clocks)
    current = {'collection': None}
    params_map = {loc['location_id']: ex.build_request_params(
        loc, build_cycle_window(date.fromisoformat(cycle_date), loc['timezone'])) for loc in locations}
    location_map = {loc['location_id']: loc for loc in locations}

    def transport(endpoint, *, params, timeout):
        if endpoint != 'https://api.open-meteo.com/v1/forecast' or tuple(timeout) != (10, 30):
            raise GateError('Unexpected transport configuration')
        matches = [key for key, value in params_map.items() if value == params]
        if len(matches) != 1:
            raise GateError('Unexpected request parameters')
        key = matches[0]
        ledger.reserve('transport', scenario, str(uuid4()))
        fault = faults.get('locations', {}).get(key, 'none')
        if fault == 'timeout':
            raise requests.exceptions.Timeout('Synthetic timeout')
        response = requests.Response()
        response.status_code = 200
        response._content = fixture_bytes(location_map[key], cycle_date, fault)
        response.encoding = 'utf-8'
        return response

    class CollectionDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None or current['collection'] is None:
                raise GateError('Collection clock context missing')
            return current['collection'].astimezone(tz)

    original_location = ex.collect_location
    @wraps(original_location)
    def collect_location(config, location, *args, **kwargs):
        current['collection'] = clock.read('city:' + location['location_id'])
        return original_location(config, location, *args, **kwargs)

    def wrap_policy(original, phase):
        @wraps(original)
        def call(*args, **kwargs):
            kwargs['project_root'] = root
            kwargs['clock'] = lambda: clock.read(phase)
            if phase == 'execute':
                # Batch timestamps before the first city use their own explicit instant.
                current['collection'] = clock.read('batch')
            return original(*args, **kwargs)
        return call

    def checked_open(original):
        def open_file(path, mode='r', *args, **kwargs):
            if any(c in mode for c in 'wax+'):
                if isinstance(path, int):
                    raise GateError('Untracked writable file descriptor')
                resolved = Path(path).resolve()
                if not any(base == resolved or base in resolved.parents for base in (root, ledger.root.resolve())):
                    raise GateError('Write outside scenario/control roots')
            return original(path, mode, *args, **kwargs)
        return open_file

    original_connect = socket.socket.connect
    def connect(sock, address):
        if allowed_db is None or address != allowed_db:
            forbidden()
        return original_connect(sock, address)

    def after(original):
        @wraps(original)
        def publish(*args, **kwargs):
            result = original(*args, **kwargs)
            marker = faults.get('after_publish')
            paths = [str(v).replace('\\', '/') for v in args if isinstance(v, (str, Path))]
            if marker and any(p.endswith(marker) for p in paths):
                ledger.event('injected_interruption', {'marker': marker})
                raise GateError('Synthetic interruption after original persistence')
            return result
        return publish

    if not _ACTIVE.acquire(blocking=False):
        raise GateError('Nested or concurrent instrumented context forbidden')
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(requests, 'get', transport))
            stack.enter_context(patch.object(requests.sessions.Session, 'request', forbidden))
            stack.enter_context(patch.object(socket.socket, 'connect', connect))
            stack.enter_context(patch.object(socket.socket, 'connect_ex', forbidden))
            stack.enter_context(patch.object(socket.socket, 'sendto', forbidden))
            stack.enter_context(patch.object(socket, 'getaddrinfo', forbidden))
            stack.enter_context(patch.object(subprocess, 'Popen', forbidden))
            stack.enter_context(patch.object(socket, 'create_connection', forbidden))
            stack.enter_context(patch.object(ex, 'PROJECT_ROOT', root))
            stack.enter_context(patch.object(ex, 'datetime', CollectionDateTime))
            stack.enter_context(patch.object(ex, 'collect_location', collect_location))
            for name, phase in [('prepare_daily_extraction', 'prepare'), ('execute_daily_extraction', 'execute'),
                                ('reconcile_daily_extraction', 'reconcile')]:
                stack.enter_context(patch.object(daily, name, wrap_policy(getattr(daily, name), phase)))
            # Python 3.10 pathlib caches io.open in its accessor. Guard the
            # public Path entry point too, preserving the original implementation.
            stack.enter_context(patch.object(Path, 'open', checked_open(Path.open)))
            for module in (builtins, io):
                stack.enter_context(patch.object(module, 'open', checked_open(module.open)))
            for module, name in [(daily, 'persist_immutable_document'), (slots, '_publish_exclusive')]:
                stack.enter_context(patch.object(module, name, after(getattr(module, name))))
            yield clock
            if daily._quality is not original_quality or daily.evaluate_for_consumption is not original_evaluate:
                raise GateError('Decision function identity changed')
    finally:
        _ACTIVE.release()


@contextmanager
def scenario_context(doc, evidence, scenario, plan, *, participant='docker'):
    require_gate(doc, evidence, participant=participant)
    if evidence.get('scenario_plan_sha256', {}).get(scenario) != digest(plan):
        raise GateError('Scenario plan not bound to reviewed evidence')
    if scenario not in doc['scenarios']:
        raise GateError('Scenario not authorized')
    root = contained(doc['root'], Path(doc['root']) / 'scenarios' / scenario)
    ledger = Ledger(Path(doc['root']) / 'control' / 'budget', digest(doc))
    import scripts.extract_weather as ex
    source = Path(doc['code_root']) / 'scripts' / 'extract_weather.py'
    if Path(ex.__file__).resolve() != source.resolve():
        raise GateError('Imported operational module from wrong checkout')
    from tools.e3.preflight import read_json
    locations = read_json(Path(doc['code_root']) / 'config' / 'locations.json')
    # load_locations normally reads PROJECT_ROOT/config. Keep fixture config original.
    if (root / 'config/locations.json').read_bytes() != (Path(doc['code_root']) / 'config/locations.json').read_bytes():
        raise GateError('Scenario location snapshot mismatch')
    with dependency_context(root=root, scenario=scenario, ledger=ledger, locations=locations,
                            cycle_date=plan['cycle_date'], clocks=plan['clocks'], faults=plan.get('faults')) as clock:
        yield root, clock
