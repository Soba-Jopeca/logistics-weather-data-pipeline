"""Manual-only warehouse loading of an already completed weather batch.

Independent of weather_extract.py; no network extraction or scheduler.
"""
from datetime import timedelta
from uuid import UUID

import pendulum
from airflow import DAG
from airflow.decorators import task


with DAG(
    dag_id="logistics_weather_warehouse",
    description="Load a verified completed Raw batch into the weather warehouse.",
    start_date=pendulum.datetime(2026, 10, 15, tz="America/Sao_Paulo"),
    schedule=None,
    catchup=False,
    is_paused_upon_creation=True,
    max_active_runs=1,
    max_active_tasks=1,
    dagrun_timeout=timedelta(minutes=20),
    default_args={"depends_on_past": False, "retries": 0},
    tags=["weather", "warehouse"],
) as dag:

    @task(task_id="validate_completed_batch",
          execution_timeout=timedelta(minutes=5),
          show_return_value_in_logs=False)
    def validate_completed_batch():
        from airflow.operators.python import get_current_context
        from airflow.exceptions import AirflowFailException
        from scripts.weather_store import build_load_package, WeatherStoreError

        conf = get_current_context()["dag_run"].conf or {}
        if set(conf) != {"batch_id"}:
            raise AirflowFailException("Manual invocation requires only batch_id.")
        try:
            batch_id = str(UUID(conf["batch_id"]))
            package = build_load_package(batch_id)
        except (ValueError, TypeError, OSError, KeyError, WeatherStoreError):
            raise AirflowFailException("Completed batch verification failed.") from None
        return {"batch_id": batch_id, "forecast_count": len(package["forecasts"])}

    @task(task_id="load_warehouse_batch",
          execution_timeout=timedelta(minutes=10),
          show_return_value_in_logs=False)
    def load_warehouse_batch(verified):
        from airflow.exceptions import AirflowFailException
        from scripts.weather_store import (
            build_load_package, persist_load_package,
            connect_weather_database, WeatherStoreError,
        )
        try:
            # Rebuild and verify on the worker, never ship JSON through XCom.
            package = build_load_package(verified["batch_id"])
            if len(package["forecasts"]) != verified["forecast_count"]:
                raise WeatherStoreError("Batch changed between tasks.")
            result = persist_load_package(
                package, connect=connect_weather_database
            )
        except Exception as error:
            # Hide potentially sensitive exception details in Airflow logs.
            raise AirflowFailException(
                "Warehouse load failed; inspect isolated database and artifacts."
            ) from None
        return {
            "batch_id": result["batch_id"],
            "forecast_count": result["forecast_count"],
            "loaded": result["loaded"],
            "idempotent_replay": result["idempotent_replay"],
        }

    load_warehouse_batch(validate_completed_batch())
