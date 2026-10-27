"""Verified, transactional persistence of immutable weather batches."""

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

from scripts.extract_weather import process_forecast
from scripts.weather_interface import (
    verify_batch_artifacts,
    verify_run_artifacts,
)
from scripts.weather_manifest import (
    load_verified_manifest,
    resolve_reference,
)
from scripts.weather_window import build_cycle_window


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = "001_weather_schema"
PRODUCT_METRICS = {
    "temperature_2m": "temperature_2m_c",
    "precipitation": "precipitation_mm",
    "wind_speed_10m": "wind_speed_10m_kmh",
}


class WeatherStoreError(ValueError):
    """A verified load could not be completed without ambiguity."""


def _read_json(path):
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeatherStoreError(f"Invalid or unreadable artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise WeatherStoreError(f"Artifact must contain a JSON object: {path.name}")
    return value


def _parse_instant(value, field, *, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise WeatherStoreError(f"Missing timestamp: {field}")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise WeatherStoreError(f"Invalid timestamp: {field}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WeatherStoreError(f"Timestamp must include a timezone: {field}")
    return parsed.astimezone(timezone.utc)


def _manifest_candidates(root, batch_id):
    references = [
        f"data/orchestration/batches/{batch_id}/manifest.json",
    ]
    contexts = root / "data" / "orchestration" / "contexts"
    if contexts.is_dir():
        references.extend(
            path.relative_to(root).as_posix()
            for path in contexts.glob("*/manifest.json")
        )
    matching = []
    for reference in references:
        path = resolve_reference(root, reference)
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(document, dict) and document.get("batch_id") == batch_id:
            matching.append(reference)
    if len(matching) != 1:
        raise WeatherStoreError(
            f"Expected one manifest for batch {batch_id}; found {len(matching)}."
        )
    return matching[0]


def build_load_package(batch_id, *, project_root=PROJECT_ROOT):
    """Verify the complete Raw chain and normalize it for one database transaction."""
    try:
        canonical_batch_id = str(UUID(batch_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise WeatherStoreError("Invalid batch_id.") from error

    root = Path(project_root).resolve()
    manifest_path = _manifest_candidates(root, canonical_batch_id)
    completion_path = f"data/orchestration/executions/{canonical_batch_id}/completed.json"
    started_path = f"data/orchestration/executions/{canonical_batch_id}/started.json"
    completion = _read_json(resolve_reference(root, completion_path))
    started_bytes = resolve_reference(root, started_path).read_bytes()
    try:
        started = json.loads(started_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeatherStoreError("Invalid execution-start artifact.") from error
    if not isinstance(started, dict):
        raise WeatherStoreError("Execution-start artifact must be a JSON object.")

    if (
        started.get("batch_id") != canonical_batch_id
        or completion.get("batch_id") != canonical_batch_id
        or completion.get("manifest_sha256") != started.get("manifest_sha256")
        or completion.get("claim_sha256") != hashlib.sha256(started_bytes).hexdigest()
    ):
        raise WeatherStoreError("Batch completion chain is inconsistent.")

    manifest = load_verified_manifest(
        project_root=root,
        manifest_path=manifest_path,
        manifest_sha256=completion["manifest_sha256"],
    )
    verified = verify_batch_artifacts(project_root=root, manifest=manifest)
    if completion.get("result") != verified:
        raise WeatherStoreError("Completed marker differs from verified artifacts.")

    batch_report_path = verified["batch_report_path"]
    batch_report_bytes = resolve_reference(root, batch_report_path).read_bytes()
    batch_report = _read_json(resolve_reference(root, batch_report_path))
    first_location = manifest["locations"][0]
    cycle = manifest["runs"][first_location["location_id"]]["cycle"]

    artifacts = {}
    for reference, digest in verified["artifact_hashes"].items():
        if reference.startswith("data/raw/batches/"):
            artifact_type = "batch_report"
        elif reference.startswith("data/raw/runs/"):
            artifact_type = "run_report"
        elif reference.startswith("data/raw/weather_"):
            artifact_type = "raw"
        else:
            raise WeatherStoreError("Unknown verified artifact reference.")
        artifact_bytes = resolve_reference(root, reference).read_bytes()
        artifacts[reference] = {
            "artifact_type": artifact_type,
            "sha256": digest,
            "size_bytes": len(artifact_bytes),
        }

    for reference, artifact_type, content in (
        (manifest_path, "manifest", resolve_reference(root, manifest_path).read_bytes()),
        (started_path, "orchestration", started_bytes),
        (completion_path, "orchestration", resolve_reference(root, completion_path).read_bytes()),
    ):
        artifacts[reference] = {
            "artifact_type": artifact_type,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }

    runs = []
    attempts = []
    forecasts = []
    publications = []
    for location in manifest["locations"]:
        location_id = location["location_id"]
        run_info = manifest["runs"][location_id]
        verified_run = verify_run_artifacts(
            project_root=root,
            manifest=manifest,
            location=location,
        )
        report = verified_run["report"]
        report_path = verified_run["report_path"]
        report_bytes = resolve_reference(root, report_path).read_bytes()
        run_status = report["run_status"]
        validation = report.get("validation")
        raw_path = report.get("raw_path")

        runs.append({
            "run_id": report["run_id"],
            "batch_id": canonical_batch_id,
            "location_id": location_id,
            "location_name": location["name"],
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "timezone": location["timezone"],
            "requested_at": _parse_instant(report["requested_at"], "requested_at"),
            "collected_at": _parse_instant(
                report.get("collected_at"), "collected_at", nullable=True
            ),
            "source": report["source"],
            "endpoint": report["endpoint"],
            "request_params": report["request_params"],
            "raw_path": raw_path,
            "raw_sha256": report.get("raw_sha256"),
            "report_path": report_path,
            "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
            "run_status": run_status,
            "validation": validation,
        })

        for attempt in report["attempts"]:
            attempts.append({
                "attempt_id": attempt["attempt_id"],
                "run_id": report["run_id"],
                "attempt_no": attempt["attempt_no"],
                "started_at": _parse_instant(attempt["started_at"], "attempt.started_at"),
                "ended_at": _parse_instant(attempt["ended_at"], "attempt.ended_at"),
                "duration_ms": attempt["duration_ms"],
                "http_status": attempt["http_status"],
                "error_category": attempt["error_category"],
                "error_message": attempt["error_message"],
            })

        records = []
        if run_status != "failed":
            raw_payload = _read_json(resolve_reference(root, raw_path))
            collected_at = _parse_instant(report["collected_at"], "collected_at")
            records, normalized_validation = process_forecast(
                raw_payload,
                build_cycle_window(
                    date.fromisoformat(manifest["cycle_date_local"]),
                    location["timezone"],
                ),
                collected_at,
                report["run_id"],
                location_id,
            )
            if normalized_validation != validation:
                raise WeatherStoreError("Normalized validation differs from the run report.")
            for record in records:
                forecasts.append({
                    "run_id": record["run_id"],
                    "location_id": record["location_id"],
                    "forecast_time_utc": _parse_instant(
                        record["forecast_time_utc"], "forecast_time_utc"
                    ),
                    "temperature_2m_c": record["temperature_2m_c"],
                    "precipitation_mm": record["precipitation_mm"],
                    "wind_speed_10m_kmh": record["wind_speed_10m_kmh"],
                })

        reasons_by_product = {}
        coverage_complete = bool(
            validation
            and validation.get("coverage", {}).get("coverage_complete")
        )
        null_counts = validation.get("null_counts", {}) if validation else {}
        for product_type, metric in PRODUCT_METRICS.items():
            reasons = []
            if run_status == "failed":
                reasons.append("run_failed")
            elif not coverage_complete:
                reasons.append("incomplete_coverage")
            if run_status != "failed" and metric in null_counts and null_counts[metric]:
                reasons.append(f"{metric}_nulls")
            reasons_by_product[product_type] = reasons
            publications.append({
                "run_id": report["run_id"],
                "location_id": location_id,
                "product_type": product_type,
                "status": "published" if not reasons else "unavailable",
                "quality_reasons": reasons,
            })

        bundle_reasons = sorted({
            reason
            for reasons in reasons_by_product.values()
            for reason in reasons
        })
        publications.append({
            "run_id": report["run_id"],
            "location_id": location_id,
            "product_type": "hourly_bundle",
            "status": "published" if not bundle_reasons else "unavailable",
            "quality_reasons": bundle_reasons,
        })

    return {
        "batch": {
            "batch_id": canonical_batch_id,
            "cycle_date_local": date.fromisoformat(manifest["cycle_date_local"]),
            "timezone": cycle["timezone"],
            "window_start_utc": _parse_instant(cycle["window_start_utc"], "window_start_utc"),
            "window_end_utc": _parse_instant(cycle["window_end_utc"], "window_end_utc"),
            "batch_status": batch_report["batch_status"],
            "started_at": _parse_instant(batch_report["started_at"], "started_at"),
            "ended_at": _parse_instant(batch_report["ended_at"], "ended_at"),
            "manifest_path": manifest_path,
            "manifest_sha256": completion["manifest_sha256"],
            "batch_report_path": batch_report_path,
            "batch_report_sha256": hashlib.sha256(batch_report_bytes).hexdigest(),
        },
        "locations": manifest["locations"],
        "runs": runs,
        "attempts": attempts,
        "forecasts": forecasts,
        "publications": publications,
        "artifacts": [
            {"batch_id": canonical_batch_id, "artifact_path": path, **artifact}
            for path, artifact in sorted(artifacts.items())
        ],
    }


def _json(value):
    from psycopg2.extras import Json

    return Json(value, dumps=lambda item: json.dumps(item, allow_nan=False))


def _require_exact_rows(cursor, label, query, params, expected_rows):
    cursor.execute(query, params)
    if cursor.fetchall() != expected_rows:
        raise WeatherStoreError(
            f"Existing batch has inconsistent {label}; manual reconciliation required."
        )


def _existing_batch_is_complete(cursor, batch, package):
    cursor.execute(
        """
        SELECT rtrim(manifest_sha256), rtrim(batch_report_sha256)
        FROM weather_mvp.weather_batches
        WHERE batch_id = %s
        """,
        (batch["batch_id"],),
    )
    existing = cursor.fetchone()
    if existing is None:
        return False
    if tuple(existing) != (batch["manifest_sha256"], batch["batch_report_sha256"]):
        raise WeatherStoreError("Batch ID already exists with conflicting source hashes.")

    batch_id = batch["batch_id"]
    _require_exact_rows(
        cursor,
        "batch metadata",
        """
        SELECT cycle_date_local, timezone, window_start_utc, window_end_utc,
               batch_status, started_at, ended_at, manifest_path,
               rtrim(manifest_sha256), batch_report_path, rtrim(batch_report_sha256)
        FROM weather_mvp.weather_batches
        WHERE batch_id = %s
        """,
        (batch_id,),
        [tuple(batch[key] for key in (
            "cycle_date_local", "timezone", "window_start_utc", "window_end_utc",
            "batch_status", "started_at", "ended_at", "manifest_path",
            "manifest_sha256", "batch_report_path", "batch_report_sha256",
        ))],
    )
    location_ids = [location["location_id"] for location in package["locations"]]
    _require_exact_rows(
        cursor,
        "location snapshots",
        """
        SELECT location_id, name, latitude, longitude, timezone
        FROM weather_mvp.locations
        WHERE location_id = ANY(%s)
        ORDER BY location_id
        """,
        (location_ids,),
        [
            (
                location["location_id"], location["name"], location["latitude"],
                location["longitude"], location["timezone"],
            )
            for location in sorted(package["locations"], key=lambda item: item["location_id"])
        ],
    )
    _require_exact_rows(
        cursor,
        "run records",
        """
        SELECT run_id::TEXT, batch_id::TEXT, location_id, location_name,
               latitude, longitude, timezone, requested_at, collected_at,
               source, endpoint, request_params, raw_path, rtrim(raw_sha256),
               report_path, rtrim(report_sha256), run_status, validation
        FROM weather_mvp.weather_runs
        WHERE batch_id = %s
        ORDER BY run_id
        """,
        (batch_id,),
        [
            tuple(run[key] for key in (
                "run_id", "batch_id", "location_id", "location_name",
                "latitude", "longitude", "timezone", "requested_at", "collected_at",
                "source", "endpoint", "request_params", "raw_path", "raw_sha256",
                "report_path", "report_sha256", "run_status", "validation",
            ))
            for run in sorted(package["runs"], key=lambda item: item["run_id"])
        ],
    )
    _require_exact_rows(
        cursor,
        "attempt records",
        """
        SELECT attempt_id::TEXT, run_id::TEXT, attempt_no, started_at, ended_at,
               duration_ms, http_status, error_category, error_message
        FROM weather_mvp.weather_attempts
        WHERE run_id IN (
            SELECT run_id FROM weather_mvp.weather_runs WHERE batch_id = %s
        )
        ORDER BY run_id, attempt_no
        """,
        (batch_id,),
        [
            tuple(attempt[key] for key in (
                "attempt_id", "run_id", "attempt_no", "started_at", "ended_at",
                "duration_ms", "http_status", "error_category", "error_message",
            ))
            for attempt in sorted(
                package["attempts"],
                key=lambda item: (item["run_id"], item["attempt_no"]),
            )
        ],
    )
    _require_exact_rows(
        cursor,
        "forecast records",
        """
        SELECT run_id::TEXT, location_id, forecast_time_utc,
               temperature_2m_c, precipitation_mm, wind_speed_10m_kmh
        FROM weather_mvp.weather_forecasts
        WHERE run_id IN (
            SELECT run_id FROM weather_mvp.weather_runs WHERE batch_id = %s
        )
        ORDER BY run_id, location_id, forecast_time_utc
        """,
        (batch_id,),
        [
            tuple(forecast[key] for key in (
                "run_id", "location_id", "forecast_time_utc",
                "temperature_2m_c", "precipitation_mm", "wind_speed_10m_kmh",
            ))
            for forecast in sorted(
                package["forecasts"],
                key=lambda item: (
                    item["run_id"], item["location_id"], item["forecast_time_utc"]
                ),
            )
        ],
    )
    _require_exact_rows(
        cursor,
        "artifact records",
        """
        SELECT batch_id::TEXT, artifact_path, artifact_type, rtrim(sha256), size_bytes
        FROM weather_mvp.weather_batch_artifacts
        WHERE batch_id = %s
        ORDER BY artifact_path
        """,
        (batch_id,),
        [
            tuple(artifact[key] for key in (
                "batch_id", "artifact_path", "artifact_type", "sha256", "size_bytes",
            ))
            for artifact in sorted(package["artifacts"], key=lambda item: item["artifact_path"])
        ],
    )
    _require_exact_rows(
        cursor,
        "publication records",
        """
        SELECT run_id::TEXT, location_id, product_type, status, quality_reasons
        FROM weather_mvp.weather_publications
        WHERE run_id IN (
            SELECT run_id FROM weather_mvp.weather_runs WHERE batch_id = %s
        )
        ORDER BY run_id, location_id, product_type
        """,
        (batch_id,),
        [
            tuple(publication[key] for key in (
                "run_id", "location_id", "product_type", "status", "quality_reasons",
            ))
            for publication in sorted(
                package["publications"],
                key=lambda item: (
                    item["run_id"], item["location_id"], item["product_type"]
                ),
            )
        ],
    )
    return True


def persist_load_package(package, *, connect):
    """Persist one verified package atomically; exact batch replay is a no-op."""
    connection = connect()
    try:
        with connection:
            with connection.cursor() as cursor:
                batch = package["batch"]
                cursor.execute(
                    """
                    INSERT INTO weather_mvp.weather_batches (
                        batch_id, cycle_date_local, timezone, window_start_utc,
                        window_end_utc, batch_status, started_at, ended_at,
                        manifest_path, manifest_sha256, batch_report_path,
                        batch_report_sha256
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (batch_id) DO NOTHING
                    RETURNING batch_id
                    """,
                    (
                        batch["batch_id"], batch["cycle_date_local"], batch["timezone"],
                        batch["window_start_utc"], batch["window_end_utc"],
                        batch["batch_status"], batch["started_at"], batch["ended_at"],
                        batch["manifest_path"], batch["manifest_sha256"],
                        batch["batch_report_path"], batch["batch_report_sha256"],
                    ),
                )
                if cursor.fetchone() is None:
                    if _existing_batch_is_complete(cursor, batch, package):
                        return {
                            "batch_id": batch["batch_id"],
                            "loaded": False,
                            "idempotent_replay": True,
                            "forecast_count": len(package["forecasts"]),
                        }
                    raise WeatherStoreError("Batch identity conflict.")

                for location in package["locations"]:
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.locations (
                            location_id, name, latitude, longitude, timezone
                        ) VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (location_id) DO NOTHING
                        """,
                        (
                            location["location_id"], location["name"],
                            location["latitude"], location["longitude"],
                            location["timezone"],
                        ),
                    )
                    cursor.execute(
                        """
                        SELECT name, latitude, longitude, timezone
                        FROM weather_mvp.locations WHERE location_id = %s
                        """,
                        (location["location_id"],),
                    )
                    if cursor.fetchone() != (
                        location["name"], location["latitude"],
                        location["longitude"], location["timezone"],
                    ):
                        raise WeatherStoreError(
                            f"Location master conflicts with snapshot: {location['location_id']}"
                        )

                for run in package["runs"]:
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.weather_runs (
                            run_id, batch_id, location_id, location_name,
                            latitude, longitude, timezone, requested_at, collected_at,
                            source, endpoint, request_params, raw_path, raw_sha256,
                            report_path, report_sha256, run_status, validation
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            run["run_id"], run["batch_id"], run["location_id"],
                            run["location_name"], run["latitude"], run["longitude"],
                            run["timezone"], run["requested_at"], run["collected_at"],
                            run["source"], run["endpoint"], _json(run["request_params"]),
                            run["raw_path"], run["raw_sha256"], run["report_path"],
                            run["report_sha256"], run["run_status"],
                            _json(run["validation"]) if run["validation"] is not None else None,
                        ),
                    )

                for attempt in package["attempts"]:
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.weather_attempts (
                            attempt_id, run_id, attempt_no, started_at, ended_at,
                            duration_ms, http_status, error_category, error_message
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        tuple(attempt[key] for key in (
                            "attempt_id", "run_id", "attempt_no", "started_at",
                            "ended_at", "duration_ms", "http_status",
                            "error_category", "error_message",
                        )),
                    )

                for forecast in package["forecasts"]:
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.weather_forecasts (
                            run_id, location_id, forecast_time_utc,
                            temperature_2m_c, precipitation_mm, wind_speed_10m_kmh
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        tuple(forecast[key] for key in (
                            "run_id", "location_id", "forecast_time_utc",
                            "temperature_2m_c", "precipitation_mm", "wind_speed_10m_kmh",
                        )),
                    )

                for artifact in package["artifacts"]:
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.weather_batch_artifacts (
                            batch_id, artifact_path, artifact_type, sha256, size_bytes
                        ) VALUES (%s, %s, %s, %s, %s)
                        """,
                        tuple(artifact[key] for key in (
                            "batch_id", "artifact_path", "artifact_type",
                            "sha256", "size_bytes",
                        )),
                    )

                for publication in package["publications"]:
                    cursor.execute(
                        """
                        INSERT INTO weather_mvp.weather_publications (
                            run_id, location_id, product_type, status, quality_reasons
                        ) VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            publication["run_id"], publication["location_id"],
                            publication["product_type"], publication["status"],
                            publication["quality_reasons"],
                        ),
                    )

        return {
            "batch_id": package["batch"]["batch_id"],
            "loaded": True,
            "idempotent_replay": False,
            "forecast_count": len(package["forecasts"]),
            "run_count": len(package["runs"]),
        }
    finally:
        connection.close()


def connect_weather_database():
    """Connect using the existing WEATHER_DB_* variables; never log secrets."""
    from dotenv import load_dotenv
    import psycopg2

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    required = ("WEATHER_DB_HOST", "WEATHER_DB_NAME", "WEATHER_DB_USER", "WEATHER_DB_PASSWORD")
    values = {key: os.getenv(key, "").strip() for key in required}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise WeatherStoreError("Missing database configuration: " + ", ".join(missing))
    port_text = os.getenv("WEATHER_DB_PORT", "5432").strip()
    try:
        port = int(port_text)
    except ValueError as error:
        raise WeatherStoreError("WEATHER_DB_PORT must be an integer.") from error
    if not 1 <= port <= 65535:
        raise WeatherStoreError("WEATHER_DB_PORT is outside the TCP port range.")
    return psycopg2.connect(
        host=values["WEATHER_DB_HOST"],
        port=port,
        dbname=values["WEATHER_DB_NAME"],
        user=values["WEATHER_DB_USER"],
        password=values["WEATHER_DB_PASSWORD"],
        connect_timeout=5,
        application_name="logistics-weather-loader",
    )


def apply_weather_schema(connection):
    """Apply the additive, versioned schema in the caller's transaction."""
    schema_path = PROJECT_ROOT / "sql" / "001_weather_schema.sql"
    with connection.cursor() as cursor:
        cursor.execute(schema_path.read_text(encoding="utf-8"))
