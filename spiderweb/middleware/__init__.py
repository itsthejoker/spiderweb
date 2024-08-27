from typing import Callable, ClassVar

from .base import SpiderwebMiddleware as SpiderwebMiddleware
from .csrf import CSRFMiddleware as CSRFMiddleware
from .sessions import SessionMiddleware as SessionMiddleware
from ..exceptions import ConfigError, UnusedMiddleware
from ..request import Request
from ..response import HttpResponse
from ..utils import import_by_string


class MiddlewareMixin:
    """Cannot be called on its own. Requires context of SpiderwebRouter."""

    middleware: list[ClassVar]
    fire_response: Callable

    def init_middleware(self):
        if self.middleware:
            middleware_by_reference = []
            for m in self.middleware:
                try:
                    middleware_by_reference.append(import_by_string(m)(server=self))
                except ImportError:
                    raise ConfigError(f"Middleware '{m}' not found.")
            self.middleware = middleware_by_reference

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
