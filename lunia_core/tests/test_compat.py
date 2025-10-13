from importlib import reload
from types import ModuleType

import builtins
import sys


def _force_module_reload(module_name: str) -> ModuleType:
    sys.modules.pop(module_name, None)
    module = __import__(module_name, fromlist=["*"])
    return reload(module)


def test_prometheus_shim_exposes_expected_attributes(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "prometheus_client":
            raise ImportError("simulated missing dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    prom = _force_module_reload("app.compat.prom")
    assert hasattr(prom, "Counter")
    counter = prom.Counter("test", "desc")
    assert hasattr(counter, "labels")
    assert counter.labels() is counter
    counter.inc()
    counter.observe(0)


def test_dotenv_shim_load_dotenv_callable(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "dotenv":
            raise ImportError("simulated missing dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    dotenv = _force_module_reload("app.compat.dotenv")
    assert callable(dotenv.load_dotenv)
    assert dotenv.load_dotenv() is None


def test_requests_shim(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "requests":
            raise ImportError("simulated missing dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    requests_mod = _force_module_reload("app.compat.requests")
    assert isinstance(requests_mod, ModuleType)
    session = requests_mod.requests
    assert hasattr(session, "get")
    resp = session.get("http://example.com")
    assert hasattr(resp, "status_code")
