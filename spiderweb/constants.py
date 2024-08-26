from peewee import DatabaseProxy

DEFAULT_ALLOWED_METHODS = ["GET"]
DEFAULT_ENCODING = "UTF-8"
__version__ = "0.10.0"

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie
REGEX_COOKIE_NAME = r"^[a-zA-Z0-9\s\(\)<>@,;:\/\\\[\]\?=\{\}\"\t]*$"

DATABASE_PROXY = DatabaseProxy()
