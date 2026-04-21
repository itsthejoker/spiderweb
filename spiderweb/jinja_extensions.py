import posixpath

from jinja2 import nodes
from jinja2.ext import Extension


class StaticFilesExtension(Extension):
    # Take things that look like `{% static "file" %}` and replace them with `/static/file`
    tags = {"static"}

    def parse(self, parser):
        token = next(parser.stream)
        args = [parser.parse_expression()]
        return nodes.Output([self.call_method("_static", args)]).set_lineno(
            token.lineno
        )

    def _static(self, file):
        return posixpath.join(f"/{self.environment.server.static_url}", file)


class UrlExtension(Extension):
    # Take things that look like `{% url "route_name" %}` and replace them with the actual URL
    tags = {"url"}

    def parse(self, parser):
        token = next(parser.stream)
        args = [parser.parse_expression()]
        return nodes.Output([self.call_method("_url", args)]).set_lineno(token.lineno)

    def _url(self, route_name):
        return self.environment.server.reverse(route_name)
