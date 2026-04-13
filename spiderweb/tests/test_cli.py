"""Tests for the spiderweb management CLI (spiderweb/cli.py)."""

import sys

import pytest

from spiderweb.cli import (
    _build_parser,
    _build_serve_parser,
    _cmd_routes,
    _cmd_version,
    _load_app,
    main,
)
from spiderweb.tests.helpers import setup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(**kwargs):
    app, _environ, _sr = setup(**kwargs)
    return app


# ---------------------------------------------------------------------------
# _load_app
# ---------------------------------------------------------------------------


class TestLoadApp:
    def test_loads_valid_app(self):
        # Use the SpiderwebRouter class itself as a known importable attribute.
        from spiderweb.main import SpiderwebRouter

        result = _load_app("spiderweb.main:SpiderwebRouter")
        assert result is SpiderwebRouter

    def test_missing_colon_exits(self):
        with pytest.raises(SystemExit) as exc:
            _load_app("spiderweb.main.SpiderwebRouter")
        assert exc.value.code == 1

    def test_bad_module_exits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            _load_app("nonexistent_xyz_pkg:something")
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "nonexistent_xyz_pkg" in captured.err

    def test_bad_attribute_exits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            _load_app("spiderweb.main:NoSuchAttr")
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "NoSuchAttr" in captured.err


# ---------------------------------------------------------------------------
# version command
# ---------------------------------------------------------------------------


class TestVersionCommand:
    def test_version_prints_package_name(self, capsys):
        _cmd_version(None, None, [])
        out = capsys.readouterr().out
        assert "spiderweb-framework" in out

    def test_version_contains_version_string(self, capsys):
        from spiderweb.constants import __version__

        _cmd_version(None, None, [])
        out = capsys.readouterr().out
        assert __version__ in out


# ---------------------------------------------------------------------------
# routes command
# ---------------------------------------------------------------------------


class TestRoutesCommand:
    def test_no_routes_prints_message(self, capsys):
        app = _make_app()
        _cmd_routes(app, None, [])
        out = capsys.readouterr().out
        assert "No routes registered" in out

    def test_routes_table_shows_path(self, capsys):
        app = _make_app()
        from spiderweb.response import HttpResponse

        @app.route("/hello")
        def hello(request):
            return HttpResponse(content="hi")

        _cmd_routes(app, None, [])
        out = capsys.readouterr().out
        assert "/hello" in out

    def test_routes_table_shows_methods(self, capsys):
        app = _make_app()
        from spiderweb.response import HttpResponse

        @app.route("/ping", allowed_methods=["GET"])
        def ping(request):
            return HttpResponse(content="pong")

        _cmd_routes(app, None, [])
        out = capsys.readouterr().out
        assert "GET" in out

    def test_routes_table_shows_view_name(self, capsys):
        app = _make_app()
        from spiderweb.response import HttpResponse

        @app.route("/greet")
        def greet_view(request):
            return HttpResponse(content="hello")

        _cmd_routes(app, None, [])
        out = capsys.readouterr().out
        assert "greet_view" in out

    def test_routes_table_shows_route_name(self, capsys):
        app = _make_app()
        from spiderweb.response import HttpResponse

        @app.route("/named", name="my_named_route")
        def named_view(request):
            return HttpResponse(content="named")

        _cmd_routes(app, None, [])
        out = capsys.readouterr().out
        assert "my_named_route" in out


# ---------------------------------------------------------------------------
# check command
# ---------------------------------------------------------------------------


class TestCheckCommand:
    def test_check_passes_for_clean_app(self, capsys):
        app = _make_app()
        from spiderweb.cli import _cmd_check

        _cmd_check(app, None, [])
        out = capsys.readouterr().out
        assert "passed" in out.lower()


# ---------------------------------------------------------------------------
# Custom management commands (@app.command decorator)
# ---------------------------------------------------------------------------


class TestCustomCommands:
    def test_decorator_registers_command(self):
        app = _make_app()
        called = []

        @app.command("mycommand")
        def mycommand(a, b, c):
            called.append(True)

        assert "mycommand" in app._management_commands
        app._management_commands["mycommand"](None, None, [])
        assert called

    def test_decorator_returns_original_function(self):
        app = _make_app()

        @app.command("noop")
        def noop(a, b, c):
            return 42

        assert noop(None, None, []) == 42

    def test_cli_dispatches_custom_command(self, capsys, monkeypatch):
        """main() should call a user-registered command when it's on app._management_commands."""
        app = _make_app()
        called = []

        @app.command("greet")
        def greet(a, args, extra):
            called.append("hi")

        # Patch _load_app so we don't need a real importable module path.
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)

        main(["--app", "fake:app", "greet"])
        assert called == ["hi"]


# ---------------------------------------------------------------------------
# CLI error paths
# ---------------------------------------------------------------------------


class TestCLIErrors:
    def test_no_command_exits_zero(self):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 0

    def test_missing_app_for_serve_exits(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["serve"])
        assert exc.value.code == 1
        assert "--app" in capsys.readouterr().err

    def test_unknown_command_exits(self, capsys, monkeypatch):
        app = _make_app()
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)
        with pytest.raises(SystemExit) as exc:
            main(["--app", "fake:app", "doesnotexist"])
        assert exc.value.code == 1
        assert "doesnotexist" in capsys.readouterr().err

    def test_version_needs_no_app(self, capsys):
        # Should not exit with an error even when --app is absent.
        main(["version"])
        assert "spiderweb-framework" in capsys.readouterr().out

    def test_spiderweb_app_env_var_used(self, monkeypatch, capsys):
        """SPIDERWEB_APP env var should supply the --app value."""
        app = _make_app()
        monkeypatch.setenv("SPIDERWEB_APP", "fake:app")
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)

        # routes should work without an explicit --app flag
        from spiderweb.response import HttpResponse

        @app.route("/env")
        def env_view(request):
            return HttpResponse(content="ok")

        main(["routes"])
        out = capsys.readouterr().out
        assert "/env" in out


# ---------------------------------------------------------------------------
# Parser structure
# ---------------------------------------------------------------------------


class TestParser:
    def test_serve_asgi_flag(self):
        args, _ = _build_serve_parser().parse_known_args(["--asgi"])
        assert args.asgi is True

    def test_serve_addr_and_port(self):
        args, _ = _build_serve_parser().parse_known_args(["--addr", "0.0.0.0", "--port", "9001"])
        assert args.addr == "0.0.0.0"
        assert args.port == 9001

    def test_serve_defaults_no_asgi(self):
        args, _ = _build_serve_parser().parse_known_args([])
        assert args.asgi is False
        assert args.addr is None
        assert args.port is None
