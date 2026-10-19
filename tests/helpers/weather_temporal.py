"""Fixtures sintéticas de C1; trabalhadores somente chamados pelos testes."""

import hashlib
import json
from datetime import date, datetime, timezone
from uuid import uuid4

from scripts.weather_manifest import build_manifest_document, encode_document
from scripts.weather_slots import canonical_slot_bytes
from scripts.weather_temporal import POLICY_VERSION, resolve_daily_slot, utc_text


def make_claim(locations, *, day=date(2026, 10, 13), source="cli"):
    slot = resolve_daily_slot(source="cli", cycle_date=day)
    batch_id = str(uuid4())
    run_ids = {location["location_id"]: str(uuid4()) for location in locations}
    config = {"endpoint": "https://api.open-meteo.com/v1/forecast", "timeout": (10, 30)}
    if source == "cli":
        owner = {"source": "cli", "invocation_id": str(uuid4())}
        context = {"scheduled_slot": utc_text(slot.scheduled_slot)}
        path = f"data/orchestration/batches/{batch_id}/manifest.json"
    else:
        owner = {
            "source": source, "dag_id": "logistics_weather_extract",
            "airflow_run_id": f"{source}__{uuid4()}",
        }
        context = {
            "dag_id": owner["dag_id"], "airflow_run_id": owner["airflow_run_id"],
            "scheduled_slot": utc_text(slot.scheduled_slot),
        }
        key = hashlib.sha256(encode_document({
            "dag_id": owner["dag_id"], "airflow_run_id": owner["airflow_run_id"],
        })).hexdigest()
        path = f"data/orchestration/contexts/{key}/manifest.json"
    manifest = build_manifest_document(
        cycle_date=day, config=config, locations=locations, batch_id=batch_id,
        run_ids=run_ids, orchestration_context=context,
    )
    identity = canonical_slot_bytes(slot)
    fingerprint = hashlib.sha256(encode_document({
        "config": config, "locations": locations, "policy_version": POLICY_VERSION,
    })).hexdigest()
    return slot, {
        "schema_version": "1", "slot": json.loads(identity),
        "slot_sha256": hashlib.sha256(identity).hexdigest(),
        "cycle_date": day.isoformat(), "policy_version": POLICY_VERSION,
        "owner": owner, "claim_token": str(uuid4()), "batch_id": batch_id,
        "run_ids": run_ids, "input_sha256": fingerprint,
        "claimed_at": utc_text(slot.scheduled_slot), "manifest_path": path,
        "manifest_sha256": hashlib.sha256(encode_document(manifest)).hexdigest(),
    }, manifest


class SequenceClock:
    def __init__(self, *instants):
        self.instants = iter(instants)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return next(self.instants)


def local_time(hour, minute=0, second=0, microsecond=0):
    from zoneinfo import ZoneInfo
    return datetime(2026, 10, 13, hour, minute, second, microsecond,
                    tzinfo=ZoneInfo("America/Sao_Paulo")).astimezone(timezone.utc)


def claim_worker(root, candidate, pipe, interrupt_after_link=False):
    """Processo descartável com barreiras próprias; nunca toca dados reais."""
    from unittest.mock import patch
    import scripts.weather_slots as slots
    from helpers.weather_resilience import blocked_external_network, restricted_writes

    with restricted_writes(root), blocked_external_network():
        pipe.send({"event": "ready"})
        if pipe.recv() != "go":
            raise AssertionError("Protocolo de teste inválido.")
        if interrupt_after_link:
            original_link = slots.os.link

            def signal_after_link(*args, **kwargs):
                result = original_link(*args, **kwargs)
                pipe.send({"event": "linked"})
                pipe.recv()  # O controlador encerra somente este filho.
                raise AssertionError("Interrupção esperada não ocorreu.")

            with patch.object(slots.os, "link", signal_after_link):
                slots.acquire_slot(root=root, candidate=candidate)
        else:
            result = slots.acquire_slot(root=root, candidate=candidate)
            pipe.send({"event": "result", "created": result["created"],
                       "batch_id": result["document"]["batch_id"]})
    pipe.close()


def daily_worker(root, config, locations, payloads, pipe):
    """Produtor em processo spawn com transporte sintético e barreiras próprias."""
    from unittest.mock import patch
    import requests
    import scripts.extract_weather as extractor
    from scripts.weather_daily import prepare_daily_extraction, execute_daily_extraction
    from helpers.weather_resilience import blocked_external_network, restricted_writes
    calls = []
    by_coord = {(loc["latitude"], loc["longitude"]): loc["location_id"] for loc in locations}

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return local_time(14).astimezone(tz)

    def transport(endpoint, *, params, timeout):
        city = by_coord[(params["latitude"], params["longitude"])]
        calls.append(city)
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payloads[city]).encode()
        return response

    with restricted_writes(root), blocked_external_network(), \
            patch.object(requests, "get", transport), patch.object(extractor, "datetime", FixedClock):
        pipe.send({"event": "ready"})
        assert pipe.recv() == "go"
        try:
            prepared = prepare_daily_extraction(project_root=root, config=config, locations=locations,
                cycle_date=date(2026, 10, 13), clock=lambda: local_time(13, 45))
            result = execute_daily_extraction(project_root=root, prepared=prepared,
                                              clock=lambda: local_time(14))
            state = result["mode"]
        except (ValueError, OSError):
            state = "blocked"
        pipe.send({"event": "result", "state": state, "calls": len(calls)})
    pipe.close()
