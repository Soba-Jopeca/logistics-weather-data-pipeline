"""Orquestração de extração; execução depende de liberação central própria."""

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.decorators import task


def _small_metadata(document):
    """Limitar cada retorno XCom a JSON pequeno, sem payload meteorológico."""
    import json

    from airflow.exceptions import AirflowFailException

    if len(json.dumps(document, allow_nan=False).encode("utf-8")) > 8192:
        raise AirflowFailException("Metadados excedem o limite de 8 KiB.")
    return document


with DAG(
    dag_id="logistics_weather_extract",
    description="Extração meteorológica por ciclo explícito, com Raw rastreável.",
    start_date=pendulum.datetime(2026, 10, 15, tz="America/Sao_Paulo"),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    max_active_runs=1,
    max_active_tasks=1,
    dagrun_timeout=timedelta(minutes=20),
    default_args={"depends_on_past": False, "retries": 0},
    tags=["weather", "extraction"],
) as dag:

    @task(
        task_id="prepare_extraction",
        execution_timeout=timedelta(minutes=1),
        multiple_outputs=False,
        show_return_value_in_logs=False,
    )
    def prepare_extraction():
        from datetime import date
        from pathlib import Path

        from airflow.exceptions import AirflowFailException
        from airflow.operators.python import get_current_context

        from scripts.extract_weather import load_api_config, load_locations
        from scripts.weather_interface import prepare_extraction as prepare

        context = get_current_context()
        dag_run = context["dag_run"]
        conf = dag_run.conf

        if not isinstance(conf, dict) or set(conf) != {"cycle_date"}:
            raise AirflowFailException(
                "Forneça somente cycle_date explícito no formato AAAA-MM-DD."
            )

        try:
            value = conf["cycle_date"]
            if not isinstance(value, str):
                raise ValueError
            cycle_date = date.fromisoformat(value)
            if cycle_date.isoformat() != value:
                raise ValueError
        except ValueError:
            raise AirflowFailException("cycle_date inválido: use AAAA-MM-DD.") from None

        # Contexto imutável: try_number e relógio da task não selecionam o ciclo.
        orchestration_context = {
            "dag_id": context["dag"].dag_id,
            "airflow_run_id": dag_run.run_id,
            "scheduled_slot": None,
        }
        for key in ("logical_date", "data_interval_start", "data_interval_end"):
            instant = context.get(key)
            orchestration_context[key] = instant.isoformat() if instant else None

        try:
            metadata = prepare(
                cycle_date=cycle_date,
                config=load_api_config(),
                locations=load_locations(),
                project_root=Path(__file__).resolve().parent.parent,
                orchestration_context=orchestration_context,
            )
        except (ValueError, OSError):
            raise AirflowFailException(
                "Preparação bloqueada; verificar configuração e auditoria local."
            ) from None
        return _small_metadata(metadata)

    @task(
        task_id="extract_batch",
        execution_timeout=timedelta(minutes=12),
        multiple_outputs=False,
        show_return_value_in_logs=False,
    )
    def extract_batch(prepared):
        from pathlib import Path

        from airflow.exceptions import AirflowFailException

        from scripts.weather_interface import execute_extraction

        try:
            metadata = execute_extraction(
                manifest_path=prepared["manifest_path"],
                manifest_sha256=prepared["manifest_sha256"],
                project_root=Path(__file__).resolve().parent.parent,
            )
        except (ValueError, OSError):
            raise AirflowFailException(
                "Extração bloqueada; consultar os artefatos e incidentes locais."
            ) from None
        # Resultado parcial é preservado; a reconciliação determina o aceite.
        return _small_metadata(metadata)

    @task(
        task_id="reconcile_extraction",
        execution_timeout=timedelta(minutes=2),
        multiple_outputs=False,
        show_return_value_in_logs=False,
    )
    def reconcile_extraction(extracted):
        import hashlib
        import json
        import logging
        from pathlib import Path

        from airflow.exceptions import AirflowFailException

        from scripts.weather_interface import verify_batch_artifacts
        from scripts.weather_manifest import load_verified_manifest, resolve_reference

        # Somente leitura: nunca chamar execute_extraction nesta task.
        try:
            root = Path(__file__).resolve().parent.parent
            manifest = load_verified_manifest(
                project_root=root,
                manifest_path=extracted["manifest_path"],
                manifest_sha256=extracted["manifest_sha256"],
            )
            verified = verify_batch_artifacts(project_root=root, manifest=manifest)
            batch_id = manifest["batch_id"]
            execution_dir = f"data/orchestration/executions/{batch_id}"
            started_bytes = resolve_reference(root, f"{execution_dir}/started.json").read_bytes()
            started = json.loads(started_bytes)
            completed = json.loads(
                resolve_reference(root, f"{execution_dir}/completed.json").read_bytes()
            )
            if (
                started["batch_id"] != batch_id
                or started["manifest_sha256"] != extracted["manifest_sha256"]
                or completed != {
                    "batch_id": batch_id,
                    "manifest_sha256": extracted["manifest_sha256"],
                    "claim_sha256": hashlib.sha256(started_bytes).hexdigest(),
                    "result": verified,
                }
            ):
                raise ValueError
            for key in (
                "batch_id", "cycle_date", "batch_status", "location_count",
                "successful_location_count", "record_count", "null_count",
                "batch_report_path",
            ):
                if extracted[key] != verified[key]:
                    raise ValueError
        except (ValueError, OSError, KeyError, TypeError):
            raise AirflowFailException(
                "Reconciliação bloqueada: integridade dos artefatos não comprovada."
            ) from None

        summary = {
            key: verified[key]
            for key in (
                "batch_id", "cycle_date", "batch_status", "location_count",
                "successful_location_count", "record_count", "null_count",
                "batch_report_path",
            )
        }
        logging.getLogger(__name__).info(
            "Reconciliação: batch=%s cycle=%s status=%s localidades=%s/%s registros=%s nulos=%s",
            summary["batch_id"], summary["cycle_date"], summary["batch_status"],
            summary["successful_location_count"], summary["location_count"],
            summary["record_count"], summary["null_count"],
        )
        if summary["batch_status"] != "success":
            raise AirflowFailException(
                "Rodada parcial ou falha; resultados preservados, sem aceite integral."
            )
        return _small_metadata(summary)

    prepared = prepare_extraction()
    extracted = extract_batch(prepared)
    reconciled = reconcile_extraction(extracted)
    prepared >> extracted >> reconciled
