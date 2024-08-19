import inspect
import logging
import pathlib
import traceback
import urllib.parse as urlparse
from threading import Thread
from typing import Optional, Callable
from wsgiref.simple_server import WSGIServer

from jinja2 import Environment, FileSystemLoader

from spiderweb.middleware import MiddlewareMiddleware
from spiderweb.constants import DEFAULT_ENCODING, DEFAULT_ALLOWED_METHODS
from spiderweb.default_views import *  # noqa: F403
from spiderweb.exceptions import (
    ConfigError,
    NotFound,
    APIError,
    NoResponseError,
    SpiderwebNetworkException,
)
from spiderweb.local_server import LocalServerMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse, TemplateResponse
from spiderweb.routes import RoutesMiddleware
from spiderweb.secrets import FernetMiddleware
from spiderweb.utils import get_http_status_by_code

file_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SpiderwebRouter(
    LocalServerMiddleware, MiddlewareMiddleware, RoutesMiddleware, FernetMiddleware
):
    def __init__(
        self,
        addr: str = None,
        port: int = None,
        templates_dirs: list[str] = None,
        middleware: list[str] = None,
        append_slash: bool = False,
        staticfiles_dirs: list[str] = None,
        routes: list[list[str | Callable | dict]] = None,
        error_routes: dict[str, Callable] = None,
        secret_key: str = None,
        log=None,
    ):
        self._routes = {}
        self.routes = routes
        self._error_routes = {}
        self.error_routes = error_routes
        self.addr = addr if addr else "localhost"
        self.port = port if port else 8000
        self.server_address = (self.addr, self.port)
        self.append_slash = append_slash
        self.templates_dirs = templates_dirs
        self.staticfiles_dirs = staticfiles_dirs
        self.middleware = middleware if middleware else []
        self.secret_key = secret_key if secret_key else self.generate_key()

        self.DEFAULT_ENCODING = DEFAULT_ENCODING
        self.DEFAULT_ALLOWED_METHODS = DEFAULT_ALLOWED_METHODS
        self.log = log if log else file_logger

        # for using .start() and .stop()
        self._thread: Optional[Thread] = None
        self._server: Optional[WSGIServer] = None
        self.BASE_DIR = self.get_caller_filepath()

        self.init_fernet()
        self.init_middleware()

        if self.routes:
            self.add_routes()

        if self.templates_dirs:
            self.env = Environment(loader=FileSystemLoader(self.templates_dirs))
        else:
            self.env = None

        if self.staticfiles_dirs:
            for static_dir in self.staticfiles_dirs:
                static_dir = pathlib.Path(static_dir)
                if not pathlib.Path(self.BASE_DIR / static_dir).exists():
                    log.error(
                        f"Static files directory '{str(static_dir)}' does not exist."
                    )
                    raise ConfigError
            self.add_route(r"/static/<str:filename>", send_file)

    def fire_response(self, start_response, request: Request, resp: HttpResponse):
        try:
            status = get_http_status_by_code(resp.status_code)
            cookies = []
            if "Set-Cookie" in resp.headers:
                cookies = resp.headers['Set-Cookie']
                del resp.headers['Set-Cookie']
            headers = list(resp.headers.items())
            for c in cookies:
                headers.append(("Set-Cookie", c))

            start_response(status, headers)

            rendered_output = resp.render()
            if not isinstance(rendered_output, list):
                rendered_output = [rendered_output]

            encoded_resp = [
                chunk.encode(DEFAULT_ENCODING) if isinstance(chunk, str) else chunk
                for chunk in rendered_output
            ]

            return encoded_resp
        except APIError:
            raise
        except ConnectionAbortedError as e:
            self.log.error(f"GET {request.path} : {e}")
        except Exception:
            self.log.error(traceback.format_exc())
            return self.fire_response(
                start_response, request, self.get_error_route(500)(request)
            )

    def get_caller_filepath(self):
        """Figure out who called us and return their path."""
        stack = inspect.stack()
        caller_frame = stack[1]
        return pathlib.Path(caller_frame.filename).parent.parent

    def get_request(self, environ):
        return Request(
            content="",
            environ=environ,
            server=self,
        )

    def send_error_response(
        self, start_response, request: Request, e: SpiderwebNetworkException
    ):
        try:
            status = get_http_status_by_code(500)
            headers = [("Content-type", "text/plain; charset=utf-8")]

            start_response(status, headers)

            resp = [
                f"Something went wrong.\n\nCode: {e.code}\n\nMsg: {e.msg}\n\nDesc: {e.desc}".encode(
                    DEFAULT_ENCODING
                )
            ]

            return resp
        except ConnectionAbortedError as e:
            self.log.error(f"{request.method} {request.path} : {e}")

    def prepare_and_fire_response(self, start_response, request, resp) -> list[bytes]:
        try:
            if isinstance(resp, dict):
                self.fire_response(request, JsonResponse(data=resp))
            if isinstance(resp, TemplateResponse):
                resp.set_template_loader(self.env)

            for middleware in self.middleware:
                middleware.process_response(request, resp)

            return self.fire_response(start_response, request, resp)

        except APIError:
            raise

        except Exception:
            self.log.error(traceback.format_exc())
            self.fire_response(
                start_response, request, self.get_error_route(500)(request)
            )

    def __call__(self, environ, start_response, *args, **kwargs):
        """Entry point for WSGI apps."""
        request = self.get_request(environ)

        try:
            handler, additional_args, allowed_methods = self.get_route(request.path)
        except NotFound:
            handler = self.get_error_route(404)
            additional_args = {}
            allowed_methods = DEFAULT_ALLOWED_METHODS
        request.handler = handler

        if request.method not in allowed_methods:
            # replace the potentially valid handler with the error route
            handler = self.get_error_route(405)

        if request.is_form_request():
            form_data = urlparse.parse_qs(request.content)
            for key, value in form_data.items():
                if len(value) == 1:
                    form_data[key] = value[0]
            setattr(request, request.method, form_data)

        try:
            if handler:
                abort = self.process_request_middleware(request)
                if abort:
                    return
                resp = handler(request, **additional_args)
                if resp is None:
                    raise NoResponseError(f"View {handler} returned None.")
                # run the response through the middleware and send it
                return self.prepare_and_fire_response(start_response, request, resp)
            else:
                raise SpiderwebNetworkException(404)
        except SpiderwebNetworkException as e:
            return self.send_error_response(start_response, request, e)
