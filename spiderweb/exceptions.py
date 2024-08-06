class SpiderwebException(Exception):
    # parent error class; all child exceptions should inherit from this
    pass


class SpiderwebNetworkException(SpiderwebException):
    """Something has gone wrong with the network stack."""

    def __init__(self, code, msg=None, desc=None):
        self.code = code
        self.msg = msg
        self.desc = desc

    def __str__(self):
        return f"{self.__class__.__name__}({self.code}, {self.msg})"


class APIError(SpiderwebNetworkException):
    pass


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
