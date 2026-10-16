import json
from copy import deepcopy

import pytest
import requests

ORIGINAL_SESSION_REQUEST = requests.sessions.Session.request

from scripts.weather_interface import build_execution_config


ENDPOINT = "https://api.open-meteo.com/v1/forecast"


def test_timeout_json_roundtrip_preserves_manifest():
    original = {
        "endpoint": ENDPOINT,
        "timeout": (10, 30),
    }

    serialized = json.dumps(original)
    restored = json.loads(serialized)
    snapshot = deepcopy(restored)

    execution_config = build_execution_config(restored)

    assert type(restored["timeout"]) is list
    assert type(execution_config["timeout"]) is tuple
    assert execution_config["timeout"] == (10, 30)
    assert execution_config["endpoint"] == ENDPOINT

    assert restored == snapshot
    assert execution_config is not restored
    assert json.dumps(restored) == serialized


@pytest.mark.parametrize(
    "timeout",
    [
        None,
        "10,30",
        [],
        [10],
        [10, 30, 60],
        [True, 30],
        ["10", 30],
        [0, 30],
        [-10, 30],
        [float("nan"), 30],
        [10, float("inf")],
        [5, 30],
    ],
)
def test_invalid_timeout_is_rejected(timeout):
    config = {
        "endpoint": ENDPOINT,
        "timeout": timeout,
    }

    with pytest.raises(ValueError):
        build_execution_config(config)

@pytest.mark.parametrize("restore_timeout", [False, True])
def test_timeout_reaches_real_requests_adapter(
    monkeypatch,
    restore_timeout,
):
    import io
    import socket

    import requests
    from urllib3.connectionpool import HTTPSConnectionPool
    from urllib3.response import HTTPResponse
    from urllib3.util import Timeout

    transport_calls = []

    def block_network(*args, **kwargs):
        raise AssertionError("Conexão de rede proibida neste teste.")

    def fake_urlopen(self, method, url, **kwargs):
        timeout = kwargs["timeout"]

        assert isinstance(timeout, Timeout)
        assert timeout.connect_timeout == 10
        assert timeout.read_timeout == 30

        transport_calls.append((method, url))

        return HTTPResponse(
            body=io.BytesIO(b'{"test": "ok"}'),
            status=200,
            headers={"Content-Type": "application/json"},
            preload_content=False,
        )

    monkeypatch.setattr(socket.socket, "connect", block_network)
    monkeypatch.setattr(socket.socket, "connect_ex", block_network)
    monkeypatch.setattr(socket, "create_connection", block_network)
    monkeypatch.setattr(HTTPSConnectionPool, "urlopen", fake_urlopen)

    manifest_config = json.loads(
        json.dumps({
            "endpoint": ENDPOINT,
            "timeout": (10, 30),
        })
    )

    config = (
        build_execution_config(manifest_config)
        if restore_timeout
        else manifest_config
    )

    prepared = requests.Request("GET", ENDPOINT).prepare()

    with requests.Session() as session:
        session.trust_env = False

        if restore_timeout:
            response = session.send(
                prepared,
                timeout=config["timeout"],
            )

            assert response.status_code == 200
            assert response.json() == {"test": "ok"}
            assert len(transport_calls) == 1
            response.close()
        else:
            with pytest.raises(ValueError, match="Timeout"):
                session.send(
                    prepared,
                    timeout=config["timeout"],
                )

            assert transport_calls == []

    assert manifest_config["timeout"] == [10, 30]

def test_manifest_execution_uses_real_requests_without_network(
    monkeypatch,
    tmp_path,
    config,
    locations,
    cycle_date,
    payload_factory,
    fixed_clock,
):
    import hashlib
    import io
    import socket
    from urllib.parse import parse_qs, urlsplit

    from urllib3.connectionpool import HTTPSConnectionPool
    from urllib3.response import HTTPResponse

    import scripts.weather_interface as interface

    reference = interface.prepare_extraction(
        cycle_date=cycle_date,
        config=config,
        locations=locations,
        project_root=tmp_path,
    )

    manifest_path = tmp_path / reference["manifest_path"]
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)

    assert manifest["config"]["timeout"] == [10, 30]

    by_coordinates = {
        (location["latitude"], location["longitude"]): location
        for location in locations
    }
    transport_calls = []

    def block_network(*args, **kwargs):
        raise AssertionError("Conexão de rede proibida neste teste.")

    def fake_urlopen(self, method, url, **kwargs):
        timeout = kwargs["timeout"]
        assert timeout.connect_timeout == 10
        assert timeout.read_timeout == 30

        query = parse_qs(urlsplit(url).query)
        coordinates = (
            float(query["latitude"][0]),
            float(query["longitude"][0]),
        )
        location = by_coordinates[coordinates]

        transport_calls.append(location["location_id"])

        body = json.dumps(
            payload_factory(location)
        ).encode("utf-8")

        return HTTPResponse(
            body=io.BytesIO(body),
            status=200,
            headers={"Content-Type": "application/json"},
            preload_content=False,
        )

    arguments = {
        "project_root": tmp_path,
        "manifest_path": reference["manifest_path"],
        "manifest_sha256": reference["manifest_sha256"],
    }

    with monkeypatch.context() as patch:
        patch.setattr(socket.socket, "connect", block_network)
        patch.setattr(socket.socket, "connect_ex", block_network)
        patch.setattr(socket, "create_connection", block_network)
        patch.setattr(HTTPSConnectionPool, "urlopen", fake_urlopen)
        patch.setattr(
            requests.sessions.Session,
            "request",
            ORIGINAL_SESSION_REQUEST,
        )

        result = interface.execute_extraction(**arguments)

    assert result["mode"] == "new_collection"
    assert result["batch_status"] == "success"
    assert result["batch_id"] == reference["batch_id"]
    assert result["record_count"] == 160
    assert transport_calls == [
        location["location_id"] for location in locations
    ]

    assert manifest_path.read_bytes() == manifest_bytes
    assert hashlib.sha256(manifest_bytes).hexdigest() == (
        reference["manifest_sha256"]
    )

    before_replay = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    # O bloqueio HTTP original da fixture já está novamente ativo.
    replay = interface.execute_extraction(**arguments)

    assert replay["mode"] == "replay"
    assert replay["batch_id"] == reference["batch_id"]
    assert replay["record_count"] == 160

    after_replay = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after_replay == before_replay