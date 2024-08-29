import inspect
from typing import get_type_hints

from pydantic import BaseModel
from pydantic_core._pydantic_core import ValidationError
from spiderweb import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import JsonResponse


class RequestModel(BaseModel, Request):
    # type hinting shenanigans that allow us to annotate Request objects
    # with the pydantic models we want to validate them with, but doesn't
    # break the Request object's ability to be used as a Request object
    pass


class PydanticMiddleware(SpiderwebMiddleware):
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
        # [{'type': 'missing', 'loc': ('comment',), 'msg': 'Field required', 'input': {'email': 'a@a.com'}, 'url': 'https://errors.pydantic.dev/2.8/v/missing'}]
        for error in errors:
            field = error["loc"][0]
            msg = error["msg"]
            error_dict["errors"].append(f"{field}: {msg}")
        return JsonResponse(status_code=400, data=error_dict)
