"""Coordenação diária; controles separados dos contratos meteorológicos.

Somente prepare/execute constituem produtores suportados. Chamadas diretas
ao coletor legado não recebem garantia global de unicidade.
"""

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from scripts.weather_manifest import (
    build_manifest_document, encode_document, load_verified_manifest,
    persist_immutable_document, resolve_reference,
)
from scripts.weather_slots import (
    SlotControlError, acquire_slot, canonical_slot_bytes, claim_dispatch,
    inspect_slot, _read,
)
from scripts.weather_temporal import (
    LOCATION_IDS, POLICY_VERSION, DailyAdmissionError, FirstTransportGuard,
    aware_utc, evaluate_admission, evaluate_freshness, parse_instant,
    resolve_daily_slot, utc_text,
)


def utc_now():
    return datetime.now(timezone.utc)


def _digest(document):
    return hashlib.sha256(encode_document(document)).hexdigest()


def _fingerprint(config, locations):
    return _digest({"config": config, "locations": locations,
                    "policy_version": POLICY_VERSION})


def airflow_daily_request(*, run_type, conf, dag_id, run_id, logical_date,
                          data_interval_start, data_interval_end):
    """Adaptador puro de contexto; não importa Airflow nem executa tasks."""
    source = getattr(run_type, "value", run_type)
    if source not in {"manual", "scheduled"}:
        raise ValueError("Tipo de DAG run não suportado.")
    if not isinstance(conf, dict):
        raise ValueError("Configuração de DAG run inválida.")
    if source == "manual":
        if set(conf) != {"cycle_date"}:
            raise ValueError("Manual exige somente cycle_date explícito.")
        slot = resolve_daily_slot(source=source, cycle_date=conf["cycle_date"])
    else:
        if conf:
            raise ValueError("Agendado não admite override de ciclo.")
        slot = resolve_daily_slot(source=source, data_interval_start=data_interval_start,
                                  data_interval_end=data_interval_end)
        if aware_utc(logical_date) != aware_utc(data_interval_start):
            raise ValueError("logical_date incompatível com CronDataIntervalTimetable.")
    context = {"dag_id": dag_id, "airflow_run_id": run_id,
               "logical_date": utc_text(logical_date),
               "data_interval_start": utc_text(data_interval_start),
               "data_interval_end": utc_text(data_interval_end)}
    return {"source": source, "cycle_date": slot.cycle_date,
            "orchestration_context": context,
            "data_interval_start": data_interval_start if source == "scheduled" else None,
            "data_interval_end": data_interval_end if source == "scheduled" else None}


def _metadata(claim, *, token=None):
    document = claim["document"]
    return {
        "cycle_date": document["cycle_date"], "batch_id": document["batch_id"],
        "claim_path": claim["path"], "claim_sha256": claim["sha256"],
        "manifest_path": document["manifest_path"],
        "manifest_sha256": document["manifest_sha256"],
        "claim_token": token,
    }


def _bound_claim(root, prepared):
    slot = resolve_daily_slot(source="cli", cycle_date=prepared["cycle_date"])
    claim = inspect_slot(root=root, slot=slot)
    if claim["state"] != "claimed":
        raise SlotControlError("Slot sem propriedade confirmada.")
    expected = _metadata(claim)
    for key in expected.keys() - {"claim_token"}:
        if prepared.get(key) != expected[key]:
            raise SlotControlError("Referência diária divergente.")
    manifest = load_verified_manifest(
        project_root=root, manifest_path=expected["manifest_path"],
        manifest_sha256=expected["manifest_sha256"],
    )
    doc = claim["document"]
    if (manifest["batch_id"] != doc["batch_id"]
            or manifest["cycle_date_local"] != doc["cycle_date"]
            or manifest["orchestration_context"].get("scheduled_slot") != utc_text(slot.scheduled_slot)
            or {k: v["run_id"] for k, v in manifest["runs"].items()} != doc["run_ids"]
            or _fingerprint(manifest["config"], manifest["locations"]) != doc["input_sha256"]):
        raise SlotControlError("Manifesto divergente da reserva.")
    return slot, claim, manifest


def _completed(root, prepared, manifest):
    """Somente leitura; nunca chamar o coletor para verificar conclusão."""
    from scripts.weather_interface import verify_batch_artifacts
    slot = resolve_daily_slot(source="cli", cycle_date=prepared["cycle_date"])
    dispatch, _ = _read(root, prepared["claim_path"].removesuffix("claim.json") + "dispatch.json")
    if (set(dispatch) != {"schema_version", "slot_sha256", "claim_sha256", "manifest_sha256",
                         "batch_id", "dispatch_id", "dispatched_at"}
            or dispatch["schema_version"] != "1"
            or dispatch["slot_sha256"] != hashlib.sha256(canonical_slot_bytes(slot)).hexdigest()
            or dispatch["claim_sha256"] != prepared["claim_sha256"]
            or dispatch["manifest_sha256"] != prepared["manifest_sha256"]
            or dispatch["batch_id"] != manifest["batch_id"]
            or str(UUID(dispatch["dispatch_id"])) != dispatch["dispatch_id"]
            or not evaluate_admission(slot, parse_instant(dispatch["dispatched_at"]))["eligible"]):
        raise SlotControlError("Dispatch não comprovado.")
    base = f"data/orchestration/executions/{manifest['batch_id']}"
    started_bytes = resolve_reference(root, f"{base}/started.json").read_bytes()
    started = json.loads(started_bytes)
    if (started["batch_id"] != manifest["batch_id"]
            or started["manifest_sha256"] != prepared["manifest_sha256"]):
        raise SlotControlError("Início divergente.")
    verified = verify_batch_artifacts(project_root=root, manifest=manifest)
    completed, _ = _read(root, f"{base}/completed.json")
    if completed != {
        "batch_id": manifest["batch_id"],
        "manifest_sha256": prepared["manifest_sha256"],
        "claim_sha256": hashlib.sha256(started_bytes).hexdigest(),
        "result": verified,
    }:
        raise SlotControlError("Conclusão divergente.")
    return verified


def _replay(root, claim):
    prepared = _metadata(claim)
    _, _, manifest = _bound_claim(root, prepared)
    _completed(root, prepared, manifest)
    return prepared


def prepare_daily_extraction(*, config, locations, project_root, source="cli",
                             cycle_date=None, orchestration_context=None,
                             data_interval_start=None, data_interval_end=None,
                             clock=utc_now):
    slot = resolve_daily_slot(source=source, cycle_date=cycle_date,
                              data_interval_start=data_interval_start,
                              data_interval_end=data_interval_end)
    context = dict(orchestration_context or {})
    context["scheduled_slot"] = utc_text(slot.scheduled_slot)
    ids = [location["location_id"] for location in locations]
    if len(ids) != 5 or set(ids) != LOCATION_IDS:
        raise ValueError("Exatamente cinco localidades aprovadas são exigidas.")
    fingerprint = _fingerprint(config, locations)
    existing = inspect_slot(root=project_root, slot=slot)
    if existing["state"] != "absent":
        if existing["document"]["input_sha256"] != fingerprint:
            raise SlotControlError("Configuração conflitante; reserva preservada.")
        return _replay(project_root, existing)
    admitted = evaluate_admission(slot, clock())
    if not admitted["eligible"]:
        raise DailyAdmissionError(admitted)
    batch_id = str(uuid4())
    run_ids = {key: str(uuid4()) for key in ids}
    if source == "cli":
        if set(context) != {"scheduled_slot"}:
            raise ValueError("CLI não aceita contexto Airflow.")
        owner = {"source": source, "invocation_id": str(uuid4())}
        path = f"data/orchestration/batches/{batch_id}/manifest.json"
    else:
        owner = {"source": source, "dag_id": context.get("dag_id"),
                 "airflow_run_id": context.get("airflow_run_id")}
        key = _digest({"dag_id": owner["dag_id"],
                       "airflow_run_id": owner["airflow_run_id"]})
        path = f"data/orchestration/contexts/{key}/manifest.json"
        if resolve_reference(project_root, path).exists():
            raise SlotControlError("Contexto histórico existente; não reassociar.")
    manifest = build_manifest_document(
        cycle_date=slot.cycle_date, config=config, locations=locations,
        batch_id=batch_id, run_ids=run_ids, orchestration_context=context,
    )
    identity = canonical_slot_bytes(slot)
    candidate = {
        "schema_version": "1", "policy_version": POLICY_VERSION,
        "slot": json.loads(identity), "slot_sha256": hashlib.sha256(identity).hexdigest(),
        "cycle_date": slot.cycle_date.isoformat(), "owner": owner,
        "claim_token": str(uuid4()), "batch_id": batch_id, "run_ids": run_ids,
        "input_sha256": fingerprint, "claimed_at": admitted["observed_at"],
        "manifest_path": path, "manifest_sha256": _digest(manifest),
    }
    claim = acquire_slot(root=project_root, candidate=candidate)
    if not claim["created"]:
        if claim["state"] == "conflict":
            raise SlotControlError("Conflito na aquisição.")
        return _replay(project_root, claim)
    persist_immutable_document(project_root, path, manifest)
    return _metadata(claim, token=candidate["claim_token"])


def execute_daily_extraction(*, prepared, project_root, clock=utc_now):
    from scripts.weather_interface import execute_extraction
    slot, claim, manifest = _bound_claim(project_root, prepared)
    completion = f"data/orchestration/executions/{manifest['batch_id']}/completed.json"
    if resolve_reference(project_root, completion).exists():
        result = _completed(project_root, prepared, manifest)
        return {**_metadata(claim), "batch_status": result["batch_status"], "mode": "replay"}
    if prepared.get("claim_token") != claim["document"]["claim_token"]:
        raise SlotControlError("Somente o fluxo proprietário pode iniciar.")
    try:
        claim_dispatch(root=project_root,
            claim_reference={"path": claim["path"], "sha256": claim["sha256"]},
            manifest_reference={"path": prepared["manifest_path"], "sha256": prepared["manifest_sha256"]},
            dispatch_id=str(uuid4()), now=clock())
        guard = FirstTransportGuard(slot, clock)
        result = execute_extraction(
            manifest_path=prepared["manifest_path"], manifest_sha256=prepared["manifest_sha256"],
            project_root=project_root, before_first_transport=guard)
    except DailyAdmissionError as error:
        persist_immutable_document(project_root,
            claim["path"].removesuffix("claim.json") + f"events/{uuid4()}.json", {
                "schema_version": "1", "claim_sha256": claim["sha256"],
                "batch_id": prepared["batch_id"], "category": "transport_admission_rejected",
                "decision": error.decision,
            })
        raise
    return {**_metadata(claim), "batch_status": result["batch_status"], "mode": result["mode"]}


def _quality(root, manifest):
    from scripts.extract_weather import parse_forecast_times
    from scripts.weather_window import build_cycle_window
    slot = resolve_daily_slot(source="cli", cycle_date=manifest["cycle_date_local"])
    reasons, collected = set(), {}
    if {loc["location_id"] for loc in manifest["locations"]} != LOCATION_IDS:
        reasons.add("incomplete_locations")
    for loc in manifest["locations"]:
        city = loc["location_id"]
        run = manifest["runs"][city]["run_id"]
        report = json.loads(resolve_reference(root, f"data/raw/runs/{run}.json").read_bytes())
        collected[city] = report.get("collected_at")
        if report["run_status"] != "validated":
            reasons.add("quality_rejected")
            continue
        payload = json.loads(resolve_reference(root, report["raw_path"]).read_bytes())
        expected = build_cycle_window(slot.cycle_date, loc["timezone"])["expected_times_utc"]
        if list(parse_forecast_times(payload)) != list(expected):
            reasons.add("incomplete_window")
        if any(report["validation"]["null_counts"].values()):
            reasons.add("null_values")
    return sorted(reasons), collected


def reconcile_daily_extraction(*, prepared, project_root, clock=utc_now):
    """Reconcilia sem HTTP; reserva exclusiva impede retomar avaliação ambígua."""
    from scripts.weather_slots import _publish_exclusive
    slot, claim, manifest = _bound_claim(project_root, prepared)
    verified = _completed(project_root, prepared, manifest)
    base = claim["path"].removesuffix("claim.json")
    readiness_path = base + "readiness.json"
    if resolve_reference(project_root, readiness_path).exists():
        return _evaluate_now(project_root, slot, clock())
    if prepared.get("mode") == "replay":
        return {"eligible": False, "reasons": ["readiness_unproven"], "batch_id": manifest["batch_id"]}
    if not _publish_exclusive(project_root, base + "assessment-started.json", {
        "schema_version": "1", "claim_sha256": claim["sha256"],
        "token": str(uuid4()), "started_at": utc_text(clock()),
    }):
        raise SlotControlError("Avaliação interrompida; prontidão não comprovada.")
    reasons, collected = _quality(project_root, manifest)
    assessed = aware_utc(clock())
    assessment = {
        "schema_version": "1", "policy_version": POLICY_VERSION,
        "claim_sha256": claim["sha256"], "batch_id": manifest["batch_id"],
        "manifest_sha256": prepared["manifest_sha256"], "verified": verified,
        "assessed_at": utc_text(assessed), "quality_reasons": reasons,
        "collected_at_by_city": collected,
    }
    reference = persist_immutable_document(project_root, base + "assessment.json", assessment)
    observed = aware_utc(clock())
    if observed < assessed:
        raise SlotControlError("Relógio regressivo; prontidão não comprovada.")
    readiness_reference = persist_immutable_document(project_root, readiness_path, {
        "schema_version": "1", "assessment": reference,
        "assessment_persisted_observed_at": utc_text(observed),
        "on_time": observed <= slot.readiness_cutoff,
    })
    # A persistência deste segundo recibo também deve concluir dentro do prazo.
    confirmed = aware_utc(clock())
    if confirmed < observed or confirmed > slot.readiness_cutoff:
        raise SlotControlError("Recibo concluído fora do prazo; prontidão não comprovada.")
    # Testemunho da observação POSTERIOR à persistência do recibo. Não é
    # reconstruído em replay. Sua ausência (inclusive crash aqui) bloqueia.
    persist_immutable_document(project_root, base + "readiness-confirmed.json", {
        "schema_version": "1", "claim_sha256": claim["sha256"],
        "readiness": readiness_reference, "confirmed_at": utc_text(confirmed),
    })
    evaluated = aware_utc(clock())
    if evaluated < confirmed:
        raise SlotControlError("Relógio regressivo na disponibilização.")
    return _evaluate_now(project_root, slot, evaluated)


def _evaluate_now(root, slot, observed_at):
    observed = aware_utc(observed_at)
    result = evaluate_for_consumption(project_root=root, cycle_date=slot.cycle_date,
                                     consumed_at=max(observed, slot.intended_consumption))
    return {**result, "evaluated_at": utc_text(observed),
            "provisional": observed < slot.intended_consumption}


def evaluate_for_consumption(*, project_root, cycle_date, consumed_at):
    """Consulta conservadora sem coleta/fallback ou escrita de artefatos."""
    slot = resolve_daily_slot(source="cli", cycle_date=cycle_date)
    consumed = aware_utc(consumed_at)
    try:
        claim = inspect_slot(root=project_root, slot=slot)
        if claim["state"] == "absent":
            return {"eligible": False, "reasons": ["unavailable"]}
        prepared = _metadata(claim)
        _, _, manifest = _bound_claim(project_root, prepared)
        verified = _completed(project_root, prepared, manifest)
        base = claim["path"].removesuffix("claim.json")
        assessment, digest = _read(project_root, base + "assessment.json")
        readiness, readiness_digest = _read(project_root, base + "readiness.json")
        confirmation, _ = _read(project_root, base + "readiness-confirmed.json")
        if (set(assessment) != {"schema_version", "policy_version", "claim_sha256", "batch_id",
                "manifest_sha256", "verified", "assessed_at", "quality_reasons", "collected_at_by_city"}
                or assessment["schema_version"] != "1"
                or set(readiness) != {"schema_version", "assessment", "assessment_persisted_observed_at", "on_time"}
                or readiness["schema_version"] != "1" or type(readiness["on_time"]) is not bool):
            raise SlotControlError("Schema operacional inválido.")
        reasons, collected = _quality(project_root, manifest)
        if (assessment["claim_sha256"] != claim["sha256"]
                or assessment["policy_version"] != POLICY_VERSION
                or assessment["batch_id"] != manifest["batch_id"]
                or assessment["manifest_sha256"] != prepared["manifest_sha256"]
                or assessment["verified"] != verified
                or assessment["quality_reasons"] != reasons
                or assessment["collected_at_by_city"] != collected
                or readiness["assessment"] != {"path": base + "assessment.json", "sha256": digest}
                or set(confirmation) != {"schema_version", "claim_sha256", "readiness", "confirmed_at"}
                or confirmation["schema_version"] != "1"
                or confirmation["claim_sha256"] != claim["sha256"]
                or confirmation["readiness"] != {
                    "path": base + "readiness.json", "sha256": readiness_digest}):
            raise SlotControlError("Recibo divergente.")
        observed = parse_instant(readiness["assessment_persisted_observed_at"])
        confirmed = parse_instant(confirmation["confirmed_at"])
        if any(value is not None and parse_instant(value) > parse_instant(assessment["assessed_at"])
               for value in collected.values()):
            reasons.append("collection_after_assessment")
        if (not readiness["on_time"] or observed > slot.readiness_cutoff
                or observed < parse_instant(assessment["assessed_at"])
                or confirmed < observed or confirmed > slot.readiness_cutoff):
            reasons.append("late_readiness")
        freshness = evaluate_freshness(collected, consumed)
        reasons.extend(freshness["reasons"])
        if consumed < slot.intended_consumption:
            reasons.append("before_consumption")
        return {"eligible": not reasons, "reasons": sorted(set(reasons)),
                "batch_id": manifest["batch_id"], "batch_status": verified["batch_status"],
                "freshness": freshness}
    except (ValueError, OSError, KeyError, TypeError):
        return {"eligible": False, "reasons": ["integrity_or_readiness_unproven"]}
