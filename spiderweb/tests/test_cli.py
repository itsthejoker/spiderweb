"""Tests for the spiderweb management CLI (spiderweb/cli.py)."""

import sys

import pytest

from spiderweb.cli import (
    _build_parser,
    _build_serve_parser,
    _cmd_routes,
    _cmd_version,
    _find_pyproject_app,
    _load_app,
    _read_pyproject_config,
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
# pyproject.toml discovery
# ---------------------------------------------------------------------------


class TestFindPyprojectApp:
    def test_returns_app_value_from_pyproject(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.spiderweb]\napp = \"mymod:myapp\"\n"
        )
        monkeypatch.chdir(tmp_path)
        assert _find_pyproject_app() == "mymod:myapp"

    def test_returns_none_when_key_absent(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text("[tool.other]\nkey = \"val\"\n")
        monkeypatch.chdir(tmp_path)
        assert _find_pyproject_app() is None

    def test_returns_none_when_no_pyproject(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert _find_pyproject_app() is None

    def test_walks_up_to_find_pyproject(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.spiderweb]\napp = \"pkg:obj\"\n"
        )
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert _find_pyproject_app() == "pkg:obj"

    def test_closer_pyproject_wins(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.spiderweb]\napp = \"outer:app\"\n"
        )
        inner = tmp_path / "sub"
        inner.mkdir()
        (inner / "pyproject.toml").write_text(
            "[tool.spiderweb]\napp = \"inner:app\"\n"
        )
        monkeypatch.chdir(inner)
        assert _find_pyproject_app() == "inner:app"

    def test_returns_none_on_malformed_toml(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe not valid toml !!!")
        monkeypatch.chdir(tmp_path)
        assert _find_pyproject_app() is None

    def test_cli_uses_pyproject_app_when_no_flag_or_env(
        self, tmp_path, monkeypatch, capsys
    ):
        """main() should pick up app from pyproject.toml when --app / env absent."""
        app = _make_app()

        (tmp_path / "pyproject.toml").write_text(
            "[tool.spiderweb]\napp = \"fake:app\"\n"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SPIDERWEB_APP", raising=False)
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)

        main(["routes"])
        # No error — the app was resolved from pyproject.toml
        captured = capsys.readouterr()
        assert "error" not in captured.err

    def test_explicit_flag_overrides_pyproject(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.spiderweb]\napp = \"wrong:app\"\n"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SPIDERWEB_APP", raising=False)

        received = []
        monkeypatch.setattr(
            "spiderweb.cli._load_app", lambda spec: received.append(spec) or _make_app()
        )

        main(["--app", "correct:app", "routes"])
        assert received == ["correct:app"]

    def test_env_var_overrides_pyproject(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.spiderweb]\napp = \"wrong:app\"\n"
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SPIDERWEB_APP", "env:app")

        received = []
        monkeypatch.setattr(
            "spiderweb.cli._load_app", lambda spec: received.append(spec) or _make_app()
        )

        main(["routes"])
        assert received == ["env:app"]


# ---------------------------------------------------------------------------
# _read_pyproject_config
# ---------------------------------------------------------------------------


class TestReadPyprojectConfig:
    def test_returns_full_section(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.spiderweb]\napp = "mymod:app"\nasgi = true\n'
        )
        monkeypatch.chdir(tmp_path)
        cfg = _read_pyproject_config()
        assert cfg == {"app": "mymod:app", "asgi": True}

    def test_returns_empty_dict_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert _read_pyproject_config() == {}

    def test_returns_empty_dict_when_section_absent(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text("[tool.other]\nkey = 1\n")
        monkeypatch.chdir(tmp_path)
        assert _read_pyproject_config() == {}

    def test_returns_empty_dict_on_malformed_toml(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe bad toml")
        monkeypatch.chdir(tmp_path)
        assert _read_pyproject_config() == {}

    def test_asgi_false_by_default(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text('[tool.spiderweb]\napp = "a:b"\n')
        monkeypatch.chdir(tmp_path)
        assert _read_pyproject_config().get("asgi", False) is False


# ---------------------------------------------------------------------------
# serve: asgi flag from pyproject.toml
# ---------------------------------------------------------------------------


class TestServeAsgiFromPyproject:
    def test_asgi_default_true_when_set_in_pyproject(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.spiderweb]\napp = "fake:app"\nasgi = true\n'
        )
        monkeypatch.chdir(tmp_path)
        args, _ = _build_serve_parser(asgi_default=True).parse_known_args([])
        assert args.asgi is True

    def test_no_asgi_flag_overrides_pyproject_true(self):
        args, _ = _build_serve_parser(asgi_default=True).parse_known_args(["--no-asgi"])
        assert args.asgi is False

    def test_asgi_flag_explicit_still_works(self):
        args, _ = _build_serve_parser(asgi_default=False).parse_known_args(["--asgi"])
        assert args.asgi is True

    def test_main_passes_asgi_default_from_pyproject(self, tmp_path, monkeypatch):
        """main() should start ASGI when pyproject sets asgi=true, no --asgi flag needed."""
        app = _make_app()
        (tmp_path / "pyproject.toml").write_text(
            '[tool.spiderweb]\napp = "fake:app"\nasgi = true\n'
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SPIDERWEB_APP", raising=False)
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)

        started_asgi = []
        monkeypatch.setattr(app, "start_asgi", lambda blocking=True: started_asgi.append(True))

        main(["serve"])
        assert started_asgi == [True]

    def test_no_asgi_flag_overrides_pyproject_in_main(self, tmp_path, monkeypatch):
        """--no-asgi on the CLI overrides asgi=true in pyproject.toml."""
        app = _make_app()
        (tmp_path / "pyproject.toml").write_text(
            '[tool.spiderweb]\napp = "fake:app"\nasgi = true\n'
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SPIDERWEB_APP", raising=False)
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)

        started_wsgi = []
        monkeypatch.setattr(app, "start", lambda blocking=True: started_wsgi.append(True))

        main(["serve", "--no-asgi"])
        assert started_wsgi == [True]


# ---------------------------------------------------------------------------
# Parser structure
# ---------------------------------------------------------------------------


class TestParser:
    def test_serve_asgi_flag(self):
        args, _ = _build_serve_parser().parse_known_args(["--asgi"])
        assert args.asgi is True

    def test_serve_no_asgi_flag(self):
        args, _ = _build_serve_parser(asgi_default=True).parse_known_args(["--no-asgi"])
        assert args.asgi is False

    def test_serve_addr_and_port(self):
        args, _ = _build_serve_parser().parse_known_args(["--addr", "0.0.0.0", "--port", "9001"])
        assert args.addr == "0.0.0.0"
        assert args.port == 9001

    def test_serve_defaults_no_asgi(self):
        args, _ = _build_serve_parser().parse_known_args([])
        assert args.asgi is False
        assert args.addr is None
        assert args.port is None
