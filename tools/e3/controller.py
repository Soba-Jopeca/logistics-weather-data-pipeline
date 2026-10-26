"""No service/subprocess startup. Operations require injected, reviewed adapters."""
from pathlib import Path
from uuid import uuid4
from tools.e3.preflight import GateError, digest, require_gate
from tools.e3.ledger import Ledger, publish


class Controller:
    def __init__(self, doc, evidence):
        self.doc, self.evidence = doc, evidence
        self.ledger = Ledger(Path(doc['root']) / 'control/budget', digest(doc))

    def dispatch_manual(self, scenario, trigger):
        require_gate(self.doc, self.evidence, participant='docker')
        if not scenario.startswith('B') or scenario not in self.doc['scenarios']:
            raise GateError('Not an approved manual scenario')
        run_id = f"p09e3__{self.doc['campaign_id']}__{scenario.lower()}__{uuid4()}"
        reservation = self.ledger.reserve('run', scenario, run_id)
        # Reservation is consumed even if trigger raises or its response is lost.
        result = trigger(run_id, scenario)
        self.ledger.event('trigger_returned', {'reservation': reservation, 'result': result})
        return run_id

    def reserve_scheduled_slots(self):
        require_gate(self.doc, self.evidence, participant='docker')
        if len(self.doc['slots']) != 2:
            raise GateError('Scheduled slots not approved')
        return [self.ledger.reserve('run', scenario, 'scheduled:' + canonical_instant(slot))
                for scenario, slot in zip(('C01', 'C02'), self.doc['slots'])]

    def contain(self, reason):
        self.ledger.freeze(reason)
        # No implicit process kill: return only campaign identity for reviewed adapter.
        return {'campaign_id': self.doc['campaign_id'], 'frozen': True,
                'process_containment_required': True}

    def export_evidence(self):
        records = self.ledger.inspect()
        return {'campaign_sha256': digest(self.doc), 'reservations': records,
                'e3_validated': False}


def coordinate_race(barrier, action, timeout=10):
    """Caller supplies isolated processes; never spawn operational producers here."""
    barrier.wait(timeout=timeout)
    return action()


def resolve_reserved_context(doc, evidence, run_id, plans):
    """Bind actual Airflow run identity to a prior run reservation."""
    require_gate(doc, evidence, participant='docker')
    ledger = Ledger(Path(doc['root']) / 'control/budget', digest(doc))
    matches = [r for r in ledger.inspect() if r['kind'] == 'run' and r['invocation'] == run_id]
    if len(matches) != 1:
        raise GateError('Run has no unique consumed reservation')
    scenario = matches[0]['scenario']
    if scenario not in plans or evidence.get('scenario_plan_sha256', {}).get(scenario) != digest(plans[scenario]):
        raise GateError('Run scenario plan mismatch')
    return evidence, scenario, plans[scenario]


def runtime_sources(block):
    """Return launch-file CONTENTS for later reviewed materialization, never write/run."""
    if block not in {'B', 'C'}:
        raise GateError('Unknown runtime block')
    dag_source = '''from pathlib import Path
from airflow.operators.python import get_current_context
from tools.e3.preflight import read_json, require_gate
from tools.e3.controller import resolve_reserved_context, canonical_instant
from tools.e3.dag_loader import load_original_dag, finite_timetable
control = Path('/campaign/control')
campaign = read_json(control / 'campaign.json')
evidence = read_json(control / 'isolation.json')
plans = read_json(control / 'plans.json')
require_gate(campaign, evidence, participant='docker')
def resolve():
    context = get_current_context()
    run = context['dag_run']
    identity = run.run_id
    if getattr(run.run_type, 'value', run.run_type) == 'scheduled':
        identity = 'scheduled:' + canonical_instant(context['data_interval_end'].isoformat())
    return resolve_reserved_context(campaign, evidence, identity, plans)
dag = load_original_dag(campaign, resolver=resolve)
'''
    if block == 'C':
        dag_source += "dag.timetable = finite_timetable(campaign['slots'])\ndag.schedule_interval = '45 13 * * *'\n"
    return {'dags/e3_weather.py': dag_source,
            'plugins/e3_timetable.py': 'from tools.e3.dag_loader import E3TimetablePlugin\n'}


def canonical_instant(value):
    from datetime import datetime, timezone
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None:
        raise GateError('Scheduled identity needs timezone')
    return instant.astimezone(timezone.utc).isoformat()


def metadata_gate_contents(doc, evidence, campaign_bytes, evidence_bytes):
    """Return checksum gate only after inspection; no DB/file operation here.

    The operator must inspect the actual Docker mounts/network first. Checksums
    bind reviewed files, not a security signature or authorization by themselves.
    """
    import json
    import hashlib
    require_gate(doc, evidence, participant='docker')
    if evidence.get('metadata_initialization_authorized') is not True:
        raise GateError('Separate metadata initialization authorization required')
    if json.loads(campaign_bytes) != doc or json.loads(evidence_bytes) != evidence:
        raise GateError('Gate bytes differ from inspected documents')
    return (hashlib.sha256(campaign_bytes).hexdigest() + '  campaign.json\n' +
            hashlib.sha256(evidence_bytes).hexdigest() + '  isolation.json\n')
