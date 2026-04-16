import inspect
import re
from typing import Callable, Any, Sequence, Optional

from spiderweb.constants import DEFAULT_ALLOWED_METHODS
from spiderweb.converters import *  # noqa: F403
from spiderweb.default_views import *  # noqa: F403
from spiderweb.exceptions import (
    NotFound,
    ConfigError,
    ParseError,
    SpiderwebException,
    ReverseNotFound,
    MethodNotAllowed,
)
from spiderweb.response import RedirectResponse, HttpResponse


class View:
    """
    Class that includes all the inheritance objects for a class-based view.

    If a class-based view is chosen, then we assume that the person using
    it knows exactly what HTTP methods that they want to accept. Instead
    of going by the default allowed methods, we'll block the defaults and
    automatically handle the rest, while they override what they want to
    handle.

    We explictly do not include CONNECT and TRACE as valid verbs here. CONNECT
    is for internet-facing services (like nginx) and TRACE should default to
    a 405 METHOD NOT ALLOWED.

    ref: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods
    """

    def __init__(self, *args, **kwargs):
        self.template_name: Optional[str] = None

    def __call__(self, request, *args, **kwargs):
        # DO NOT OVERRIDE.
        if hasattr(self, request.method.lower()):
            return getattr(self, request.method.lower())(request, *args, **kwargs)
        raise MethodNotAllowed

    # The descriptions are straight from Mozilla -- they're just here so
    # that they autopopulate in end user IDEs.

    def delete(self, request, *args, **kwargs) -> HttpResponse:
        """
        The DELETE method deletes the specified resource.
        """
        raise MethodNotAllowed

    def get(self, request, *args, **kwargs) -> HttpResponse:
        """
        The GET method requests a representation of the specified resource.
        Requests using GET should only retrieve data and should not contain a
        request content.
        """
        raise MethodNotAllowed

    def head(self, request, *args, **kwargs) -> HttpResponse:
        """
        The HEAD method asks for a response identical to a GET request, but
        without a response body.
        """
        raise MethodNotAllowed

    def options(self, request, *args, **kwargs) -> HttpResponse:
        """
        The OPTIONS method describes the communication options for the target
        resource.
        """
        # Get a list of all functions on the child class that called this.
        # Filter out all the functions that aren't route-related, then
        # return that. OPTIONS is always available, so we include it by
        # default.
        values = {"options"}
        for cls in type(self).mro():
            if cls is View:
                break
            values.update(
                {
                    name
                    for name in cls.__dict__.keys()
                    if name
                    in ["get", "post", "delete", "head", "put", "patch", "options"]
                    and callable(getattr(self, name))
                }
            )
        return HttpResponse(
            status_code=204, headers={"ALLOW": ", ".join(values).upper()}
        )

    def patch(self, request, *args, **kwargs) -> HttpResponse:
        """
        The PATCH method applies partial modifications to a resource.
        """
        raise MethodNotAllowed

    def post(self, request, *args, **kwargs) -> HttpResponse:
        """
        The POST method submits an entity to the specified resource, often
        causing a change in state or side effects on the server.
        """
        raise MethodNotAllowed

    def put(self, request, *args, **kwargs) -> HttpResponse:
        """
        The PUT method replaces all current representations of the target
        resource with the request content.
        """
        raise MethodNotAllowed


def convert_match_to_dict(match: dict, extra_converters: dict = None):
    """Convert a match object to a dict with the proper converted types for each match.

    extra_converters maps converter class names to converter classes and is used
    for any custom converters registered via register_converter().
    """
    result = {}
    for k, v in match.items():
        param_name, converter_name = k.split("__")
        if extra_converters and converter_name in extra_converters:
            cls = extra_converters[converter_name]
        else:
            cls = globals()[converter_name]
        result[param_name] = cls().to_python(v)
    return result


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
    _converters: dict  # name -> converter class (custom converters)
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
        # Build a by-class-name lookup for any registered custom converters so
        # convert_match_to_dict can find them without touching globals().
        custom_by_class = {cls.__name__: cls for cls in self._converters.values()}
        for option in self._routes.keys():
            if match_data := option.match(path):
                return (
                    self._routes[option]["func"],
                    convert_match_to_dict(match_data.groupdict(), custom_by_class),
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
                    converter_name, name = name.split(":")
                    # Check custom converters first, then fall back to built-ins.
                    if converter_name in self._converters:
                        converter_cls = self._converters[converter_name]
                    else:
                        try:
                            converter_cls = globals()[
                                converter_name.title() + "Converter"
                            ]
                        except KeyError:
                            raise ParseError(f"Unknown converter {converter_name}")
                else:
                    converter_cls = StrConverter  # noqa: F405
                parts[i] = (
                    rf"(?P<{name}__{converter_cls.__name__}>{converter_cls.regex})"
                )
        return re.compile(rf"^{'/'.join(parts)}$")

    def register_converter(self, cls) -> None:
        """Register a custom path-parameter converter class.

        The converter must have a ``regex`` class attribute (the pattern to
        match) and a ``to_python(value)`` method.  Its ``name`` attribute (or,
        falling back to the class name lowercased with "converter" stripped) is
        what you use in route paths::

            class SlugConverter:
                regex = r"[-a-z0-9_]+"
                name = "slug"

                def to_python(self, value):
                    return str(value)

            app.register_converter(SlugConverter)

            @app.route("/posts/<slug:post_slug>")
            def get_post(request, post_slug): ...
        """
        name = getattr(cls, "name", cls.__name__.lower().replace("converter", ""))
        self._converters[name] = cls

    def include_routegroup(self, routegroup) -> None:
        """Include all routes from a RouteGroup into this router.

        Route paths are prefixed with ``routegroup.prefix``.  If the group
        has a ``namespace``, route names become ``"namespace:name"``.
        """
        for path, func, allowed_methods, name in routegroup._pending_routes:
            full_path = routegroup.prefix + path
            if name is not None and routegroup.namespace:
                full_name = f"{routegroup.namespace}:{name}"
            else:
                full_name = name
            self.add_route(full_path, func, allowed_methods, full_name)

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

        if inspect.isclass(method) and issubclass(method, View):
            view_class = method

            def wrapped_view(request, *args, **kwargs):
                return view_class()(request, *args, **kwargs)

            method = wrapped_view

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
