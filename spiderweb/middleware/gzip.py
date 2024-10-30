"""
Source code inspiration: https://github.com/colour-science/flask-compress/blob/master/flask_compress/flask_compress.py
"""

from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse

import gzip


class GzipMiddleware(SpiderwebMiddleware):

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

        return zipped.decode("UTF-8")
