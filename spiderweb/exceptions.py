class SpiderwebException(Exception):
    # parent error class; all child exceptions should inherit from this
    def __str__(self):
        return f"{self.__class__.__name__}({self.code}, {self.msg})"


class SpiderwebNetworkException(SpiderwebException):
    """Something has gone wrong with the network stack."""

    def __init__(self, code, msg=None, desc=None):
        self.code = code
        self.msg = msg
        self.desc = desc


class APIError(SpiderwebNetworkException):
    pass


class NotFound(SpiderwebNetworkException):
    def __init__(self):
        self.code = 404
        self.msg = "Not Found"
        self.desc = "The requested resource could not be found"


class BadRequest(SpiderwebNetworkException):
    def __init__(self, desc=None):
        self.code = 400
        self.msg = "Bad Request"
        self.desc = desc if desc else "The request could not be understood by the server"


class Unauthorized(SpiderwebNetworkException):
    def __init__(self, desc=None):
        self.code = 401
        self.msg = "Unauthorized"
        self.desc = desc if desc else "The request requires user authentication"


class Forbidden(SpiderwebNetworkException):
    def __init__(self, desc=None):
        self.code = 403
        self.msg = "Forbidden"
        self.desc = desc if desc else "You are not allowed to access this resource"


class ServerError(SpiderwebNetworkException):
    def __init__(self, desc=None):
        self.code = 500
        self.msg = "Internal Server Error"
        self.desc = desc if desc else "The server has encountered an error"


class ConfigError(SpiderwebException):
    pass


class ParseError(SpiderwebException):
    pass


class GeneralException(SpiderwebException):
    pass


class UnusedMiddleware(SpiderwebException):
    pass


class NoResponseError(SpiderwebException):
    pass
