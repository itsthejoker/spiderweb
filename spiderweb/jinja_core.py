from typing import TYPE_CHECKING

from jinja2 import Environment


if TYPE_CHECKING:
    from spiderweb import SpiderwebRouter


class SpiderwebEnvironment(Environment):
    # Contains all the normal abilities of the Jinja environment, but with a link
    # back to the server for easy access to settings and other server-related
    # information.
    def __init__(self, server=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server: "SpiderwebRouter" = server
