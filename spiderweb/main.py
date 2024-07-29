# very simple RPC server in python
# Originally from https://gist.github.com/earonesty/ab07b4c0fea2c226e75b3d538cc0dc55
# Extensively modified by @itsthejoker

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse as urlparse
import threading
import logging
from typing import Callable, Any

from spiderweb.converters import *  # noqa: F403
from spiderweb.exceptions import APIError, ConfigError, ParseError, GeneralException

log = logging.getLogger(__name__)


def api_route(path):
    def outer(func):
        if not hasattr(func, "_routes"):
            setattr(func, "_routes", [])
        func._routes += [path]
        return func

    return outer


def convert_path(path):
    """Convert a path to a regex."""
    parts = path.split("/")
    for i, part in enumerate(parts):
        if part.startswith("<") and part.endswith(">"):
            name = part[1:-1]
            if "__" in name:
                raise ConfigError(
                    f"Cannot use `__` (double underscore) in path variable."
                    f" Please fix '{name}'."
                )
            if ":" in name:
                converter, name = name.split(":")
                try:
                    converter = globals()[converter.title() + "Converter"]
                except KeyError:
                    raise ParseError(f"Unknown converter {converter}")
            else:
                converter = StrConverter  # noqa: F405
            parts[i] = r"(?P<%s>%s)" % (
                f"{name}__{str(converter.__name__)}",
                converter.regex,
            )
    return re.compile(r"^%s$" % "/".join(parts))


def convert_match_to_dict(match: dict):
    """Convert a match object to a dict with the proper converted types for each match."""
    return {
        k.split("__")[0]: globals()[k.split("__")[1]]().to_python(v)
        for k, v in match.items()
    }


class APIServer(HTTPServer):
    def __init__(self, addr: str, port: int, custom_handler: Callable = None):
        """
        Create a new server on address, port. Port can be zero.

        > from simple_rpc_server import APIServer, APIError, api_route

        Create your handlers by inheriting from APIServer and tagging them with
        @api_route("/path"). Alternately, you can use the APIServer() directly
        by calling `add_handler("path", function)`.

        Raise network errors by raising `APIError(code, message, description=None)`.

        Return responses by simply returning a dict() or str() object.

        Parameter to handlers is a dict().

        Query arguments are shoved into the dict via urllib.parse_qs.
        """
        server_address = (addr, port)
        self.__addr = addr

        # shim class that is an APIHandler
        class HandlerClass(APIHandler):
            pass

        self.handler_class = custom_handler if custom_handler else HandlerClass

        # routed methods map into handler
        for method in type(self).__dict__.values():
            if hasattr(method, "_routes"):
                for route in method._routes:
                    self.add_route(route, method)

        try:
            super().__init__(server_address, HandlerClass)
        except OSError:
            raise GeneralException("Port already in use.")

    def add_route(self, path: str, method: Callable):
        self.handler_class._routes[convert_path(path)] = method

    def port(self):
        """Return current port."""
        return self.socket.getsockname()[1]

    def address(self):
        """Return current IP address."""
        return self.socket.getsockname()[0]

    def uri(self, path):
        """Make a URI pointing at myself."""
        if path[0] == "/":
            path = path[1:]
        return "http://" + self.__addr + ":" + str(self.port()) + "/" + path

    def start(self, blocking=False):
        if not blocking:
            threading.Thread(target=self.serve_forever).start()
        else:
            try:
                self.serve_forever()
            except KeyboardInterrupt:
                print()  # empty line after ^C
                print("Stopping server!")
                return

    def shutdown(self):
        super().shutdown()
        self.socket.close()


class APIHandler(BaseHTTPRequestHandler):
    # I can't help the naming convention of these because that's what
    # BaseHTTPRequestHandler uses for some weird reason
    _routes = {}

    def do_GET(self):
        self.do_action()

    def do_POST(self):
        content = "{}"
        if self.headers["Content-Length"]:
            length = int(self.headers["Content-Length"])
            content = self.rfile.read(length)
        info = None
        if content:
            try:
                info = json.loads(content)
            except json.JSONDecodeError:
                raise APIError(400, "Invalid JSON", content)
        self.do_action(info)

    def get_route(self, path) -> tuple[Callable, dict[str, Any]]:
        for option in self._routes.keys():
            if match_data := option.match(path):
                return self._routes[option], convert_match_to_dict(
                    match_data.groupdict()
                )
        raise APIError(404, "No route found")

    def do_action(self, info=None):
        info = info or {}
        try:
            url = urlparse.urlparse(self.path)

            handler, additional_args = self.get_route(url.path)

            if url.query:
                params = urlparse.parse_qs(url.query)
            else:
                params = {}

            info.update(params)

            if handler:
                try:
                    response = handler(info, **additional_args)
                    self.send_response(200)
                    if response is None:
                        response = ""
                    if isinstance(response, dict):
                        response = json.dumps(response)
                    response = bytes(str(response), "utf-8")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                except APIError:
                    raise
                except ConnectionAbortedError as e:
                    log.error(f"GET {self.path} : {e}")
                except Exception as e:
                    raise APIError(500, str(e))
            else:
                raise APIError(404)
        except APIError as e:
            try:
                self.send_error(e.code, e.msg, e.desc)
            except ConnectionAbortedError as e:
                log.error(f"GET {self.path} : {e}")
