"""
Source code inspiration: https://github.com/colour-science/flask-compress/blob/master/flask_compress/flask_compress.py
"""
from spiderweb.exceptions import ConfigError
from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.server_checks import ServerCheck
from spiderweb.request import Request
from spiderweb.response import HttpResponse

import gzip


class CheckValidGzipCompressionLevel(ServerCheck):
    INVALID_GZIP_COMPRESSION_LEVEL = (
        "`gzip_compression_level` must be an integer between 1 and 9."
    )

    def check(self):
        if not isinstance(self.server.gzip_compression_level, int):
            raise ConfigError(self.INVALID_GZIP_COMPRESSION_LEVEL)
        if self.server.gzip_compression_level not in range(1, 10):
            raise ConfigError("Gzip compression level must be an integer between 1 and 9.")


class CheckValidGzipMinimumLength(ServerCheck):
    INVALID_GZIP_MINIMUM_LENGTH = "`gzip_minimum_length` must be a positive integer."

    def check(self):
        if not isinstance(self.server.gzip_minimum_length, int):
            raise ConfigError(self.INVALID_GZIP_MINIMUM_LENGTH)
        if self.server.gzip_minimum_length < 1:
            raise ConfigError(self.INVALID_GZIP_MINIMUM_LENGTH)


class GzipMiddleware(SpiderwebMiddleware):

    checks = [CheckValidGzipCompressionLevel, CheckValidGzipMinimumLength]

    algorithm = "gzip"
    minimum_length = 500

    def post_process(
        self, request: Request, response: HttpResponse, rendered_response: str
    ) -> str:
        # Only actually compress the response if the following attributes are true:
        #
        # * The response status code is a 2xx success code
        # * The response length is at least 500 bytes
        # * The response is not already compressed (e.g. it's not an image)
        # * The request accepts gzip encoding
        # * The response is not a streaming response
        if (
            not (200 <= response.status_code < 300)
            or len(rendered_response) < self.minimum_length
            or not isinstance(rendered_response, str)
            or self.algorithm in response.headers.get("Content-Encoding", "")
            or self.algorithm not in request.headers.get("Accept-Encoding", "")
        ):
            return rendered_response

        zipped = gzip.compress(rendered_response.encode("UTF-8"), compresslevel=6)
        response.headers["Content-Encoding"] = self.algorithm
        response.headers["Content-Length"] = str(len(zipped))

        return zipped
