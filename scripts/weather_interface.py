import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

from scripts.weather_manifest import (
    build_manifest_document,
    encode_document,
    persist_immutable_document,
    resolve_reference,
)


def _prepare_extraction(
    *,
    cycle_date,
    config,
    locations,
    project_root,
    orchestration_context=None,
    batch_id=None,
    run_ids=None,
):
    context = (
        orchestration_context
        if orchestration_context is not None
        else {}
    )

    if not isinstance(context, dict):
        raise ValueError("Contexto de orquestração inválido.")

    dag_id = context.get("dag_id")
    airflow_run_id = context.get("airflow_run_id")

    if bool(dag_id) != bool(airflow_run_id):
        raise ValueError("dag_id e airflow_run_id devem ser fornecidos juntos.")

    if dag_id and airflow_run_id:
        identity = {
            "dag_id": dag_id,
            "airflow_run_id": airflow_run_id,
        }
        context_key = hashlib.sha256(
            encode_document(identity)
        ).hexdigest()

        reference = (
            f"data/orchestration/contexts/{context_key}/manifest.json"
        )
    else:
        batch_id = (
            str(uuid4())
            if batch_id is None
            else str(UUID(batch_id))
        )
        reference = (
            f"data/orchestration/batches/{batch_id}/manifest.json"
        )

    target = resolve_reference(project_root, reference)

    if target.exists():
        existing = json.loads(target.read_bytes())

        if not isinstance(existing, dict):
            raise ValueError("Manifesto existente inválido.")

        if batch_id is None:
            batch_id = existing.get("batch_id")

        if run_ids is None:
            runs = existing.get("runs")

            if not isinstance(runs, dict):
                raise ValueError("Mapa de runs do manifesto inválido.")

            run_ids = {
                location_id: run["run_id"]
                for location_id, run in runs.items()
            }

    else:
        batch_id = str(uuid4()) if batch_id is None else batch_id

        if run_ids is None:
            run_ids = {
                location["location_id"]: str(uuid4())
                for location in locations
            }

    document = build_manifest_document(
        cycle_date=cycle_date,
        config=config,
        locations=locations,
        batch_id=batch_id,
        run_ids=run_ids,
        orchestration_context=context,
    )

    persisted = persist_immutable_document(
        project_root,
        reference,
        document,
    )

    return {
        "manifest_path": persisted["path"],
        "manifest_sha256": persisted["sha256"],
        "batch_id": document["batch_id"],
        "cycle_date": document["cycle_date_local"],
    }

def claim_extraction(
    *,
    project_root,
    batch_id,
    manifest_sha256,
):
    from datetime import datetime, timezone

    canonical_batch_id = str(UUID(batch_id))

    if (
        not isinstance(manifest_sha256, str)
        or len(manifest_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in manifest_sha256
        )
    ):
        raise ValueError("Hash do manifesto inválido.")

    reference = (
        f"data/orchestration/executions/"
        f"{canonical_batch_id}/started.json"
    )

    claim = {
        "batch_id": canonical_batch_id,
        "manifest_sha256": manifest_sha256,
        "execution_token": str(uuid4()),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        return persist_immutable_document(
            project_root,
            reference,
            claim,
        )
    except ValueError as error:
        raise ValueError(
            "A rodada já possui uma marca de início. "
            "Exigir reconciliação do resultado final; "
            "não iniciar outra coleta automaticamente."
        ) from error

def record_extraction_incident(
    *,
    project_root,
    category,
    batch_id=None,
):
    from datetime import datetime, timezone

    allowed_categories = {
        "manifest_integrity",
        "ambiguous_state",
        "artifact_integrity",
        "persistence_error",
        "execution_error",
    }

    if category not in allowed_categories:
        raise ValueError("Categoria de incidente inválida.")

    canonical_batch_id = (
        str(UUID(batch_id))
        if batch_id is not None
        else None
    )

    incident_id = str(uuid4())
    reference = (
        f"data/orchestration/incidents/{incident_id}.json"
    )

    document = {
        "incident_id": incident_id,
        "batch_id": canonical_batch_id,
        "category": category,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "automatic_collection_blocked": True,
    }

    return persist_immutable_document(
        project_root,
        reference,
        document,
    )

def verify_run_artifacts(*, project_root, manifest, location):
    location_id = location["location_id"]
    expected = manifest["runs"][location_id]
    run_id = expected["run_id"]
    reference = f"data/raw/runs/{run_id}.json"

    report_bytes = resolve_reference(
        project_root, reference
    ).read_bytes()
    report = json.loads(report_bytes)

    if not isinstance(report, dict):
        raise ValueError("Relatório de run inválido.")

    expected_fields = {
        "run_id": run_id,
        "batch_id": manifest["batch_id"],
        "location_id": location_id,
        "location": location,
        "source": "Open-Meteo",
        "endpoint": manifest["config"]["endpoint"],
        "request_params": expected["request_params"],
        "cycle": expected["cycle"],
    }

    for field, value in expected_fields.items():
        if report.get(field) != value:
            raise ValueError("Relatório divergente do manifesto.")

    allowed_statuses = {
        "validated",
        "validated_with_nulls",
        "incomplete",
        "failed",
    }

    if report.get("run_status") not in allowed_statuses:
        raise ValueError("Estado do run inválido.")

    attempts = report.get("attempts")

    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 3:
        raise ValueError("Tentativas ausentes ou fora do limite.")

    attempt_ids = set()

    for number, attempt in enumerate(attempts, start=1):
        if not isinstance(attempt, dict):
            raise ValueError("Registro de tentativa inválido.")

        attempt_id = str(UUID(attempt["attempt_id"]))

        if (
            attempt["run_id"] != run_id
            or type(attempt["attempt_no"]) is not int
            or attempt["attempt_no"] != number
            or attempt_id in attempt_ids
        ):
            raise ValueError("Identidade ou sequência de tentativa inválida.")

        attempt_ids.add(attempt_id)

    if report.get("requested_at") != attempts[0].get("started_at"):
        raise ValueError("Início da solicitação divergente das tentativas.")

    artifacts = {
        reference: hashlib.sha256(report_bytes).hexdigest(),
    }

    raw_reference = report.get("raw_path")
    raw_hash = report.get("raw_sha256")

    if raw_reference is None:
        if (
            raw_hash is not None
            or report["run_status"] != "failed"
            or report.get("collected_at") is not None
            or attempts[-1].get("http_status") is not None
        ):
            raise ValueError("Ausência de Raw incoerente com o run.")

    else:
        if raw_reference != f"data/raw/weather_{run_id}.json":
            raise ValueError("Caminho Raw divergente do run.")

        raw_bytes = resolve_reference(
            project_root, raw_reference
        ).read_bytes()
        actual_hash = hashlib.sha256(raw_bytes).hexdigest()

        if raw_hash != actual_hash:
            raise ValueError("Hash Raw divergente.")

        if report.get("collected_at") != attempts[-1].get("ended_at"):
            raise ValueError("Coleta divergente da última tentativa.")

        artifacts[raw_reference] = actual_hash

    return {
        "report": report,
        "report_path": reference,
        "artifact_hashes": artifacts,
        "attempt_ids": sorted(attempt_ids),
    }

def verify_batch_artifacts(*, project_root, manifest):
    from datetime import date, datetime

    from scripts.extract_weather import process_forecast
    from scripts.weather_window import build_cycle_window

    batch_id = manifest["batch_id"]
    reference = f"data/raw/batches/{batch_id}.json"

    summary_bytes = resolve_reference(
        project_root, reference
    ).read_bytes()
    summary = json.loads(summary_bytes)

    if not isinstance(summary, dict):
        raise ValueError("Resumo da rodada inválido.")

    if (
        summary.get("batch_id") != batch_id
        or summary.get("cycle_date_local") != manifest["cycle_date_local"]
    ):
        raise ValueError("Resumo divergente do manifesto.")

    results = summary.get("results")
    locations = manifest["locations"]

    if not isinstance(results, list) or len(results) != len(locations):
        raise ValueError("Resumo não contém todas as localidades.")

    artifact_hashes = {
        reference: hashlib.sha256(summary_bytes).hexdigest(),
    }
    seen_attempts = set()
    successful = 0
    record_count = 0
    null_count = 0

    for location, result in zip(locations, results):
        verified = verify_run_artifacts(
            project_root=project_root,
            manifest=manifest,
            location=location,
        )
        report = verified["report"]

        if (
            not isinstance(result, dict)
            or result.get("report") != report
            or result.get("report_path") != verified["report_path"]
        ):
            raise ValueError("Resumo e relatório individual divergem.")

        attempt_ids = set(verified["attempt_ids"])

        if seen_attempts & attempt_ids:
            raise ValueError("Tentativa reutilizada entre cidades.")

        seen_attempts.update(attempt_ids)
        artifact_hashes.update(verified["artifact_hashes"])

        if report["run_status"] != "failed":
            raw_bytes = resolve_reference(
                project_root, report["raw_path"]
            ).read_bytes()
            payload = json.loads(raw_bytes)

            window = build_cycle_window(
                date.fromisoformat(manifest["cycle_date_local"]),
                location["timezone"],
            )
            collected_at = datetime.fromisoformat(report["collected_at"])

            _, validation = process_forecast(
                payload,
                window,
                collected_at,
                report["run_id"],
                location["location_id"],
            )

            if validation != report.get("validation"):
                raise ValueError("Validação persistida diverge do Raw.")

            if not validation["coverage"]["coverage_complete"]:
                expected_status = "incomplete"
            elif any(validation["null_counts"].values()):
                expected_status = "validated_with_nulls"
            else:
                expected_status = "validated"

            if report["run_status"] != expected_status:
                raise ValueError("Estado do run diverge da validação.")

            record_count += validation["record_count"]
            null_count += sum(validation["null_counts"].values())

        if report["run_status"] in ("validated", "validated_with_nulls"):
            successful += 1

    if successful == len(locations):
        expected_batch_status = "success"
    elif successful:
        expected_batch_status = "partial_success"
    else:
        expected_batch_status = "failed"

    if (
        summary.get("batch_status") != expected_batch_status
        or summary.get("location_count") != len(locations)
        or summary.get("successful_location_count") != successful
    ):
        raise ValueError("Estado ou contadores da rodada incoerentes.")

    return {
        "batch_id": batch_id,
        "cycle_date": manifest["cycle_date_local"],
        "batch_status": expected_batch_status,
        "location_count": len(locations),
        "successful_location_count": successful,
        "record_count": record_count,
        "null_count": null_count,
        "batch_report_path": reference,
        "artifact_hashes": artifact_hashes,
    }

def execute_extraction(
    *,
    manifest_path,
    manifest_sha256,
    project_root,
):
    from datetime import date

    from scripts.extract_weather import collect_batch, save_batch_report
    from scripts.weather_manifest import load_verified_manifest

    batch_id = None
    phase = "manifest_integrity"

    try:
        manifest = load_verified_manifest(
            project_root=project_root,
            manifest_path=manifest_path,
            manifest_sha256=manifest_sha256,
        )
        batch_id = manifest["batch_id"]

        execution_dir = (
            f"data/orchestration/executions/{batch_id}"
        )
        started_reference = f"{execution_dir}/started.json"
        completed_reference = f"{execution_dir}/completed.json"

        started_path = resolve_reference(project_root, started_reference)
        completed_path = resolve_reference(project_root, completed_reference)

        if completed_path.exists():
            phase = "artifact_integrity"

            started_bytes = started_path.read_bytes()
            started = json.loads(started_bytes)

            if (
                started["batch_id"] != batch_id
                or started["manifest_sha256"] != manifest_sha256
            ):
                raise ValueError("Marca de início divergente.")

            verified = verify_batch_artifacts(
                project_root=project_root,
                manifest=manifest,
            )

            expected_completion = {
                "batch_id": batch_id,
                "manifest_sha256": manifest_sha256,
                "claim_sha256": hashlib.sha256(
                    started_bytes
                ).hexdigest(),
                "result": verified,
            }

            completed = json.loads(completed_path.read_bytes())

            if completed != expected_completion:
                raise ValueError("Conclusão ou artefatos divergentes.")

            mode = "replay"

        else:
            phase = "ambiguous_state"

            if started_path.exists():
                raise ValueError("Execução iniciada sem conclusão confirmada.")

            expected_artifacts = [
                f"data/raw/batches/{batch_id}.json",
            ]

            for run in manifest["runs"].values():
                run_id = run["run_id"]
                expected_artifacts.extend([
                    f"data/raw/runs/{run_id}.json",
                    f"data/raw/weather_{run_id}.json",
                ])

            if any(
                resolve_reference(project_root, reference).exists()
                for reference in expected_artifacts
            ):
                raise ValueError("Artefatos existentes sem conclusão confirmada.")

            claim = claim_extraction(
                project_root=project_root,
                batch_id=batch_id,
                manifest_sha256=manifest_sha256,
            )

            phase = "execution_error"

            batch = collect_batch(
                manifest["config"],
                manifest["locations"],
                date.fromisoformat(manifest["cycle_date_local"]),
                batch_id=batch_id,
                run_ids={
                    location_id: run["run_id"]
                    for location_id, run in manifest["runs"].items()
                },
                project_root=project_root,
                request_params_by_location={
                    location_id: run["request_params"]
                    for location_id, run in manifest["runs"].items()
                },
            )

            phase = "persistence_error"
            save_batch_report(batch, project_root=project_root)

            phase = "artifact_integrity"
            verified = verify_batch_artifacts(
                project_root=project_root,
                manifest=manifest,
            )

            phase = "persistence_error"
            persist_immutable_document(
                project_root,
                completed_reference,
                {
                    "batch_id": batch_id,
                    "manifest_sha256": manifest_sha256,
                    "claim_sha256": claim["sha256"],
                    "result": verified,
                },
            )

            mode = "new_collection"

        return {
            "batch_id": batch_id,
            "cycle_date": verified["cycle_date"],
            "batch_status": verified["batch_status"],
            "location_count": verified["location_count"],
            "successful_location_count": (
                verified["successful_location_count"]
            ),
            "record_count": verified["record_count"],
            "null_count": verified["null_count"],
            "manifest_path": manifest_path,
            "manifest_sha256": manifest_sha256,
            "batch_report_path": verified["batch_report_path"],
            "completion_path": completed_reference,
            "mode": mode,
        }

    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        OverflowError,
    ) as error:
        try:
            incident = record_extraction_incident(
                project_root=project_root,
                category=phase,
                batch_id=batch_id,
            )
        except (ValueError, OSError):
            raise ValueError(
                "Extração bloqueada. Não foi possível persistir "
                "a auditoria do incidente."
            ) from None

        raise ValueError(
            f"Extração bloqueada. Incidente: {incident['path']}"
        ) from None

def prepare_extraction(
    *,
    cycle_date,
    config,
    locations,
    project_root,
    orchestration_context=None,
    batch_id=None,
    run_ids=None,
):
    try:
        return _prepare_extraction(
            cycle_date=cycle_date,
            config=config,
            locations=locations,
            project_root=project_root,
            orchestration_context=orchestration_context,
            batch_id=batch_id,
            run_ids=run_ids,
        )

    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        OverflowError,
    ):
        incident_batch_id = None

        if isinstance(batch_id, str):
            try:
                incident_batch_id = str(UUID(batch_id))
            except ValueError:
                pass

        try:
            incident = record_extraction_incident(
                project_root=project_root,
                category="manifest_integrity",
                batch_id=incident_batch_id,
            )
        except (ValueError, OSError):
            raise ValueError(
                "Preparação bloqueada. Não foi possível persistir "
                "a auditoria do incidente."
            ) from None

        raise ValueError(
            f"Preparação bloqueada. Incidente: {incident['path']}"
        ) from None
