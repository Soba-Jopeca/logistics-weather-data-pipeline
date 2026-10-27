"""P03 offline only: no task callable, DAG run, service or operational CLI."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import date
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

import pytest

from tools.e3.preflight import (BASELINE, BASELINE_HASHES, GateError, digest, read_json,
                                validate_campaign, inspect_baseline, require_gate,
                                verify_mount_identity, contained, source_digest)
from tools.e3.ledger import Ledger, publish
from tools.e3.runtime import ScriptClock, dependency_context, forbidden
from tools.e3.fixtures import fixture_bytes
from tools.e3.controller import Controller, resolve_reserved_context

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolation(monkeypatch):
    for obj, name in [(socket.socket, 'connect'), (socket.socket, 'connect_ex'),
                      (socket.socket, 'sendto'), (socket, 'getaddrinfo')]:
        monkeypatch.setattr(obj, name, forbidden)


@pytest.fixture
def campaign(tmp_path):
    doc = read_json(ROOT / 'tools/e3/campaign.example.json')
    doc.update(root=str(tmp_path / 'campaign'), code_root=str(ROOT))
    return doc


@pytest.fixture
def approved(campaign):
    campaign.update(enabled=True, authorization='offline-test-only')
    evidence = dict(campaign_sha256=digest(campaign), external_network_blocked=True,
                    operational_mounts_absent=True, exclusive_metadata=True,
                    write_confinement=True, shared_root_verified=True)
    return campaign, evidence


def test_baseline_inventory(campaign):
    assert inspect_baseline(campaign) == digest(BASELINE_HASHES)
    assert len(BASELINE_HASHES) >= 8


def test_source_digest_normalizes_windows_line_endings(tmp_path):
    lf = tmp_path / 'lf.txt'
    crlf = tmp_path / 'crlf.txt'
    lf.write_bytes(b'first\nsecond\n')
    crlf.write_bytes(b'first\r\nsecond\r\n')
    assert source_digest(lf) == source_digest(crlf)


@pytest.mark.parametrize('field,value', [('baseline','bad'), ('enabled',1), ('campaign_id','oops'),
    ('root','relative'), ('scenarios',['B01','B01']), ('slots',[1,2,3]), ('authorization',None)])
def test_invalid_campaign(campaign, field, value):
    campaign[field] = value
    with pytest.raises(GateError):
        validate_campaign(campaign)


def test_extra_field_and_overlapping_roots(campaign):
    campaign['extra'] = 1
    with pytest.raises(GateError): validate_campaign(campaign)
    del campaign['extra']
    campaign['root'] = str(ROOT / 'data/e3')
    with pytest.raises(GateError): validate_campaign(campaign)


def test_modified_hash_fails(campaign):
    campaign['hashes']['scripts/weather_daily.py'] = '0'*64
    with pytest.raises(GateError): inspect_baseline(campaign)


def test_disabled_campaign(campaign):
    with pytest.raises(GateError): require_gate(campaign, {}, participant='docker')


@pytest.mark.parametrize('key', ['external_network_blocked','operational_mounts_absent',
                                 'exclusive_metadata','write_confinement','shared_root_verified'])
def test_missing_gate(approved, key):
    doc, evidence = approved
    evidence[key] = False
    with pytest.raises(GateError): require_gate(doc, evidence, participant='docker')


def test_windows_not_claimed(approved):
    doc, evidence = approved
    with pytest.raises(GateError): require_gate(doc, evidence, participant='windows')
    assert require_gate(doc, evidence, participant='docker')


def test_duplicate_json_and_escape(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{"a":1,"a":2}')
    with pytest.raises(GateError): read_json(path)
    with pytest.raises(GateError): contained(tmp_path, tmp_path/'../escape')


def test_shared_visibility_not_atomicity(tmp_path):
    p = tmp_path/'witness'; p.write_bytes(b'visibility')
    result = verify_mount_identity(tmp_path, tmp_path, 'witness', hashlib.sha256(p.read_bytes()).hexdigest())
    assert result == {'visibility': True, 'atomicity_proven': False}
    with pytest.raises(GateError): verify_mount_identity(tmp_path,tmp_path,'witness','0'*64)


def test_ledger_exclusive_and_consumed(tmp_path):
    ledger = Ledger(tmp_path/'ledger', 'a'*64)
    ledger.reserve('run','B02','first')
    with pytest.raises(GateError): ledger.reserve('run','B02','second')
    assert len(ledger.inspect()) == 1
    assert (ledger.root/'reservation.lock').is_dir()


def test_global_budget(tmp_path):
    from tools.e3.preflight import LIMITS
    ledger = Ledger(tmp_path/'ledger', 'b'*64)
    for scenario, (runs, transports) in LIMITS.items():
        for i in range(runs): ledger.reserve('run',scenario,f'{scenario}-run-{i}')
        for i in range(transports): ledger.reserve('transport',scenario,f'{scenario}-http-{i}')
    assert sum(r['kind']=='run' for r in ledger.inspect()) == 15
    assert sum(r['kind']=='transport' for r in ledger.inspect()) == 37
    with pytest.raises(GateError): ledger.reserve('transport','B01','extra')


def test_cli_budget_and_freeze(tmp_path):
    ledger=Ledger(tmp_path/'ledger','a'*64)
    ledger.reserve('cli','B08','cli')
    ledger.freeze('operator containment')
    with pytest.raises(GateError): ledger.reserve('run','B01','run')


def test_corrupt_ledger(tmp_path):
    ledger=Ledger(tmp_path/'ledger','a'*64)
    ledger.reserve('run','B01','one')
    (ledger.root/'reservation-0001.json').write_text('{}')
    with pytest.raises(GateError): ledger.reserve('run','B01','two')


def _race_worker(root, barrier, queue):
    # Spawned workers never import/run meteorological producers or open network.
    socket.socket.connect = forbidden
    socket.socket.connect_ex = forbidden
    ledger = Ledger(Path(root), 'a'*64)
    barrier.wait(timeout=10)
    try:
        ledger.reserve('run','B02',str(os.getpid()))
        queue.put('reserved')
    except GateError:
        queue.put('blocked')


def test_ledger_process_race(tmp_path):
    ctx=multiprocessing.get_context('spawn')
    barrier,queue=ctx.Barrier(2),ctx.Queue()
    workers=[ctx.Process(target=_race_worker,args=(str(tmp_path/'ledger'),barrier,queue)) for _ in range(2)]
    try:
        for worker in workers: worker.start()
        results=[queue.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(timeout=15)
            assert worker.exitcode == 0
        assert sorted(results)==['blocked','reserved']
        assert len(Ledger(tmp_path/'ledger','a'*64).inspect())==1
    finally:
        for worker in workers:
            if worker.is_alive(): worker.terminate(); worker.join()
        queue.close()


def test_interrupted_critical_section(tmp_path):
    ledger=Ledger(tmp_path/'ledger','a'*64)
    ledger._lock()
    with pytest.raises(GateError): Ledger(ledger.root,'a'*64).reserve('run','B01','restart')


def test_publication_failure_preserves_lock(tmp_path):
    ledger=Ledger(tmp_path/'ledger','a'*64)
    with patch('tools.e3.ledger.os.link', side_effect=PermissionError('synthetic')):
        with pytest.raises(PermissionError): ledger.reserve('run','B01','failed')
    assert (ledger.root/'reservation.lock').exists()
    assert list(ledger.root.glob('.pending-*'))


def test_finite_clock():
    clock=ScriptClock({'prepare':['2026-10-20T13:45:00-03:00']})
    assert clock.read('prepare').hour==13
    with pytest.raises(GateError): clock.read('prepare')
    with pytest.raises(GateError): ScriptClock({'prepare':['2026-10-20T13:45:00']})


def test_fixture_deterministic_and_faults(locations):
    first=fixture_bytes(locations[0],'2026-10-20')
    assert first==fixture_bytes(locations[0],'2026-10-20')
    assert len(json.loads(first)['hourly']['time'])==32
    assert json.loads(fixture_bytes(locations[0],'2026-10-20','null'))['hourly']['temperature_2m'][0] is None
    with pytest.raises(GateError): fixture_bytes(locations[0],'2026-10-20','undefined')


def test_transport_original_guard_and_no_fallback(tmp_path, locations):
    import scripts.extract_weather as ex
    import scripts.weather_daily as daily
    from scripts.weather_window import build_cycle_window
    root=tmp_path/'scenarios/B01'; root.mkdir(parents=True)
    ledger=Ledger(tmp_path/'control/budget','a'*64)
    quality,eligible=daily._quality,daily.evaluate_for_consumption
    params=ex.build_request_params(locations[0],build_cycle_window(date(2026,10,20),locations[0]['timezone']))
    calls=[]
    with dependency_context(root=root,scenario='B01',ledger=ledger,locations=locations,
                            cycle_date='2026-10-20',clocks={}):
        response=ex.fetch_forecast_response('https://api.open-meteo.com/v1/forecast',params,
                                           before_first_transport=lambda:calls.append('guard'))
        assert response.status_code==200 and calls==['guard']
        assert daily._quality is quality and daily.evaluate_for_consumption is eligible
        with pytest.raises(GateError): ex.fetch_forecast_response('https://unexpected.invalid',params)
        with pytest.raises(GateError): socket.create_connection(('example.invalid',443))
        with pytest.raises(GateError): subprocess.Popen(['echo','blocked'])
    assert len(ledger.inspect())==1


def test_failed_fixture_never_live(tmp_path,locations):
    import scripts.extract_weather as ex
    from scripts.weather_window import build_cycle_window
    root=tmp_path/'scenarios/B01'; root.mkdir(parents=True)
    ledger=Ledger(tmp_path/'control/budget','a'*64)
    params=ex.build_request_params(locations[0],build_cycle_window(date(2026,10,20),locations[0]['timezone']))
    with dependency_context(root=root,scenario='B01',ledger=ledger,locations=locations,
        cycle_date='2026-10-20',clocks={},faults={'locations':{locations[0]['location_id']:'undefined'}}):
        with pytest.raises(GateError): ex.fetch_forecast_response('https://api.open-meteo.com/v1/forecast',params)
    assert len(ledger.inspect())==1


def test_write_guard(tmp_path,locations):
    root=tmp_path/'campaign/scenarios/B01'; root.mkdir(parents=True)
    with dependency_context(root=root,scenario='B01',ledger=Ledger(tmp_path/'campaign/control','a'*64),
                            locations=locations,cycle_date='2026-10-20',clocks={}):
        with pytest.raises(GateError): (tmp_path/'outside').write_text('forbidden')
    assert not (tmp_path/'outside').exists()


def test_trigger_failure_consumes_run(approved):
    doc,evidence=approved
    controller=Controller(doc,evidence)
    def fail(*args): raise RuntimeError('synthetic response lost')
    with pytest.raises(RuntimeError): controller.dispatch_manual('B01',fail)
    assert len(controller.ledger.inspect())==1
    controller.contain('stop')
    assert controller.export_evidence()['e3_validated'] is False


def test_no_unreserved_context(approved):
    doc,evidence=approved
    with pytest.raises(GateError): resolve_reserved_context(doc,evidence,'unknown',{})


def test_compose_static_no_operational_mounts():
    text=(ROOT/'tools/e3/compose.e3.yaml').read_text()
    assert 'internal: true' in text and 'read_only: true' in text
    assert 'create_host_path: false' in text
    assert 'docker.sock' not in text and 'external: true' not in text
    assert 'control/secrets' not in text
    assert 'file: ${E3_ROOT:?}/secrets/' in text
    assert 'airflow db migrate' not in text
    assert 'entrypoint: [python, -m, tools.e3.preflight]' in text


def test_original_dag_parse_only(campaign):
    # Import failure is a test ERROR, never an optional skip.
    from airflow.models import DAG
    from airflow.models.taskinstance import TaskInstance
    from airflow.operators.python import PythonOperator
    from sqlalchemy.engine import Engine
    from tools.e3.dag_loader import load_original_dag, verify_task_graph
    with ExitStack() as stack:
        for owner,name in [(DAG,'test'),(TaskInstance,'_run_raw_task'),(PythonOperator,'execute'),(Engine,'connect')]:
            stack.enter_context(patch.object(owner,name,forbidden))
        dag=load_original_dag(campaign,resolver=forbidden)
        assert verify_task_graph(dag)
        assert dag.schedule_interval is None
        assert dag.is_paused_upon_creation is True


def test_finite_timetable_only_two_slots():
    import pendulum
    from airflow.timetables.base import TimeRestriction
    from tools.e3.dag_loader import finite_timetable
    ends=['2026-10-20T13:45:00-03:00','2026-10-21T13:45:00-03:00']
    timetable=finite_timetable(ends)
    restriction=TimeRestriction(earliest=pendulum.parse('2026-10-19T13:45:00-03:00'),latest=None,catchup=True)
    first=timetable.next_dagrun_info(last_automated_data_interval=None,restriction=restriction)
    second=timetable.next_dagrun_info(last_automated_data_interval=first.data_interval,restriction=restriction)
    assert first.data_interval.end==pendulum.parse(ends[0])
    assert second.data_interval.end==pendulum.parse(ends[1])
    assert timetable.next_dagrun_info(last_automated_data_interval=second.data_interval,restriction=restriction) is None
    assert timetable.deserialize(timetable.serialize()).serialize()==timetable.serialize()


@pytest.mark.parametrize('fault,expected', [('none',True),('null',False)])
def test_real_policy_with_instrumented_dependencies(tmp_path,locations,config,fault,expected):
    import scripts.weather_daily as daily
    root=tmp_path/'campaign/scenarios/B01'; root.mkdir(parents=True)
    ledger=Ledger(tmp_path/'campaign/control/budget','a'*64)
    early='2026-10-20T13:45:00-03:00'; ready='2026-10-20T13:50:00-03:00'
    clocks={'prepare':[early], 'execute':[early,early], 'batch':[early],
            'reconcile':[ready]*5, **{'city:'+loc['location_id']:[early] for loc in locations}}
    faults={'locations':{locations[0]['location_id']:fault}}
    with dependency_context(root=root,scenario='B01',ledger=ledger,locations=locations,
                            cycle_date='2026-10-20',clocks=clocks,faults=faults):
        prepared=daily.prepare_daily_extraction(config=config,locations=locations,
                    project_root=root,cycle_date=date(2026,10,20))
        completed=daily.execute_daily_extraction(prepared=prepared,project_root=root)
        result=daily.reconcile_daily_extraction(prepared=completed,project_root=root)
        assert result['eligible'] is expected
    assert len(ledger.inspect())==5
    # New instrumented process context, original immutable references and timestamps.
    with dependency_context(root=root,scenario='B01',ledger=ledger,locations=locations,
        cycle_date='2026-10-20',clocks={'batch':[ready], 'reconcile':[ready]}):
        replay=daily.prepare_daily_extraction(config=config,locations=locations,
                   project_root=root,cycle_date=date(2026,10,20))
        completed2=daily.execute_daily_extraction(prepared=replay,project_root=root)
        result2=daily.reconcile_daily_extraction(prepared=completed2,project_root=root)
        assert completed2['mode']=='replay'
        assert completed2['batch_id']==completed['batch_id']
        assert result2['eligible'] is expected
    assert len(ledger.inspect())==5


def test_interruption_after_actual_claim(tmp_path,locations,config):
    import scripts.weather_daily as daily
    root=tmp_path/'campaign/scenarios/B06'; root.mkdir(parents=True)
    ledger=Ledger(tmp_path/'campaign/control/budget','a'*64)
    with dependency_context(root=root,scenario='B06',ledger=ledger,locations=locations,
        cycle_date='2026-10-20',clocks={'prepare':['2026-10-20T13:45:00-03:00']},
        faults={'after_publish':'claim.json'}):
        with pytest.raises(GateError):
            daily.prepare_daily_extraction(config=config,locations=locations,
                project_root=root,cycle_date=date(2026,10,20))
    assert len(list(root.glob('data/orchestration/slots/*/claim.json')))==1
    assert not list(root.glob('data/orchestration/batches/*/manifest.json'))
    assert ledger.inspect()==[]


def test_generated_runtime_only_parsed():
    import ast
    from tools.e3.controller import runtime_sources
    for block in ('B','C'):
        sources=runtime_sources(block)
        for path,source in sources.items(): ast.parse(source,filename=path)
        assert 'require_gate' in sources['dags/e3_weather.py']
    with pytest.raises(GateError): runtime_sources('A')


def test_metadata_gate_no_implicit_initialization(approved):
    from tools.e3.controller import metadata_gate_contents
    doc,evidence=approved
    with pytest.raises(GateError): metadata_gate_contents(doc,evidence,b'{}',b'{}')
    evidence['metadata_initialization_authorized']=True
    content=metadata_gate_contents(doc,evidence,json.dumps(doc).encode(),json.dumps(evidence).encode())
    assert content.count('\n')==2 and 'campaign.json' in content and 'isolation.json' in content
    with pytest.raises(GateError): metadata_gate_contents(doc,evidence,b'{}',b'{}')


def test_scheduled_identity_canonical():
    from tools.e3.controller import canonical_instant
    assert canonical_instant('2026-10-20T13:45:00-03:00')==canonical_instant('2026-10-20T16:45:00+00:00')
    with pytest.raises(GateError): canonical_instant('2026-10-20T13:45:00')
