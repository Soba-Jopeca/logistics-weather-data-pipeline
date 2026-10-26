"""Load original DAG without executing tasks; finite timetable is test-only."""
import hashlib
import importlib.util
from functools import wraps
from pathlib import Path
from tools.e3.preflight import GateError, inspect_baseline

TASKS = {'prepare_extraction', 'extract_batch', 'reconcile_extraction'}


def verify_task_graph(dag):
    from datetime import timedelta
    if dag.dag_id != 'logistics_weather_extract' or set(dag.task_ids) != TASKS:
        raise GateError('Unexpected DAG/tasks')
    expected = {'prepare_extraction': {'extract_batch'}, 'extract_batch': {'reconcile_extraction'}, 'reconcile_extraction': set()}
    for task in dag.tasks:
        if task.retries != 0 or task.downstream_task_ids != expected[task.task_id]:
            raise GateError('Task graph/retry mismatch')
        minutes = {'prepare_extraction': 1, 'extract_batch': 12, 'reconcile_extraction': 2}[task.task_id]
        if task.execution_timeout != timedelta(minutes=minutes):
            raise GateError('Task timeout mismatch')
    if dag.max_active_runs != 1 or dag.max_active_tasks != 1 or dag.dagrun_timeout != timedelta(minutes=20):
        raise GateError('DAG concurrency/timeout mismatch')
    return True


def load_original_dag(doc, resolver=None):
    inspect_baseline(doc)
    path = Path(doc['code_root']) / 'dags/weather_extract.py'
    spec = importlib.util.spec_from_file_location('p09_e3_original_dag', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dag = module.dag
    verify_task_graph(dag)
    if resolver is not None:
        for task in dag.tasks:
            original = task.python_callable
            @wraps(original)
            def instrumented(*args, _original=original, **kwargs):
                from tools.e3.runtime import scenario_context
                # Resolver must match current run to a consumed, approved reservation.
                evidence, scenario, plan = resolver()
                with scenario_context(doc, evidence, scenario, plan) as (root, _):
                    previous = module.__file__
                    try:
                        module.__file__ = str(root / 'dags/weather_extract.py')
                        return _original(*args, **kwargs)
                    finally:
                        module.__file__ = previous
            task.python_callable = instrumented
    return dag


# Airflow imports are deliberately required, never replaced by test doubles.
from airflow.timetables.interval import CronDataIntervalTimetable
from airflow.plugins_manager import AirflowPlugin
import pendulum


class ApprovedSlotsTimetable(CronDataIntervalTimetable):
    """Real cron interval calculation, bounded to two consecutive approved slots."""
    def __init__(self, slots):
        if len(slots) != 2 or len(set(slots)) != 2:
            raise GateError('Exactly two distinct approved slots required')
        if any(not isinstance(s, str) or ('+' not in s[10:] and '-' not in s[10:] and not s.endswith('Z')) for s in slots):
            raise GateError('Explicit timezone required')
        self.ends = sorted(pendulum.parse(s) for s in slots)
        local = [e.in_timezone('America/Sao_Paulo') for e in self.ends]
        if any((e.hour, e.minute, e.second, e.microsecond) != (13, 45, 0, 0) for e in local):
            raise GateError('Non-nominal scheduled slot')
        if local[0].add(days=1) != local[1]:
            raise GateError('Campaign slots must be consecutive days')
        super().__init__('45 13 * * *', timezone='America/Sao_Paulo')

    def next_dagrun_info(self, *, last_automated_data_interval, restriction):
        info = super().next_dagrun_info(last_automated_data_interval=last_automated_data_interval,
                                      restriction=restriction)
        if info is None or info.data_interval.end not in self.ends:
            return None
        return info

    def serialize(self):
        return {'slots': [e.isoformat() for e in self.ends]}

    @classmethod
    def deserialize(cls, data):
        if set(data) != {'slots'}:
            raise GateError('Unknown timetable serialization')
        return cls(data['slots'])


class E3TimetablePlugin(AirflowPlugin):
    name = 'p09_e3_approved_slots'
    timetables = [ApprovedSlotsTimetable]


def finite_timetable(slots):
    return ApprovedSlotsTimetable(slots)
