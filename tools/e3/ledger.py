"""Conservative append-only budget. No lease, deletion, reclaim or refund."""
import os
from pathlib import Path
from uuid import uuid4
from tools.e3.preflight import GateError, LIMITS, digest, read_json
import json


def publish(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    temp = path.parent / ('.pending-' + str(uuid4()))
    # Pending artifacts remain as interruption evidence. Never remove old evidence.
    with temp.open('xb') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    try:
        os.link(temp, path)
    except FileExistsError:
        return False
    return True


class Ledger:
    def __init__(self, root, campaign_sha256):
        self.root = Path(root)
        self.campaign = campaign_sha256

    def freeze(self, reason):
        publish(self.root / 'frozen.json', {'campaign': self.campaign, 'reason': reason})

    def _lock(self):
        if (self.root / 'frozen.json').exists():
            raise GateError('Campaign frozen')
        # An interrupted critical section is ambiguous: never steal this lock.
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            (self.root / 'reservation.lock').mkdir()
        except FileExistsError as exc:
            raise GateError('Budget busy or interrupted; no automatic recovery') from exc

    def inspect(self):
        records = []
        for path in sorted(self.root.glob('reservation-*.json')):
            item = read_json(path)
            if set(item) != {'campaign', 'kind', 'scenario', 'invocation', 'ordinal'} or item['campaign'] != self.campaign:
                raise GateError('Corrupt ledger')
            if item['scenario'] not in LIMITS or item['kind'] not in {'run', 'transport', 'cli'}:
                raise GateError('Unknown ledger record')
            if type(item['ordinal']) is not int or item['ordinal'] != len(records) + 1:
                raise GateError('Ledger gap or reordering')
            if path.name != f"reservation-{item['ordinal']:04d}.json":
                raise GateError('Ledger filename mismatch')
            records.append(item)
        if len({r['invocation'] for r in records}) != len(records):
            raise GateError('Duplicate operation identity')
        self._check_counts(records)
        return records

    @staticmethod
    def _check_counts(records):
        for kind, total in [('run', 15), ('transport', 37), ('cli', 1)]:
            items = [r for r in records if r['kind'] == kind]
            if len(items) > total:
                raise GateError('Global budget exceeded')
            for scenario, limits in LIMITS.items():
                cap = (1 if scenario == 'B08' else 0) if kind == 'cli' else limits[kind == 'transport']
                if sum(r['scenario'] == scenario for r in items) > cap:
                    raise GateError('Scenario budget exceeded')
            if kind == 'run' and (sum(r['scenario'].startswith('B') for r in items) > 13 or
                                  sum(r['scenario'].startswith('C') for r in items) > 2):
                raise GateError('Block budget exceeded')

    def reserve(self, kind, scenario, invocation):
        if kind not in {'run', 'transport', 'cli'} or scenario not in LIMITS or not isinstance(invocation, str) or not invocation:
            raise GateError('Invalid reservation')
        self._lock()
        success = False
        try:
            records = self.inspect()
            if any(r['invocation'] == invocation for r in records):
                raise GateError('Invocation already consumed; reconcile, never repeat')
            item = dict(campaign=self.campaign, kind=kind, scenario=scenario,
                        invocation=invocation, ordinal=len(records) + 1)
            self._check_counts(records + [item])
            if not publish(self.root / f"reservation-{item['ordinal']:04d}.json", item):
                raise GateError('Reservation conflict')
            success = True
            return item
        finally:
            # On any ambiguous failure keep the lock. Successful reservation remains consumed.
            if success:
                (self.root / 'reservation.lock').rmdir()

    def event(self, category, details):
        if not publish(self.root / 'events' / (str(uuid4()) + '.json'),
                       dict(campaign=self.campaign, category=category, details=details)):
            raise GateError('Event publication conflict')
