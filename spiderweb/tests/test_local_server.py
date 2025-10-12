import signal
import threading
import time

from hypothesis import given, strategies as st

from spiderweb.local_server import LocalServerMixin


class _FakeSocket:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeServer:
    def __init__(self):
        self.shutdown_called = False
        self.socket = _FakeSocket()
        self._run_count = 0

    def set_app(self, app):
        self.app = app

    def serve_forever(self):
        # Simulate a small bit of work and then return
        self._run_count += 1
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


class DummyApp(LocalServerMixin):
    def __init__(self, addr: str, port: int):
        self.addr = addr
        self.port = port
        self.log = _ListLogger()

    def __call__(self, environ, start_response):  # pragma: no cover - not used
        pass

    def create_server(self):
        # override to avoid binding a real socket
        srv = _FakeServer()
        srv.set_app(self)
        return srv

    def stop(self):  # wrap to expose call through to mixin.stop for verification
        # call parent stop to hit code paths under test
        super().stop()


@given(
    addr=st.ip_addresses().map(str), port=st.integers(min_value=1025, max_value=65535)
)
def test_start_non_blocking_and_stop_calls_shutdown_and_close(addr, port):
    app = DummyApp(addr, port)
    thread = app.start(blocking=False)
    # Should return a Thread and set internal state
    assert isinstance(thread, threading.Thread)
    assert hasattr(app, "_server") and hasattr(app, "_thread")

    # Stop should call shutdown and close socket
    app.stop()
    assert isinstance(app._server, _FakeServer)
    assert app._server.shutdown_called is True
    assert app._server.socket.closed is True


def test_signal_handler_logs_warning_and_stops(monkeypatch):
    app = DummyApp("127.0.0.1", 0)
    # track stop calls
    called = {"stop": 0}

    def _stop():
        called["stop"] += 1

    monkeypatch.setattr(app, "stop", _stop)
    app.signal_handler(signal.SIGINT, None)
    # one warning and one stop recorded
    assert any(
        level == "warning" and "Shutting down!" in msg for level, msg in app.log.records
    )
    assert called["stop"] == 1
