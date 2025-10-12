import inspect
from typing import get_type_hints

try:  # pragma: no cover - import guard
    from pydantic import BaseModel  # type: ignore
    from pydantic_core._pydantic_core import ValidationError  # type: ignore

    PYDANTIC_AVAILABLE = True
except Exception:  # pragma: no cover - executed only when pydantic isn't installed
    PYDANTIC_AVAILABLE = False

    class BaseModel:  # minimal stub to allow module import without pydantic
        @classmethod
        def parse_obj(cls, *args, **kwargs):  # noqa: D401 - simple shim
            raise RuntimeError(
                "Pydantic is not installed. Install with 'pip install"
                " spiderweb-framework[pydantic]' or 'pip install pydantic'"
                " to use PydanticMiddleware."
            )

    class ValidationError(Exception):  # simple stand-in so type hints resolve
        def errors(self):  # match pydantic's ValidationError API used below
            return []


from spiderweb import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import JsonResponse
from spiderweb.server_checks import ServerCheck


class RequestModel(BaseModel, Request):
    # type hinting shenanigans that allow us to annotate Request objects
    # with the pydantic models we want to validate them with, but doesn't
    # break the Request object's ability to be used as a Request object
    pass


class CheckPydanticInstalled(ServerCheck):
    def check(self):
        try:
            from pydantic import BaseModel as _BM  # noqa: F401
            from pydantic_core._pydantic_core import ValidationError as _VE  # noqa: F401
            return None
        except Exception:
            return RuntimeError(
                "Pydantic is not installed. Install with 'pip install"
                " spiderweb-framework[pydantic]' or 'pip install pydantic'"
                " to use PydanticMiddleware."
            )


class PydanticMiddleware(SpiderwebMiddleware):
    checks = [CheckPydanticInstalled]

    def process_request(self, request):
        if not request.method == "POST":
            return
        types = get_type_hints(request.handler)
        # we don't know what the user named the request object, but
        # we know that it's first in the list, and it's always an arg.
        request_arg_name = inspect.getfullargspec(request.handler).args[0]
        if types.get(request_arg_name) in RequestModel.__subclasses__():
            try:
                data = types[request_arg_name].parse_obj(request.POST)
                request.validated_data = data
            except ValidationError as e:
                return self.on_error(request, e)

    def on_error(self, request: Request, e: ValidationError):
        # Separated out into its own method so that it can be overridden
        errors = e.errors()
        error_dict = {"message": "Validation error", "errors": []}
        # [
        #   {
        #       'type': 'missing',
        #       'loc': ('comment',),
        #       'msg': 'Field required',
        #       'input': {'email': 'a@a.com'},
        #       'url': 'https://errors.pydantic.dev/2.8/v/missing'
        #   }
        # ]
        for error in errors:
            field = error["loc"][0]
            msg = error["msg"]
            error_dict["errors"].append(f"{field}: {msg}")
        return JsonResponse(status_code=400, data=error_dict)
