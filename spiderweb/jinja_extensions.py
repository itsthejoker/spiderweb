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
