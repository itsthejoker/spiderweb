import asyncio
import signal
import threading
import time
from logging import Logger
from threading import Thread
from typing import NoReturn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler

from spiderweb.constants import __version__
from spiderweb.exceptions import ConfigError


class SpiderwebRequestHandler(WSGIRequestHandler):
    server_version = "spiderweb/" + __version__

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class LocalServerMixin:
    """Cannot be called on its own. Requires context of SpiderwebRouter."""

    addr: str
    port: int
    log: Logger
    _server: WSGIServer
    _thread: Thread

    def create_server(self):
        server = WSGIServer((self.addr, self.port), SpiderwebRequestHandler)
        server.set_app(self)
        return server

    def signal_handler(self, sig, frame) -> NoReturn:
        self.log.warning("Shutting down!")
        self.stop()

    def start(self, blocking=False):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.log.info(f"Starting server on http://{self.addr}:{self.port}")
        self.log.info("Press CTRL+C to stop the server.")
        self._server = self.create_server()
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.start()

        if not blocking:
            return self._thread
        else:
            while self._thread.is_alive():
                try:
                    time.sleep(0.2)
                except KeyboardInterrupt:
                    self.stop()

    def stop(self):
        self._server.shutdown()
        self._server.socket.close()

    def start_asgi(self, blocking=True):
        try:
            import uvicorn
        except ImportError:
            raise ConfigError(
                "uvicorn is required for ASGI mode. "
                "Install it with: pip install spiderweb-framework[asgi]"
            )
        self.log.info(f"Starting ASGI server on http://{self.addr}:{self.port}")
        self.log.info("Press CTRL+C to stop the server.")
        # Do NOT call signal.signal() here: uvicorn installs its own SIGINT/SIGTERM
        # handlers and would immediately overwrite ours. Shutdown hooks should be
        # registered via on_shutdown= callbacks instead.
        #
        # NOTE: asyncio.run() raises RuntimeError if an event loop is already running
        # (e.g. inside pytest-asyncio tests or Jupyter). In those environments, call
        # app.asgi_app directly with an external ASGI server instead of start_asgi().
        config = uvicorn.Config(self.asgi_app, host=self.addr, port=self.port)
        server = uvicorn.Server(config)
        if blocking:
            # Blocks the calling thread until the server exits (mirrors start(blocking=True))
            asyncio.run(server.serve())
        else:
            # Run the server in a background thread and return immediately
            # (mirrors the threading behaviour of start(blocking=False))
            t = threading.Thread(
                target=asyncio.run, args=(server.serve(),), daemon=True
            )
            t.start()
            return t
