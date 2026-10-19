"""Controle imutável de propriedade. Não executa ou recupera coleta.

Garantia restrita a participantes que compartilham este namespace/filesystem.
Atomicidade de publicação não equivale a durabilidade perante queda de energia.
"""

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from scripts.weather_manifest import encode_document, resolve_reference
from scripts.weather_temporal import (
    DailySlot, LOCATION_IDS, POLICY_VERSION, evaluate_admission,
    parse_instant, resolve_daily_slot, utc_text,
)


class SlotControlError(ValueError):
    pass


def canonical_slot_bytes(slot):
    if not isinstance(slot, DailySlot):
        raise SlotControlError("Slot inválido.")
    return json.dumps({
        "pipeline": "logistics-weather-data-pipeline",
        "purpose": "daily-logistics-decision",
        "scheduled_slot_utc": utc_text(slot.scheduled_slot),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")


def slot_reference(slot):
    digest = hashlib.sha256(canonical_slot_bytes(slot)).hexdigest()
    return f"data/orchestration/slots/{digest}/claim.json"


def _hash(value):
    if (
        not isinstance(value, str) or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise SlotControlError("SHA-256 inválido.")
    return value


def _uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise SlotControlError("UUID não canônico.")


def _exact(document, fields):
    if not isinstance(document, dict) or set(document) != set(fields):
        raise SlotControlError("Campos do controle diferentes do schema.")


def _validate_claim(document, root):
    _exact(document, {
        "schema_version", "slot", "slot_sha256", "cycle_date", "policy_version",
        "owner", "claim_token", "batch_id", "run_ids", "input_sha256",
        "claimed_at", "manifest_path", "manifest_sha256",
    })
    if document["schema_version"] != "1" or document["policy_version"] != POLICY_VERSION:
        raise SlotControlError("Versão de controle/política incompatível.")
    slot = resolve_daily_slot(source="cli", cycle_date=document["cycle_date"])
    identity = canonical_slot_bytes(slot)
    if document["slot"] != json.loads(identity):
        raise SlotControlError("Identidade de slot divergente.")
    if document["slot_sha256"] != hashlib.sha256(identity).hexdigest():
        raise SlotControlError("Hash de slot divergente.")
    _hash(document["input_sha256"])
    _hash(document["manifest_sha256"])
    _uuid(document["batch_id"])
    _uuid(document["claim_token"])
    runs = document["run_ids"]
    if not isinstance(runs, dict) or set(runs) != LOCATION_IDS:
        raise SlotControlError("Mapa de runs diferente das cinco localidades.")
    for run_id in runs.values():
        _uuid(run_id)
    if len(set(runs.values())) != 5:
        raise SlotControlError("Run ID reutilizado entre cidades.")
    claimed = parse_instant(document["claimed_at"])
    if utc_text(claimed) != document["claimed_at"]:
        raise SlotControlError("Instante de claim não canônico.")
    if not evaluate_admission(slot, claimed)["eligible"]:
        raise SlotControlError("Claim fora da janela de admissão.")
    owner = document["owner"]
    if not isinstance(owner, dict):
        raise SlotControlError("Proprietário inválido.")
    if owner.get("source") == "cli":
        _exact(owner, {"source", "invocation_id"})
        _uuid(owner["invocation_id"])
        expected = f"data/orchestration/batches/{document['batch_id']}/manifest.json"
    elif owner.get("source") in {"manual", "scheduled"}:
        _exact(owner, {"source", "dag_id", "airflow_run_id"})
        if owner["dag_id"] != "logistics_weather_extract":
            raise SlotControlError("DAG proprietária inválida.")
        run_id = owner["airflow_run_id"]
        if not isinstance(run_id, str) or not run_id.strip() or run_id != run_id.strip():
            raise SlotControlError("Airflow run ID inválido.")
        context_key = hashlib.sha256(encode_document({
            "dag_id": owner["dag_id"], "airflow_run_id": run_id,
        })).hexdigest()
        expected = f"data/orchestration/contexts/{context_key}/manifest.json"
    else:
        raise SlotControlError("Origem proprietária inválida.")
    if document["manifest_path"] != expected:
        raise SlotControlError("Caminho do manifesto diverge do proprietário.")
    resolve_reference(root, expected)
    return slot


def _read(root, reference):
    target = resolve_reference(root, reference)
    if (Path(root) / reference).is_symlink():
        raise SlotControlError("Link simbólico não permitido no controle.")
    content = target.read_bytes()
    try:
        document = json.loads(content)
        if encode_document(document) != content:
            raise SlotControlError("Controle não canônico.")
    except (ValueError, TypeError, UnicodeError) as error:
        raise SlotControlError("Controle corrompido; nenhuma recuperação automática.") from error
    return document, hashlib.sha256(content).hexdigest()


def _publish_exclusive(root, reference, document):
    """Existência nunca é aquisição, inclusive quando os bytes são iguais."""
    target = resolve_reference(root, reference)
    content = encode_document(document)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with NamedTemporaryFile(mode="wb", dir=target.parent, prefix=".pending-",
                                suffix=".json", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.link(temporary_path, target)
        except FileExistsError:
            return False
        if target.read_bytes() != content:
            raise SlotControlError("Publicação não confirmada; preservar reserva.")
        return True
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def inspect_slot(*, root, slot):
    """Inspeciona propriedade, não comprova conclusão nem autoriza replay."""
    reference = slot_reference(slot)
    try:
        document, digest = _read(root, reference)
    except FileNotFoundError:
        return {"state": "absent", "path": reference, "created": False}
    validated = _validate_claim(document, root)
    if validated != slot:
        raise SlotControlError("Registro pertence a outro slot.")
    return {
        "state": "claimed", "path": reference, "sha256": digest,
        "document": document, "created": False,
    }


def acquire_slot(*, root, candidate):
    """O coordenador deve validar relógio real antes de construir o candidato."""
    # Copiar pela serialização impede alterações do dicionário durante a chamada.
    candidate = json.loads(encode_document(candidate))
    slot = _validate_claim(candidate, root)
    reference = slot_reference(slot)
    created = _publish_exclusive(root, reference, candidate)
    result = inspect_slot(root=root, slot=slot)
    if result["state"] != "claimed":
        raise SlotControlError("Reserva desapareceu; não iniciar coleta.")
    if created:
        if result["document"] != candidate:
            raise SlotControlError("Reserva mudou após aquisição.")
        result["created"] = True
        return result
    original = result["document"]
    if any(original[key] != candidate[key] for key in (
        "input_sha256", "policy_version",
    )):
        result["state"] = "conflict"
    # Mesmo proprietário/token recebe created=False; não reemitir autorização.
    return result


def claim_dispatch(*, root, claim_reference, manifest_reference, dispatch_id, now):
    """Barreira de entrada única. Só o coordenador proprietário deve invocar.

    Requer referências {path, sha256}; não recupera dispatch nem autoriza HTTP.
    """
    claim, claim_hash = _read(root, claim_reference["path"])
    slot = _validate_claim(claim, root)
    if claim_reference != {"path": slot_reference(slot), "sha256": claim_hash}:
        raise SlotControlError("Referência de claim divergente.")
    if manifest_reference != {
        "path": claim["manifest_path"], "sha256": claim["manifest_sha256"],
    }:
        raise SlotControlError("Referência de manifesto divergente do claim.")
    from scripts.weather_manifest import load_verified_manifest
    manifest = load_verified_manifest(
        project_root=root, manifest_path=manifest_reference["path"],
        manifest_sha256=manifest_reference["sha256"],
    )
    if (
        manifest["batch_id"] != claim["batch_id"]
        or manifest["cycle_date_local"] != claim["cycle_date"]
        or {key: value["run_id"] for key, value in manifest["runs"].items()} != claim["run_ids"]
        or manifest["orchestration_context"].get("scheduled_slot") != utc_text(slot.scheduled_slot)
    ):
        raise SlotControlError("Manifesto incompatível com o slot.")
    if not evaluate_admission(slot, now)["eligible"]:
        raise SlotControlError("Dispatch fora da admissão; reserva preservada.")
    _uuid(dispatch_id)
    reference = claim_reference["path"].removesuffix("claim.json") + "dispatch.json"
    document = {
        "schema_version": "1", "slot_sha256": claim["slot_sha256"],
        "claim_sha256": claim_hash, "manifest_sha256": claim["manifest_sha256"],
        "batch_id": claim["batch_id"], "dispatch_id": dispatch_id,
        "dispatched_at": utc_text(now),
    }
    if not _publish_exclusive(root, reference, document):
        raise SlotControlError("Dispatch existente; exigir inspeção, sem retomada automática.")
    return {"path": reference, "sha256": hashlib.sha256(encode_document(document)).hexdigest()}
