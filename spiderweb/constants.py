from peewee import DatabaseProxy

DEFAULT_ALLOWED_METHODS = ["POST", "GET", "PUT", "PATCH", "DELETE"]
DEFAULT_ENCODING = "UTF-8"
__version__ = "1.0.0"

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie
REGEX_COOKIE_NAME = r"^[a-zA-Z0-9\s\(\)<>@,;:\/\\\[\]\?=\{\}\"\t]*$"

DATABASE_PROXY = DatabaseProxy()

DEFAULT_CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
)
DEFAULT_CORS_ALLOW_HEADERS = (
    "accept",
    "authorization",
    "content-type",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
)
