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
        from pathlib import Path
        from airflow.exceptions import AirflowFailException
        from airflow.operators.python import get_current_context
        from scripts.extract_weather import load_api_config, load_locations
        from scripts.weather_daily import airflow_daily_request, prepare_daily_extraction
        from scripts.weather_temporal import DailyAdmissionError

        context = get_current_context()
        dag_run = context["dag_run"]
        try:
            request = airflow_daily_request(
                run_type=dag_run.run_type, conf=dag_run.conf,
                dag_id=context["dag"].dag_id, run_id=dag_run.run_id,
                logical_date=context["logical_date"],
                data_interval_start=context["data_interval_start"],
                data_interval_end=context["data_interval_end"],
            )
            metadata = prepare_daily_extraction(
                **request, config=load_api_config(), locations=load_locations(),
                project_root=Path(__file__).resolve().parent.parent,
            )
        except (DailyAdmissionError, ValueError, OSError):
            raise AirflowFailException(
                "Preparação diária bloqueada; verificar contexto, prazo e slot."
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

        from scripts.weather_daily import execute_daily_extraction
        from scripts.weather_temporal import DailyAdmissionError

        try:
            metadata = execute_daily_extraction(
                prepared=prepared,
                project_root=Path(__file__).resolve().parent.parent,
            )
        except (DailyAdmissionError, ValueError, OSError):
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
        import logging
        from pathlib import Path
        from airflow.exceptions import AirflowFailException
        from scripts.weather_daily import reconcile_daily_extraction

        # Reconciliação não tem caminho de transporte ou nova coleta.
        try:
            summary = reconcile_daily_extraction(
                prepared=extracted, project_root=Path(__file__).resolve().parent.parent,
            )
        except (ValueError, OSError, KeyError, TypeError):
            raise AirflowFailException(
                "Reconciliação diária bloqueada; integridade/prontidão não comprovada."
            ) from None
        logging.getLogger(__name__).info("Avaliação operacional: %s", summary)
        if not summary["eligible"]:
            raise AirflowFailException(
                "Indisponível para decisão diária; artefatos preservados."
            )
        return _small_metadata(summary)

    prepared = prepare_extraction()
    extracted = extract_batch(prepared)
    reconciled = reconcile_extraction(extracted)
    prepared >> extracted >> reconciled
