from typing import Callable, ClassVar
import sys

from .base import SpiderwebMiddleware as SpiderwebMiddleware
from ..exceptions import ConfigError, UnusedMiddleware, StartupErrors
from ..request import Request
from ..response import HttpResponse
from ..utils import import_by_string


class MiddlewareMixin:
    """Cannot be called on its own. Requires context of SpiderwebRouter."""

    _middleware: list[str]
    middleware: list[ClassVar]
    fire_response: Callable

    def init_middleware(self):
        if self._middleware:
            middleware_by_reference = []
            for m in self._middleware:
                try:
                    middleware_by_reference.append(import_by_string(m)(server=self))
                except ImportError:
                    raise ConfigError(f"Middleware '{m}' not found.")
            self.middleware = middleware_by_reference

    def run_middleware_checks(self):
        errors = []
        for middleware in self.middleware:
            if hasattr(middleware, "checks"):
                for check in middleware.checks:
                    if issue := check(server=self).check():
                        errors.append(issue)

        if errors:
            # just show the messages
            sys.tracebacklimit = 1
            raise StartupErrors(
                "Problems were identified during startup — cannot continue.", errors
            )

    def process_request_middleware(self, request: Request) -> None | bool:
        for middleware in self.middleware:
            try:
                resp = middleware.process_request(request)
            except UnusedMiddleware:
                self.middleware.remove(middleware)
                continue
            if resp:
                self.process_response_middleware(request, resp)
                return resp  # abort further processing

    def process_response_middleware(
        self, request: Request, response: HttpResponse
    ) -> None:
        for middleware in reversed(self.middleware):
            try:
                middleware.process_response(request, response)
            except UnusedMiddleware:
                self.middleware.remove(middleware)
                continue
