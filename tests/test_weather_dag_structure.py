"""Testes estáticos/DagBag: nunca executar callables, operadores ou DAG runs."""

import ast
import builtins
from contextlib import ExitStack
from datetime import timedelta
import json
import io
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
DAG_FILE = ROOT / "dags" / "weather_extract.py"
TASK_IDS = {"prepare_extraction", "extract_batch", "reconcile_extraction"}


def forbidden(*args, **kwargs):
    raise AssertionError("Operação bloqueada durante validação estrutural.")


def guarded_parse():
    # Imports de bibliotecas Airflow são separados do código autoral.
    from airflow.models import DAG, DagBag, Variable
    from airflow.hooks.base import BaseHook
    from airflow.models.taskinstance import TaskInstance
    from airflow.operators.python import PythonOperator
    import requests
    from sqlalchemy.engine import Engine

    originals = {
        name: getattr(Path, name)
        for name in (
            "open", "read_text", "read_bytes", "write_text", "write_bytes",
            "mkdir", "stat", "exists", "is_file", "is_dir", "unlink",
        )
    }

    def is_project_data(path):
        candidate = str(path).replace("\\", "/")
        return any(
            candidate == str(ROOT / folder)
            or candidate.startswith(str(ROOT / folder) + "/")
            or candidate.startswith(folder + "/")
            for folder in ("data", "config")
        ) or candidate == str(ROOT / ".env") or candidate == ".env"

    def guard_path(name):
        def guarded(path, *args, **kwargs):
            # Permitir leitura do código/bibliotecas, bloquear dados e cadastro.
            if is_project_data(path):
                forbidden()
            return originals[name](path, *args, **kwargs)
        return guarded

    dag_filename = str(DAG_FILE)
    task_body_calls = []

    def block_task_bodies(frame, event, arg):
        if (
            event == "call"
            and frame.f_code.co_filename == dag_filename
            and frame.f_code.co_name in TASK_IDS
        ):
            task_body_calls.append(frame.f_code.co_name)
            forbidden()

    previous_profile = sys.getprofile()
    with ExitStack() as stack:
        for target in (
            (Variable, "get"), (BaseHook, "get_connection"),
            (Engine, "connect"), (PythonOperator, "execute"),
            (TaskInstance, "_run_raw_task"), (DAG, "test"),
            (requests.sessions.Session, "request"),
            (socket.socket, "connect"),
        ):
            stack.enter_context(patch.object(*target, side_effect=forbidden))
        for module in (builtins, io):
            original_open = module.open

            def guarded_open(path, *args, _original=original_open, **kwargs):
                if is_project_data(path):
                    forbidden()
                return _original(path, *args, **kwargs)

            stack.enter_context(patch.object(module, "open", guarded_open))
        # Dados não são acessados nem via pathlib durante parsing.
        for name in originals:
            stack.enter_context(patch.object(Path, name, guard_path(name)))
        sys.setprofile(block_task_bodies)
        try:
            bag = DagBag(
                dag_folder=str(DAG_FILE),
                include_examples=False,
                read_dags_from_db=False,
                safe_mode=False,
            )
        finally:
            sys.setprofile(previous_profile)
    if task_body_calls:
        raise AssertionError(f"Corpos de task invocados: {task_body_calls}")
    return bag


class WeatherDagStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import airflow
        except ModuleNotFoundError as error:
            if error.name != "airflow":
                raise
            raise AssertionError("Airflow 2.9.2 obrigatório; não aceitar skip neste gate.") from None
        if airflow.__version__ != "2.9.2":
            raise AssertionError("A validação exige Apache Airflow 2.9.2.")
        before = set(sys.modules)
        cls.bag = guarded_parse()
        cls.new_project_imports = {
            name for name in set(sys.modules) - before if name.startswith("scripts.")
        }
        if cls.bag.import_errors:
            raise AssertionError(cls.bag.import_errors)
        # dagbag.dags evita get_dag() que pode consultar metadados.
        cls.dag = cls.bag.dags["logistics_weather_extract"]
        cls.tree = ast.parse(DAG_FILE.read_text(encoding="utf-8"))

    def test_dag_id_and_exact_task_ids(self):
        self.assertEqual(set(self.bag.dags), {"logistics_weather_extract"})
        self.assertEqual(set(self.dag.task_ids), TASK_IDS)

    def test_dependencies_and_leaf(self):
        expected = {
            "prepare_extraction": {"extract_batch"},
            "extract_batch": {"reconcile_extraction"},
            "reconcile_extraction": set(),
        }
        for task_id, downstream in expected.items():
            self.assertEqual(self.dag.get_task(task_id).downstream_task_ids, downstream)
        self.assertEqual([task.task_id for task in self.dag.leaves], ["reconcile_extraction"])
        self.assertEqual(self.dag.get_task("prepare_extraction").upstream_task_ids, set())

    def test_no_schedule_and_paused_on_creation(self):
        self.assertIsNone(self.dag.schedule_interval)
        self.assertFalse(self.dag.timetable.can_be_scheduled)
        self.assertTrue(self.dag.is_paused_upon_creation)
        # Não ler dag.is_paused: isso acessaria o banco de metadados.

    def test_temporal_and_concurrency_properties(self):
        self.assertEqual(self.dag.timezone.name, "America/Sao_Paulo")
        local_start = self.dag.start_date.in_timezone("America/Sao_Paulo")
        self.assertEqual(local_start.isoformat(), "2026-10-15T00:00:00-03:00")
        self.assertFalse(self.dag.catchup)
        self.assertEqual(self.dag.max_active_runs, 1)
        self.assertEqual(self.dag.max_active_tasks, 1)
        self.assertEqual(self.dag.dagrun_timeout, timedelta(minutes=20))

    def test_taskflow_retries_trigger_rules_and_timeouts(self):
        from airflow.decorators.python import _PythonDecoratedOperator
        timeouts = {"prepare_extraction": 1, "extract_batch": 12, "reconcile_extraction": 2}
        for task in self.dag.tasks:
            self.assertIsInstance(task, _PythonDecoratedOperator)
            self.assertEqual(task.retries, 0)
            self.assertFalse(task.depends_on_past)
            self.assertEqual(task.trigger_rule, "all_success")
            self.assertEqual(task.execution_timeout, timedelta(minutes=timeouts[task.task_id]))
            self.assertFalse(task.multiple_outputs)
            self.assertFalse(task.show_return_value_in_logs)

    def test_serialization_without_execution(self):
        from airflow.serialization.serialized_objects import SerializedDAG
        serialized = SerializedDAG.to_dict(self.dag)
        json.dumps(serialized, allow_nan=False)
        restored = SerializedDAG.from_dict(serialized)
        self.assertEqual(set(restored.task_ids), TASK_IDS)
        self.assertFalse(restored.timetable.can_be_scheduled)

    def test_no_authorial_import_at_module_top_level(self):
        for node in self.tree.body:
            if isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or "").startswith("scripts"))
            elif isinstance(node, ast.Import):
                self.assertFalse(any(alias.name.startswith("scripts") for alias in node.names))
        # Parsing não pode importar os módulos autorais sequer indiretamente.
        self.assertFalse(self.new_project_imports)

    def test_reconciliation_has_no_collection_call(self):
        function = next(
            node for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef) and node.name == "reconcile_extraction"
        )
        for node in ast.walk(function):
            if isinstance(node, ast.ImportFrom):
                self.assertFalse(any(alias.name in {"execute_extraction", "execute_daily_extraction", "collect_batch", "collect_location"} for alias in node.names))
        # Análise AST, sem invocar a função ou simular uma task.
        self.assertTrue(any(isinstance(node, ast.Raise) for node in ast.walk(function)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
