import inspect
import logging
import pathlib
import re
import traceback
import urllib.parse as urlparse
from logging import Logger
from threading import Thread
from typing import Optional, Callable, Sequence, Literal
from wsgiref.simple_server import WSGIServer

from jinja2 import BaseLoader, FileSystemLoader
from peewee import Database, SqliteDatabase

from spiderweb.middleware import MiddlewareMixin
from spiderweb.constants import (
    DEFAULT_CORS_ALLOW_METHODS,
    DEFAULT_CORS_ALLOW_HEADERS,
)
from spiderweb.constants import (
    DATABASE_PROXY,
    DEFAULT_ENCODING,
    DEFAULT_ALLOWED_METHODS,
)
from spiderweb.db import SpiderwebModel
from spiderweb.default_views import *  # noqa: F403
from spiderweb.exceptions import (
    ConfigError,
    NotFound,
    APIError,
    NoResponseError,
    SpiderwebNetworkException,
)
from spiderweb.jinja_core import SpiderwebEnvironment
from spiderweb.local_server import LocalServerMixin
from spiderweb.request import Request
from spiderweb.response import HttpResponse, TemplateResponse, JsonResponse
from spiderweb.routes import RoutesMixin
from spiderweb.secrets import FernetMixin
from spiderweb.utils import get_http_status_by_code, convert_url_to_regex

console_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SpiderwebRouter(LocalServerMixin, MiddlewareMixin, RoutesMixin, FernetMixin):
    def __init__(
        self,
        *,
        addr: str = None,
        port: int = None,
        allowed_hosts: Sequence[str | re.Pattern] = None,
        cors_allowed_origins: Sequence[str] = None,
        cors_allowed_origin_regexes: Sequence[str] = None,
        cors_allow_all_origins: bool = False,
        cors_urls_regex: str | re.Pattern[str] = r"^.*$",
        cors_allow_methods: Sequence[str] = None,
        cors_allow_headers: Sequence[str] = None,
        cors_expose_headers: Sequence[str] = None,
        cors_preflight_max_age: int = 86400,
        cors_allow_credentials: bool = False,
        cors_allow_private_network: bool = False,
        csrf_trusted_origins: Sequence[str] = None,
        db: Optional[Database] = None,
        debug: bool = False,
        templates_dirs: Sequence[str] = None,
        middleware: Sequence[str] = None,
        append_slash: bool = False,
        staticfiles_dirs: Sequence[str] = None,
        static_url: str = "static",
        routes: Sequence[tuple[str, Callable] | tuple[str, Callable, dict]] = None,
        error_routes: dict[int, Callable] = None,
        secret_key: str = None,
        session_max_age: int = 60 * 60 * 24 * 14,  # 2 weeks
        session_cookie_name: str = "swsession",
        session_cookie_secure: bool = False,  # should be true if serving over HTTPS
        session_cookie_http_only: bool = True,
        session_cookie_same_site: Literal["strict", "lax", "none"] = "lax",
        session_cookie_path: str = "/",
        log: Logger = None,
        **kwargs,
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
        self.static_url = static_url
        self._middleware: list[str] = middleware or []
        self.middleware: list[Callable] = []
        self.secret_key = secret_key if secret_key else self.generate_key()
        self._allowed_hosts = allowed_hosts or ["*"]
        self.allowed_hosts = [convert_url_to_regex(i) for i in self._allowed_hosts]

        self.cors_allowed_origins = cors_allowed_origins or []
        self.cors_allowed_origin_regexes = cors_allowed_origin_regexes or []
        self.cors_allow_all_origins = cors_allow_all_origins
        self.cors_urls_regex = cors_urls_regex
        self.cors_allow_methods = cors_allow_methods or DEFAULT_CORS_ALLOW_METHODS
        self.cors_allow_headers = cors_allow_headers or DEFAULT_CORS_ALLOW_HEADERS
        self.cors_expose_headers = cors_expose_headers or []
        self.cors_preflight_max_age = cors_preflight_max_age
        self.cors_allow_credentials = cors_allow_credentials
        self.cors_allow_private_network = cors_allow_private_network

        self._csrf_trusted_origins = csrf_trusted_origins or []
        self.csrf_trusted_origins = [
            convert_url_to_regex(i) for i in self._csrf_trusted_origins
        ]

        self.debug = debug

        self.extra_data = kwargs

        # session middleware
        self.session_max_age = session_max_age
        self.session_cookie_name = session_cookie_name
        self.session_cookie_secure = session_cookie_secure
        self.session_cookie_http_only = session_cookie_http_only
        self.session_cookie_same_site = session_cookie_same_site
        self.session_cookie_path = session_cookie_path

        self.DEFAULT_ENCODING = DEFAULT_ENCODING
        self.DEFAULT_ALLOWED_METHODS = DEFAULT_ALLOWED_METHODS
        self.log: logging.Logger = log if log else console_logger

        # for using .start() and .stop()
        self._thread: Optional[Thread] = None
        self._server: Optional[WSGIServer] = None
        self.BASE_DIR = self.get_caller_filepath()

        self.init_fernet()
        self.init_middleware()

        self.db = db or SqliteDatabase(self.BASE_DIR / "spiderweb.db")
        # give the models the db connection
        DATABASE_PROXY.initialize(self.db)
        self.db.create_tables(SpiderwebModel.__subclasses__())
        for model in SpiderwebModel.__subclasses__():
            model.check_for_needed_migration()

        if self.routes:
            self.add_routes()

        if self.error_routes:
            self.add_error_routes()

        template_env_args = {
            "server": self,
            "extensions": [
                "spiderweb.jinja_extensions.StaticFilesExtension",
            ],
        }

        if self.templates_dirs:
            self.template_loader = SpiderwebEnvironment(
                loader=FileSystemLoader(self.templates_dirs),
                **template_env_args,
            )
        else:
            self.template_loader = None
        self.string_loader = SpiderwebEnvironment(
            loader=BaseLoader(), **template_env_args
        )

        if self.staticfiles_dirs:
            for static_dir in self.staticfiles_dirs:
                static_dir = pathlib.Path(static_dir)
                if not pathlib.Path(self.BASE_DIR / static_dir).exists():
                    self.log.error(
                        f"Static files directory '{str(static_dir)}' does not exist."
                    )
                    raise ConfigError
            if self.debug:
                # We don't need a log message here because this is the expected behavior
                self.add_route(rf"/{self.static_url}/<path:filename>", send_file)  # noqa: F405
            else:
                self.log.warning(
                    "`staticfiles_dirs` is set, but `debug` is set to FALSE. Static"
                    " files will not be served."
                )

        # finally, run the startup checks to verify everything is correct and happy.
        self.log.info("Run startup checks...")
        self.run_middleware_checks()

    def fire_response(self, start_response, request: Request, resp: HttpResponse):
        try:
            status = get_http_status_by_code(resp.status_code)
            cookies = []
            varies = []
            resp.headers = {k.replace("_", "-"): v for k, v in resp.headers.items()}
            if "set-cookie" in resp.headers:
                cookies = resp.headers["set-cookie"]
                del resp.headers["set-cookie"]
            if "vary" in resp.headers:
                varies = resp.headers["vary"]
                del resp.headers["vary"]
            resp.headers = {k: str(v) for k, v in resp.headers.items()}
            headers = list(resp.headers.items())
            for c in cookies:
                headers.append(("set-cookie", str(c)))
            for v in varies:
                headers.append(("vary", str(v)))

            start_response(status, headers)

            try:
                rendered_output = resp.render()
            except Exception as e:
                self.log.error("Fatal error!")
                self.log.error(e)
                self.log.error(traceback.format_exc())
                return [f"Internal Server Error: {e}".encode(DEFAULT_ENCODING)]

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
            headers = [("Content-Type", "text/plain; charset=utf-8")]

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
                return self.fire_response(
                    start_response, request, JsonResponse(data=resp)
                )
            if isinstance(resp, TemplateResponse):
                resp.set_template_loader(self.template_loader)
                resp.set_string_loader(self.string_loader)

            self.process_response_middleware(request, resp)

            return self.fire_response(start_response, request, resp)

        except APIError:
            raise

        except Exception:
            self.log.error(traceback.format_exc())
            self.fire_response(
                start_response, request, self.get_error_route(500)(request)
            )

    def check_valid_host(self, request) -> bool:
        host = request.headers.get("http_host")
        if not host:
            return False
        for option in self.allowed_hosts:
            if re.match(option, host):
                return True
        return False

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

        if not self.check_valid_host(request):
            handler = self.get_error_route(403)

        if request.is_form_request():
            form_data = urlparse.parse_qs(request.content)
            for key, value in form_data.items():
                if len(value) == 1:
                    form_data[key] = value[0]
            setattr(request, request.method, form_data)

        try:
            if handler:
                abort_view = self.process_request_middleware(request)
                if abort_view:
                    return self.prepare_and_fire_response(
                        start_response, request, abort_view
                    )
                resp = handler(request, **additional_args)
                if resp is None:
                    raise NoResponseError(f"View {handler} returned None.")
                # run the response through the middleware and send it
                return self.prepare_and_fire_response(start_response, request, resp)
            else:
                raise SpiderwebNetworkException(404)
        except SpiderwebNetworkException as e:
            return self.send_error_response(start_response, request, e)
