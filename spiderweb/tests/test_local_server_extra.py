"""Extra coverage tests for spiderweb/local_server.py."""

import sys
import threading
import time
from unittest.mock import patch

import pytest

from spiderweb.exceptions import ConfigError
from spiderweb.local_server import LocalServerMixin, SpiderwebRequestHandler
from spiderweb.constants import __version__

# ---------------------------------------------------------------------------
# Helpers (mirrors test_local_server.py style)
# ---------------------------------------------------------------------------


class _FakeSocket:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeServer:
    def __init__(self):
        self.shutdown_called = False
        self.socket = _FakeSocket()
        self._serve_count = 0

    def set_app(self, app):
        self.app = app

    def serve_forever(self):
        self._serve_count += 1
        time.sleep(0.01)

    def shutdown(self):
        self.shutdown_called = True


class _ListLogger:
    def __init__(self):
        self.records = []

    def info(self, msg):
        self.records.append(("info", str(msg)))

    def warning(self, msg):
        self.records.append(("warning", str(msg)))


class _DummyApp(LocalServerMixin):
    def __init__(self, addr="127.0.0.1", port=8888):
        self.addr = addr
        self.port = port
        self.log = _ListLogger()

    def __call__(self, environ, start_response):  # pragma: no cover
        pass

    def create_server(self):
        srv = _FakeServer()
        srv.set_app(self)
        return srv


# ---------------------------------------------------------------------------
# SpiderwebRequestHandler server_version
# ---------------------------------------------------------------------------


def test_request_handler_version_string():
    assert SpiderwebRequestHandler.server_version == f"spiderweb/{__version__}"


# ---------------------------------------------------------------------------
# create_server (real path, not overridden)
# ---------------------------------------------------------------------------


def test_create_server_returns_server_with_app_set():
    """create_server binds the app to the server and returns it."""
    app = _DummyApp()
    srv = _DummyApp.create_server(app)
    # Fake server was created with the app set
    assert srv.app is app


# ---------------------------------------------------------------------------
# start_asgi: missing uvicorn raises ConfigError (lines 61-67)
# ---------------------------------------------------------------------------


def test_start_asgi_without_uvicorn_raises_config_error(monkeypatch):
    """start_asgi() raises ConfigError when uvicorn is not installed."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "uvicorn":
            raise ImportError("No module named 'uvicorn'")
        return real_import(name, *args, **kwargs)

    app = _DummyApp()
    # Provide asgi_app attribute so the method can reference it
    app.asgi_app = None

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ConfigError):
        app.start_asgi()


# ---------------------------------------------------------------------------
# start_asgi: non-blocking mode returns a Thread (lines 84-87)
# ---------------------------------------------------------------------------


def test_start_asgi_non_blocking_returns_thread():
    """start_asgi(blocking=False) starts uvicorn in a daemon thread."""
    app = _DummyApp()

    # Create a minimal fake uvicorn module
    class _FakeConfig:
        def __init__(self, asgi_app, host, port):
            pass

    class _FakeServer:
        def __init__(self, config):
            pass

        async def serve(self):
            # Simulate work then exit
            import asyncio

            await asyncio.sleep(0.01)

    class _FakeUvicorn:
        Config = _FakeConfig
        Server = _FakeServer

    app.asgi_app = object()  # just needs to exist

    with patch.dict(sys.modules, {"uvicorn": _FakeUvicorn()}):
        t = app.start_asgi(blocking=False)

    assert isinstance(t, threading.Thread)
    assert t.daemon is True
    # Let the thread finish so we don't leave dangling threads
    t.join(timeout=2)
