import ast
import builtins
import importlib
import io
from pathlib import Path

import pytest
import requests
import dotenv


MODULES = [
    "scripts.extract_weather",
    "scripts.weather_window",
    "scripts.weather_manifest",
    "scripts.weather_interface",
    "scripts.weather_temporal",
    "scripts.weather_slots",
    "scripts.weather_daily",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_module_top_level_has_no_project_io(monkeypatch, module_name):
    # Carregar dependências e ler/compilar o código antes do bloqueio.
    module = importlib.import_module(module_name)
    path = Path(module.__file__)
    source = path.read_text(encoding="utf-8-sig")
    code = compile(source, str(path), "exec")

    def forbidden(*args, **kwargs):
        raise AssertionError("I/O autoral durante import")

    namespace = {
        "__name__": f"{module_name}_import_probe",
        "__file__": str(path),
        "__package__": "scripts",
    }

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(io, "open", forbidden)
        patch.setattr(dotenv, "load_dotenv", forbidden)
        patch.setattr(requests, "get", forbidden)
        patch.setattr(requests.sessions.Session, "request", forbidden)

        for method in (
            "open",
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "mkdir",
            "resolve",
            "stat",
            "exists",
            "is_file",
            "is_dir",
        ):
            patch.setattr(Path, method, forbidden)

        exec(code, namespace)

    assert callable(namespace.get(
        {
            "scripts.extract_weather": "main",
            "scripts.weather_window": "build_cycle_window",
            "scripts.weather_manifest": "build_manifest_document",
            "scripts.weather_interface": "execute_extraction",
            "scripts.weather_temporal": "resolve_daily_slot",
            "scripts.weather_slots": "acquire_slot",
            "scripts.weather_daily": "prepare_daily_extraction",
        }[module_name]
    ))


@pytest.mark.parametrize("module_name", MODULES)
def test_project_modules_do_not_import_airflow(module_name):
    module = importlib.import_module(module_name)
    source = Path(module.__file__).read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue

        assert not any(
            name == "airflow" or name.startswith("airflow.")
            for name in names
        )