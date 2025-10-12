import re
from typing import Callable, Any, Sequence

from spiderweb.constants import DEFAULT_ALLOWED_METHODS
from spiderweb.converters import *  # noqa: F403
from spiderweb.default_views import *  # noqa: F403
from spiderweb.exceptions import (
    NotFound,
    ConfigError,
    ParseError,
    SpiderwebException,
    ReverseNotFound,
)
from spiderweb.response import RedirectResponse


def convert_match_to_dict(match: dict):
    """Convert a match object to a dict with the proper converted types for each match."""
    return {
        k.split("__")[0]: globals()[k.split("__")[1]]().to_python(v)
        for k, v in match.items()
    }


class DummyRedirectRoute:
    def __init__(self, location):
        self.location = location

    def __call__(self, request):
        return RedirectResponse(self.location)


class RoutesMixin:
    """Cannot be called on its own. Requires context of SpiderwebRouter."""

    # ones that start with underscores are the compiled versions, non-underscores
    # are the user-supplied versions
    _routes: dict
    routes: Sequence[tuple[str, Callable] | tuple[str, Callable, dict]]
    _error_routes: dict
    error_routes: dict[int, Callable]
    append_slash: bool
    fix_route_starting_slash: bool

    def route(self, path, allowed_methods=None, name=None) -> Callable:
        """
        Decorator for adding a route to a view.

        Usage:

        app = WebServer()

        @app.route("/hello")
        def index(request):
            return HttpResponse(content="Hello, world!")

        :param path: str
        :param allowed_methods: list[str]
        :param name: str
        :return: Callable
        """

        def outer(func):
            self.add_route(path, func, allowed_methods, name)
            return func

        return outer

    def get_route(self, path) -> tuple[Callable, dict[str, Any], list[str]]:
        for option in self._routes.keys():
            if match_data := option.match(path):
                return (
                    self._routes[option]["func"],
                    convert_match_to_dict(match_data.groupdict()),
                    self._routes[option]["allowed_methods"],
                )
        raise NotFound()

    def add_error_route(self, code: int, method: Callable):
        """Add an error route to the server."""
        if code not in self._error_routes:
            self._error_routes[code] = method
        else:
            raise ConfigError(f"Error route for code {code} already exists.")

    def error(self, code: int) -> Callable:
        def outer(func):
            self.add_error_route(code, func)
            return func

        return outer

    def get_error_route(self, code: int) -> Callable:
        view = self._error_routes.get(code) or globals().get(f"http{code}")
        if not view:
            return http500  # noqa: F405
        return view

    def check_for_route_duplicates(self, path: str):
        if self.convert_path(path) in self._routes:
            raise ConfigError(f"Route '{path}' already exists.")

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

    def add_route(
        self,
        path: str,
        method: Callable,
        allowed_methods: None | list[str] = None,
        name: str = None,
    ):
        """Add a route to the server."""
        allowed_methods = (
            getattr(method, "allowed_methods", None)
            or allowed_methods
            or DEFAULT_ALLOWED_METHODS
        )
        if not path.startswith("/") and self.fix_route_starting_slash:
            path = "/" + path
        reverse_path = re.sub(r"<(.*?):(.*?)>", r"{\2}", path) if "<" in path else path

        def get_packet(func):
            return {
                "func": func,
                "allowed_methods": allowed_methods,
                "name": name,
                "reverse": reverse_path,
            }

        if self.append_slash and not path.endswith("/"):
            updated_path = path + "/"
            self.check_for_route_duplicates(updated_path)
            self.check_for_route_duplicates(path)
            self._routes[self.convert_path(path)] = get_packet(
                DummyRedirectRoute(updated_path)
            )
            self._routes[self.convert_path(updated_path)] = get_packet(method)
        else:
            self.check_for_route_duplicates(path)
            self._routes[self.convert_path(path)] = get_packet(method)

    def add_routes(self):
        for line in self.routes:
            if len(line) == 3:
                path, func, kwargs = line
                for k, v in kwargs.items():
                    setattr(func, k, v)
            else:
                path, func = line
            self.add_route(path, func)

    def add_error_routes(self):
        for code, func in self.error_routes.items():
            self.add_error_route(int(code), func)

    def reverse(
        self, view_name: str, data: dict[str, Any] = None, query: dict[str, Any] = None
    ) -> str:
        # take in a view name and return the path
        for option in self._routes.values():
            if option["name"] == view_name:
                path = option["reverse"]
                if args := re.findall(r"{(.*?)}", path):
                    if not data:
                        raise SpiderwebException(
                            f"Missing arguments for reverse: {args}"
                        )
                    for arg in args:
                        if arg not in data:
                            raise SpiderwebException(
                                f"Missing argument '{arg}' for reverse."
                            )
                        path = path.replace(f"{{{arg}}}", str(data[arg]))

                if query:
                    path += "?" + "&".join([f"{k}={str(v)}" for k, v in query.items()])
                return path
        raise ReverseNotFound(f"View '{view_name}' not found.")
