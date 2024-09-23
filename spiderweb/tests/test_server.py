import pytest

from spiderweb.exceptions import ConfigError
from spiderweb.tests.helpers import setup


def test_staticfiles_dirs_option():
    app, environ, start_response = setup(staticfiles_dirs="spiderweb/tests/staticfiles")

    assert app.staticfiles_dirs == ["spiderweb/tests/staticfiles"]


def test_staticfiles_dirs_not_found():
    with pytest.raises(ConfigError):
        app, environ, start_response = setup(staticfiles_dirs="not/a/real/path")
