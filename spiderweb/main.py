# Started life from
# https://gist.github.com/earonesty/ab07b4c0fea2c226e75b3d538cc0dc55
#
# Extensively modified by @itsthejoker
import json
import re
import signal
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse as urlparse
import threading
import logging
from typing import Callable, Any, NoReturn

from jinja2 import Environment, FileSystemLoader

from spiderweb.converters import *  # noqa: F403
from spiderweb.default_responses import http403, http404, http500  # noqa: F401
from spiderweb.exceptions import (
    APIError,
    ConfigError,
    ParseError,
    GeneralException,
    NoResponseError, UnusedMiddleware, SpiderwebNetworkException, NotFound,
)
from spiderweb.request import Request
from spiderweb.response import HttpResponse, JsonResponse, TemplateResponse, RedirectResponse
from spiderweb.utils import import_by_string


log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def route(path):
    def outer(func):
        if not hasattr(func, "_routes"):
            setattr(func, "_routes", [])
        func._routes += [path]
        return func

    return outer


class DummyRedirectRoute:
    def __init__(self, location):
        self.location = location

    def __call__(self, request):
        return RedirectResponse(self.location)


def convert_match_to_dict(match: dict):
    """Convert a match object to a dict with the proper converted types for each match."""
    return {
        k.split("__")[0]: globals()[k.split("__")[1]]().to_python(v)
        for k, v in match.items()
    }


class WebServer(HTTPServer):
    def __init__(
        self,
        addr: str = None,
        port: int = None,
        custom_handler: Callable = None,
        templates_dirs: list[str] = None,
        middleware: list[str] = None,
        append_slash: bool = False,
    ):
        """
        Create a new server on address, port. Port can be zero.

        > from simple_rpc_server import WebServer, APIError, route

        Create your handlers by inheriting from WebServer and tagging them with
        @route("/path"). Alternately, you can use the WebServer() directly
        by calling `add_handler("path", function)`.
        """
        addr = addr if addr else "localhost"
        port = port if port else 8000
        self.append_slash = append_slash
        self.templates_dirs = templates_dirs
        self.middleware = middleware if middleware else []
        self._thread = None

        if self.middleware:
            middleware_by_reference = []
            for m in self.middleware:
                try:
                    middleware_by_reference.append(import_by_string(m)())
                except ImportError:
                    raise ConfigError(f"Middleware '{m}' not found.")
            self.middleware = middleware_by_reference

        if self.templates_dirs:
            self.env = Environment(loader=FileSystemLoader(self.templates_dirs))
        else:
            self.env = None
        server_address = (addr, port)
        self.__addr = addr

        # shim class that is an RequestHandler
        class HandlerClass(RequestHandler):
            pass

        # inject template loader, middleware, and other important things into handler
        self.handler_class = custom_handler if custom_handler else HandlerClass
        self.handler_class.env = self.env
        self.handler_class.middleware = self.middleware
        self.handler_class.append_slash = self.append_slash

        # routed methods map into handler
        for method in type(self).__dict__.values():
            if hasattr(method, "_routes"):
                for route in method._routes:
                    self.add_route(route, method)

        try:
            super().__init__(server_address, self.handler_class)
        except OSError:
            raise GeneralException("Port already in use.")

    def convert_path(self, path: str):
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
                parts[i] = rf"(?P<{name}__{str(converter.__name__)}>{converter.regex})"
        return re.compile(rf"^{'/'.join(parts)}$")

    def check_for_route_duplicates(self, path: str):
        if self.convert_path(path) in self.handler_class._routes:
            raise ConfigError(f"Route '{path}' already exists.")

    def add_route(self, path: str, method: Callable):
        """Add a route to the server."""
        if not hasattr(self.handler_class, "_routes"):
            setattr(self.handler_class, "_routes", [])

        if self.append_slash and not path.endswith("/"):
            updated_path = path + "/"
            self.check_for_route_duplicates(updated_path)
            self.check_for_route_duplicates(path)
            self.handler_class._routes[self.convert_path(path)] = DummyRedirectRoute(updated_path)
            self.handler_class._routes[self.convert_path(updated_path)] = method
        else:
            self.check_for_route_duplicates(path)
            self.handler_class._routes[self.convert_path(path)] = method

    def route(self, path) -> Callable:
        """
        Decorator for adding a route to a view.

        Usage:

        app = WebServer()

        @app.route("/hello")
        def index(request):
            return HttpResponse(content="Hello, world!")

        :param path: str
        :return: Callable
        """

        def outer(func):
            self.add_route(path, func)
            return func

        return outer

    @property
    def port(self):
        """Return current port."""
        return self.socket.getsockname()[1]

    @property
    def address(self):
        """Return current IP address."""
        return self.socket.getsockname()[0]

    def uri(self, path=None):
        """Make a URI pointing at myself."""
        path = path if path else ""
        if path.startswith("/"):
            path = path[1:]
        return self.__addr + ":" + str(self.port()) + "/" + path

    def signal_handler(self, sig, frame) -> NoReturn:
        log.warning('Shutting down!')
        self.stop()

    def start(self, blocking=False):
        signal.signal(signal.SIGINT, self.signal_handler)
        log.info(f"Starting server on {self.address}:{self.port}")
        log.info("Press CTRL+C to stop the server.")
        self._thread = threading.Thread(target=self.serve_forever)
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
        super().shutdown()
        self.socket.close()


class RequestHandler(BaseHTTPRequestHandler):
    # I can't help the naming convention of these because that's what
    # BaseHTTPRequestHandler uses for some weird reason

    # These stop pycharm from complaining about these not existing. They're
    # injected by the WebServer class at runtime
    _routes = {}
    middleware = []

    def get_request(self):
        return Request(
            content="",
            body="",
            method=self.command,
            headers=self.headers,
            path=self.path,
        )

    def do_GET(self):
        request = self.get_request()
        self.handle_request(request)

    def do_POST(self):
        content = "{}"
        if self.headers["Content-Length"]:
            length = int(self.headers["Content-Length"])
            content = self.rfile.read(length)
        request = self.get_request()
        request.content = content
        if content:
            try:
                request.json()
            except json.JSONDecodeError:
                raise APIError(400, "Invalid JSON", content)
        self.handle_request(request)

    def get_route(self, path) -> tuple[Callable, dict[str, Any]]:
        for option in self._routes.keys():
            if match_data := option.match(path):
                return self._routes[option], convert_match_to_dict(
                    match_data.groupdict()
                )
        raise NotFound()

    def get_error_route(self, code: int) -> Callable:
        try:
            view = globals()[f"http{code}"]
            return view
        except KeyError:
            return http500

    def _fire_response(self, resp: HttpResponse):
        self.send_response(resp.status_code)
        content = resp.render()
        self.send_header("Content-Length", str(len(content)))
        if resp.headers:
            for key, value in resp.headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(bytes(content, "utf-8"))

    def fire_response(self, request: Request, resp: HttpResponse):
        try:
            self._fire_response(resp)
        except APIError:
            raise
        except ConnectionAbortedError as e:
            log.error(f"GET {self.path} : {e}")
        except Exception:
            log.error(traceback.format_exc())
            self.fire_response(request, self.get_error_route(500)(request))

    def process_request_middleware(self, request: Request) -> None | bool:
        for middleware in self.middleware:
            try:
                resp = middleware.process_request(request)
            except UnusedMiddleware:
                self.middleware.remove(middleware)
                continue
            if resp:
                self.process_response_middleware(request, resp)
                self.fire_response(request, resp)
                return True  # abort further processing

    def process_response_middleware(self, request: Request, response: HttpResponse) -> None:
        for middleware in self.middleware:
            try:
                middleware.process_response(request, response)
            except UnusedMiddleware:
                self.middleware.remove(middleware)
                continue

    def prepare_and_fire_response(self, request, resp) -> None:
        try:
            if isinstance(resp, dict):
                self.fire_response(request, JsonResponse(data=resp))
            if isinstance(resp, TemplateResponse):
                if hasattr(self, "env"):  # injected from above
                    resp.set_template_loader(self.env)

            for middleware in self.middleware:
                middleware.process_response(request, resp)

            self.fire_response(request, resp)

        except APIError:
            raise

        except Exception:
            log.error(traceback.format_exc())
            self.fire_response(request, self.get_error_route(500)(request))

    def send_error_response(self, request: Request, e: SpiderwebNetworkException):
        try:
            self.send_error(e.code, e.msg, e.desc)
        except ConnectionAbortedError as e:
            log.error(f"{request.method} {self.path} : {e}")

    def handle_request(self, request):

        request.url = urlparse.urlparse(request.path)

        try:
            handler, additional_args = self.get_route(request.url.path)
        except NotFound:
            handler = self.get_error_route(404)
            additional_args = {}

        if request.url.query:
            params = urlparse.parse_qs(request.url.query)
        else:
            params = {}

        request.query_params = params
        try:
            if handler:
                # middleware is injected from WebServer
                abort = self.process_request_middleware(request)
                if abort:
                    return

                resp = handler(request, **additional_args)
                if resp is None:
                    raise NoResponseError(f"View {handler} returned None.")
                # run the response through the middleware and send it
                self.prepare_and_fire_response(request, resp)
            else:
                raise SpiderwebNetworkException(404)
        except SpiderwebNetworkException as e:
            self.send_error_response(request, e)
