"""Explicit runner only. Importing this file never executes the CLI."""
import sys
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from tools.e3.preflight import GateError, digest, require_gate
from tools.e3.ledger import Ledger
from tools.e3.runtime import scenario_context


def run_original_cli(doc, evidence, scenario, plan, *, participant):
    require_gate(doc, evidence, participant=participant)
    if scenario != 'B08':
        raise GateError('Only one B08 concurrent CLI permitted')
    ledger = Ledger(Path(doc['root']) / 'control/budget', digest(doc))
    ledger.reserve('cli', scenario, str(uuid4()))
    import scripts.extract_weather as extractor
    with scenario_context(doc, evidence, scenario, plan, participant=participant):
        with patch.object(sys, 'argv', ['extract_weather.py', '--cycle-date', plan['cycle_date']]):
            return extractor.main()
