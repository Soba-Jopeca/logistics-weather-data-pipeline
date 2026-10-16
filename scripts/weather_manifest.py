import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
from tempfile import NamedTemporaryFile


def resolve_reference(project_root, reference):
    if not isinstance(reference, str) or not reference:
        raise ValueError("A referência deve ser um caminho relativo.")

    if (
        "\\" in reference
        or ":" in reference
        or PureWindowsPath(reference).is_absolute()
        or Path(reference).is_absolute()
        or any(part in ("", ".", "..") for part in reference.split("/"))
    ):
        raise ValueError("Referência de arquivo inválida.")

    root = Path(project_root).resolve()
    target = (root / reference).resolve()

    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError("Referência fora da raiz autorizada.") from error

    return target


def encode_document(document):
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        indent=4,
        allow_nan=False,
    ).encode("utf-8")


def persist_immutable_document(project_root, reference, document):
    target = resolve_reference(project_root, reference)
    content = encode_document(document)
    target.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = None

    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=".pending-",
            suffix=".json",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())

        try:
            # Publicar o arquivo completo sem substituir um destino existente.
            os.link(temporary_path, target)
        except FileExistsError:
            if target.read_bytes() != content:
                raise ValueError(
                    "Documento conflitante; o original foi preservado."
                )

        saved_bytes = target.read_bytes()

        if saved_bytes != content:
            raise OSError("Conteúdo persistido diferente do esperado.")

        return {
            "path": reference,
            "sha256": hashlib.sha256(saved_bytes).hexdigest(),
        }

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
def build_manifest_document(
    *,
    cycle_date,
    config,
    locations,
    batch_id,
    run_ids,
    orchestration_context=None,
):
    from copy import deepcopy
    from datetime import date
    from uuid import UUID

    from scripts.extract_weather import (
        build_request_params,
        validate_locations,
    )
    from scripts.weather_window import build_cycle_window

    if type(cycle_date) is not date:
        raise ValueError("cycle_date deve ser uma data, sem horário.")

    if not isinstance(config, dict):
        raise ValueError("Configuração inválida.")

    if set(config) != {"endpoint", "timeout"}:
        raise ValueError("Configuração contém campos ausentes ou desconhecidos.")

    endpoint = config["endpoint"]

    if endpoint != "https://api.open-meteo.com/v1/forecast":
        raise ValueError("Endpoint diferente da fonte aprovada.")

    timeout = config["timeout"]

    if (
        not isinstance(timeout, (list, tuple))
        or len(timeout) != 2
        or any(type(value) not in (int, float) for value in timeout)
        or list(timeout) != [10, 30]
    ):
        raise ValueError("Timeout diferente da política aprovada.")

    locations_snapshot = deepcopy(locations)
    validate_locations(locations_snapshot)

    location_ids = [
        location["location_id"]
        for location in locations_snapshot
    ]

    if not isinstance(run_ids, dict) or set(run_ids) != set(location_ids):
        raise ValueError("run_ids deve identificar todas as localidades.")

    canonical_batch_id = str(UUID(batch_id))
    canonical_run_ids = {
        location_id: str(UUID(run_ids[location_id]))
        for location_id in location_ids
    }

    if len(set(canonical_run_ids.values())) != len(location_ids):
        raise ValueError("Cada localidade deve possuir um run_id distinto.")

    context = deepcopy(
        orchestration_context
        if orchestration_context is not None
        else {}
    )

    allowed_context = {
        "dag_id",
        "airflow_run_id",
        "logical_date",
        "data_interval_start",
        "data_interval_end",
        "scheduled_slot",
        "origin_batch_id",
    }

    if not isinstance(context, dict) or set(context) - allowed_context:
        raise ValueError("Contexto de orquestração contém campos inválidos.")

    for value in context.values():
        if value is not None and (
            not isinstance(value, str) or not value.strip()
        ):
            raise ValueError("Valores do contexto devem ser textos ou null.")

    has_dag = bool(context.get("dag_id"))
    has_airflow_run = bool(context.get("airflow_run_id"))

    if has_dag != has_airflow_run:
        raise ValueError("dag_id e airflow_run_id devem ser fornecidos juntos.")

    if context.get("origin_batch_id") is not None:
        context["origin_batch_id"] = str(UUID(context["origin_batch_id"]))

    requests_snapshot = {}

    for location in locations_snapshot:
        window = build_cycle_window(
            cycle_date,
            location["timezone"],
        )

        requests_snapshot[location["location_id"]] = {
            "run_id": canonical_run_ids[location["location_id"]],
            "request_params": build_request_params(location, window),
            "cycle": {
                "cycle_date_local": cycle_date.isoformat(),
                "timezone": window["timezone"],
                "window_start_utc": window["window_start_utc"].isoformat(),
                "window_end_utc": window["window_end_utc"].isoformat(),
            },
        }

    return {
        "manifest_version": "1",
        "extraction_contract": "weather-v0.1",
        "batch_id": canonical_batch_id,
        "cycle_date_local": cycle_date.isoformat(),
        "config": {
            "endpoint": endpoint,
            "timeout": list(timeout),
        },
        "locations": locations_snapshot,
        "runs": requests_snapshot,
        "orchestration_context": context,
    }

def load_verified_manifest(
    *,
    project_root,
    manifest_path,
    manifest_sha256,
):
    from datetime import date

    if (
        not isinstance(manifest_sha256, str)
        or len(manifest_sha256) != 64
        or any(character not in "0123456789abcdef"
               for character in manifest_sha256)
    ):
        raise ValueError("Hash do manifesto inválido.")

    if (
        not isinstance(manifest_path, str)
        or not manifest_path.startswith("data/orchestration/")
        or not manifest_path.endswith("/manifest.json")
    ):
        raise ValueError("Referência de manifesto inválida.")

    path = resolve_reference(project_root, manifest_path)
    content = path.read_bytes()

    if hashlib.sha256(content).hexdigest() != manifest_sha256:
        raise ValueError("Hash do manifesto divergente.")

    try:
        document = json.loads(content)

        if not isinstance(document, dict):
            raise ValueError("O manifesto deve ser um objeto.")

        runs = document["runs"]

        if not isinstance(runs, dict):
            raise ValueError("Mapa de runs inválido.")

        rebuilt = build_manifest_document(
            cycle_date=date.fromisoformat(document["cycle_date_local"]),
            config=document["config"],
            locations=document["locations"],
            batch_id=document["batch_id"],
            run_ids={
                location_id: run["run_id"]
                for location_id, run in runs.items()
            },
            orchestration_context=document["orchestration_context"],
        )

        if encode_document(rebuilt) != content:
            raise ValueError("Manifesto incoerente com o contrato.")

    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError("Estrutura do manifesto inválida.") from error

    return document