from http import HTTPStatus
from typing import Optional

from spiderweb.request import Request


def import_by_string(name):
    # https://stackoverflow.com/a/547867
    components = name.split(".")
    mod = __import__(components[0])
    for comp in components[1:]:
        mod = getattr(mod, comp)
    return mod


def is_safe_path(path: str) -> bool:
    # this cannot possibly catch all issues
    return not ".." in str(path)


def get_http_status_by_code(code: int) -> Optional[str]:
    """
    Get the full HTTP status code required by WSGI by code.

    Example:
        >>> get_http_status_by_code(200)
        '200 OK'
    """
    resp = HTTPStatus(code)
    if resp:
        return f"{resp.value} {resp.phrase}"


def is_form_request(request: Request) -> bool:
    return (
        "Content-Type" in request.headers
        and request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    )
