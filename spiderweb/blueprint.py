from typing import Callable


class Blueprint:
    """
    A group of routes with a shared URL prefix and optional namespace.

    Usage::

        api = Blueprint(prefix="/api", namespace="api")

        @api.route("/users", name="list")
        def list_users(request):
            return JsonResponse([])

        app = SpiderwebRouter()
        app.include_blueprint(api)

        # Routes are registered as /api/users
        # Reverse lookup: app.reverse("api:list") -> "/api/users"
    """

    def __init__(self, prefix: str = "", namespace: str = None):
        self.prefix = prefix.rstrip("/")
        self.namespace = namespace
        self._pending_routes: list[tuple] = []

    def route(
        self, path: str, allowed_methods: list[str] = None, name: str = None
    ) -> Callable:
        def outer(func):
            self.add_route(path, func, allowed_methods, name)
            return func

        return outer

    def add_route(
        self,
        path: str,
        func: Callable,
        allowed_methods: list[str] = None,
        name: str = None,
    ):
        self._pending_routes.append((path, func, allowed_methods, name))
