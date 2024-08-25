import signal
import threading
import time
from logging import Logger
from threading import Thread
from typing import NoReturn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler

from spiderweb.constants import __version__


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
        self.log.info(f"Starting server on {self.addr}:{self.port}")
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
