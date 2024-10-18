
"""
    Source code inspiration :https://github.com/colour-science/flask-compress/blob/master/flask_compress/flask_compress.py
"""


from spiderweb.middleware import SpiderwebMiddleware
from spiderweb.request import Request
from spiderweb.response import HttpResponse


import gzip


class GzipMiddleware(SpiderwebMiddleware):
    
    algorithm = "gzip"
    minimum_length = 500

    def post_process(self, request: Request, response: HttpResponse, rendered_response: str) -> str:
        
        #right status, length > 500, instance string (because FileResponse returns list of bytes ,
        # not already compressed, and client accepts gzip
        if not (200 <= response.status_code < 300) or \
           len(rendered_response) < self.minimum_length or \
           not isinstance(rendered_response, str) or \
           self.algorithm in response.headers.get("Content-Encoding", "") or \
           self.algorithm not in request.headers.get("Accept-Encoding", ""):
           return rendered_response
        
        zipped = gzip.compress(rendered_response.encode('UTF-8'))
        response.headers["Content-Encoding"] = self.algorithm
        response.headers["Content-Length"] = str(len(zipped))
        
        return zipped   
        
