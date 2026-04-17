"""Tests for the spiderweb management CLI (spiderweb/cli.py)."""

from unittest.mock import patch

import pytest

from spiderweb.cli import (
    _build_serve_parser,
    _cmd_makemigrations,
    _cmd_migrate,
    _cmd_routes,
    _cmd_version,
    _ensure_migrations_dir,
    _find_pyproject_app,
    _get_migrations_dir,
    _load_app,
    _make_alembic_config,
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
# new command
# ---------------------------------------------------------------------------


class TestNewCommand:
    def test_scaffolds_files(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        from spiderweb.cli import _cmd_new

        _cmd_new(None, None, ["my_proj"])

        assert (tmp_path / "my_proj").is_dir()
        assert (tmp_path / "my_proj" / "app.py").is_file()
        assert (tmp_path / "my_proj" / "pyproject.toml").is_file()

        out = capsys.readouterr().out
        assert "Created app.py" in out
        assert "Created pyproject.toml" in out
        assert "Scaffolded new project" in out

    def test_skips_existing_files(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        from spiderweb.cli import _cmd_new

        proj = tmp_path / "my_proj"
        proj.mkdir()
        (proj / "app.py").write_text("existing")
        (proj / "pyproject.toml").write_text("[tool.spiderweb]\napp = 'my:app'")

        _cmd_new(None, None, ["my_proj"])

        assert (proj / "app.py").read_text() == "existing"

        out = capsys.readouterr().out
        assert "app.py already exists, skipping." in out
        assert "pyproject.toml already exists, skipping." in out

    def test_updates_existing_pyproject(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        from spiderweb.cli import _cmd_new

        proj = tmp_path / "my_proj"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[tool.other]\n")

        _cmd_new(None, None, ["my_proj"])

        content = (proj / "pyproject.toml").read_text()
        assert "[tool.other]" in content
        assert "[tool.spiderweb]" in content
        assert 'app = "app:app"' in content

        out = capsys.readouterr().out
        assert "Updated pyproject.toml with [tool.spiderweb] section" in out

    def test_current_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from spiderweb.cli import _cmd_new

        _cmd_new(None, None, ["."])

        assert (tmp_path / "app.py").is_file()
        assert (tmp_path / "pyproject.toml").is_file()


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

    def test_missing_app_for_serve_exits(self, capsys, monkeypatch):
        monkeypatch.setattr("spiderweb.cli._read_pyproject_config", lambda: {})
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
            '[tool.spiderweb]\napp = "mymod:myapp"\n'
        )
        monkeypatch.chdir(tmp_path)
        assert _find_pyproject_app() == "mymod:myapp"

    def test_returns_none_when_key_absent(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text('[tool.other]\nkey = "val"\n')
        monkeypatch.chdir(tmp_path)
        assert _find_pyproject_app() is None

    def test_returns_none_when_no_pyproject(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert _find_pyproject_app() is None

    def test_walks_up_to_find_pyproject(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text('[tool.spiderweb]\napp = "pkg:obj"\n')
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert _find_pyproject_app() == "pkg:obj"

    def test_closer_pyproject_wins(self, tmp_path, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.spiderweb]\napp = "outer:app"\n'
        )
        inner = tmp_path / "sub"
        inner.mkdir()
        (inner / "pyproject.toml").write_text('[tool.spiderweb]\napp = "inner:app"\n')
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

        (tmp_path / "pyproject.toml").write_text('[tool.spiderweb]\napp = "fake:app"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SPIDERWEB_APP", raising=False)
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)

        main(["routes"])
        # No error — the app was resolved from pyproject.toml
        captured = capsys.readouterr()
        assert "error" not in captured.err

    def test_explicit_flag_overrides_pyproject(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.spiderweb]\napp = "wrong:app"\n'
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
            '[tool.spiderweb]\napp = "wrong:app"\n'
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

    def test_wsgi_flag_overrides_pyproject_true(self):
        args, _ = _build_serve_parser(asgi_default=True).parse_known_args(["--wsgi"])
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
        monkeypatch.setattr(
            app, "start_asgi", lambda blocking=True: started_asgi.append(True)
        )

        main(["serve"])
        assert started_asgi == [True]

    def test_wsgi_flag_overrides_pyproject_in_main(self, tmp_path, monkeypatch):
        """--wsgi on the CLI overrides asgi=true in pyproject.toml."""
        app = _make_app()
        (tmp_path / "pyproject.toml").write_text(
            '[tool.spiderweb]\napp = "fake:app"\nasgi = true\n'
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SPIDERWEB_APP", raising=False)
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)

        started_wsgi = []
        monkeypatch.setattr(
            app, "start", lambda blocking=True: started_wsgi.append(True)
        )

        main(["serve", "--wsgi"])
        assert started_wsgi == [True]


# ---------------------------------------------------------------------------
# Parser structure
# ---------------------------------------------------------------------------


class TestParser:
    def test_serve_asgi_flag(self):
        args, _ = _build_serve_parser().parse_known_args(["--asgi"])
        assert args.asgi is True

    def test_serve_wsgi_flag(self):
        args, _ = _build_serve_parser(asgi_default=True).parse_known_args(["--wsgi"])
        assert args.asgi is False

    def test_serve_addr_and_port(self):
        args, _ = _build_serve_parser().parse_known_args(
            ["--addr", "0.0.0.0", "--port", "9001"]
        )
        assert args.addr == "0.0.0.0"
        assert args.port == 9001

    def test_serve_defaults_no_asgi(self):
        args, _ = _build_serve_parser().parse_known_args([])
        assert args.asgi is False
        assert args.addr is None
        assert args.port is None


# ---------------------------------------------------------------------------
# _ensure_migrations_dir / _get_migrations_dir
# ---------------------------------------------------------------------------


class TestMigrationsDir:
    def test_creates_directory_structure(self, tmp_path):
        migrations_dir = tmp_path / "migrations"
        _ensure_migrations_dir(migrations_dir)
        assert (migrations_dir / "versions").is_dir()
        assert (migrations_dir / "env.py").is_file()
        assert (migrations_dir / "script.py.mako").is_file()

    def test_does_not_overwrite_existing_env_py(self, tmp_path):
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "versions").mkdir()
        env_py = migrations_dir / "env.py"
        env_py.write_text("# custom content")
        mako = migrations_dir / "script.py.mako"
        mako.write_text("# custom mako")

        _ensure_migrations_dir(migrations_dir)

        assert env_py.read_text() == "# custom content"
        assert mako.read_text() == "# custom mako"

    def test_prints_message_on_first_run(self, tmp_path, capsys):
        _ensure_migrations_dir(tmp_path / "migrations")
        out = capsys.readouterr().out
        assert "Created migrations directory" in out

    def test_no_message_when_already_exists(self, tmp_path, capsys):
        migrations_dir = tmp_path / "migrations"
        _ensure_migrations_dir(migrations_dir)
        capsys.readouterr()  # clear first-run output
        _ensure_migrations_dir(migrations_dir)
        out = capsys.readouterr().out
        assert "Created migrations directory" not in out

    def test_get_migrations_dir_default(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _get_migrations_dir({})
        assert result == tmp_path / "migrations"

    def test_get_migrations_dir_custom(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _get_migrations_dir({"migrations_dir": "db/migrations"})
        assert result == tmp_path / "db" / "migrations"

    def test_get_migrations_dir_uses_pyproject_location(self, tmp_path, monkeypatch):
        """migrations/ should land next to pyproject.toml, not necessarily cwd."""
        (tmp_path / "pyproject.toml").write_text("[tool.spiderweb]\napp = 'a:b'\n")
        nested = tmp_path / "sub" / "dir"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        result = _get_migrations_dir({})
        assert result == tmp_path / "migrations"


# ---------------------------------------------------------------------------
# _make_alembic_config
# ---------------------------------------------------------------------------


class TestMakeAlembicConfig:
    def test_returns_config_with_script_location(self, tmp_path):
        app = _make_app()
        cfg = _make_alembic_config(app, tmp_path / "migrations")
        assert cfg.get_main_option("script_location") == str(tmp_path / "migrations")

    def test_returns_config_with_engine(self, tmp_path):
        app = _make_app()
        cfg = _make_alembic_config(app, tmp_path / "migrations")
        assert cfg.attributes["engine"] is app.db_engine

    def test_returns_config_with_sqlalchemy_url(self, tmp_path):
        app = _make_app()
        cfg = _make_alembic_config(app, tmp_path / "migrations")
        url = cfg.get_main_option("sqlalchemy.url")
        assert url is not None
        assert "sqlite" in url


# ---------------------------------------------------------------------------
# makemigrations command
# ---------------------------------------------------------------------------


class TestMakeMigrationsCommand:
    def _run(self, app, extra, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("alembic.command.revision") as mock_revision:
            _cmd_makemigrations(app, None, extra)
            return mock_revision

    def test_calls_alembic_revision_autogenerate(self, tmp_path, monkeypatch):
        app = _make_app()
        mock = self._run(app, [], tmp_path, monkeypatch)
        mock.assert_called_once()
        _, kwargs = mock.call_args
        assert kwargs["autogenerate"] is True

    def test_message_flag_passed_through(self, tmp_path, monkeypatch):
        app = _make_app()
        mock = self._run(app, ["-m", "add users"], tmp_path, monkeypatch)
        _, kwargs = mock.call_args
        assert kwargs["message"] == "add users"

    def test_empty_flag_disables_autogenerate(self, tmp_path, monkeypatch):
        app = _make_app()
        mock = self._run(app, ["--empty"], tmp_path, monkeypatch)
        _, kwargs = mock.call_args
        assert kwargs["autogenerate"] is False

    def test_scaffolds_migrations_dir_on_first_run(self, tmp_path, monkeypatch):
        app = _make_app()
        monkeypatch.chdir(tmp_path)
        with patch("alembic.command.revision"):
            _cmd_makemigrations(app, None, [])
        assert (tmp_path / "migrations" / "env.py").exists()

    def test_cli_dispatches_makemigrations(self, tmp_path, monkeypatch):
        app = _make_app()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)
        with patch("alembic.command.revision") as mock_revision:
            main(["--app", "fake:app", "makemigrations", "-m", "initial"])
        mock_revision.assert_called_once()


# ---------------------------------------------------------------------------
# migrate command
# ---------------------------------------------------------------------------


class TestMigrateCommand:
    def _run(self, app, extra, tmp_path, monkeypatch):
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        with (
            patch("alembic.command.upgrade") as mock_upgrade,
            patch("alembic.command.downgrade") as mock_downgrade,
            patch("alembic.command.stamp") as mock_stamp,
        ):
            _cmd_migrate(app, None, extra)
            return mock_upgrade, mock_downgrade, mock_stamp

    def test_defaults_to_upgrade_head(self, tmp_path, monkeypatch):
        app = _make_app()
        up, _, _ = self._run(app, [], tmp_path, monkeypatch)
        up.assert_called_once()
        assert up.call_args[0][1] == "head"

    def test_explicit_revision_upgrades(self, tmp_path, monkeypatch):
        app = _make_app()
        up, _, _ = self._run(app, ["abc123"], tmp_path, monkeypatch)
        up.assert_called_once()
        assert up.call_args[0][1] == "abc123"

    def test_zero_downgrades_to_base(self, tmp_path, monkeypatch):
        app = _make_app()
        _, down, _ = self._run(app, ["zero"], tmp_path, monkeypatch)
        down.assert_called_once()
        assert down.call_args[0][1] == "base"

    def test_base_downgrades(self, tmp_path, monkeypatch):
        app = _make_app()
        _, down, _ = self._run(app, ["base"], tmp_path, monkeypatch)
        down.assert_called_once()
        assert down.call_args[0][1] == "base"

    def test_negative_relative_downgrades(self, tmp_path, monkeypatch):
        app = _make_app()
        _, down, _ = self._run(app, ["-1"], tmp_path, monkeypatch)
        down.assert_called_once()
        assert down.call_args[0][1] == "-1"

    def test_fake_stamps_database(self, tmp_path, monkeypatch):
        app = _make_app()
        _, _, stamp = self._run(app, ["--fake"], tmp_path, monkeypatch)
        stamp.assert_called_once()
        assert stamp.call_args[0][1] == "head"

    def test_fake_zero_stamps_base(self, tmp_path, monkeypatch):
        app = _make_app()
        _, _, stamp = self._run(app, ["zero", "--fake"], tmp_path, monkeypatch)
        stamp.assert_called_once()
        assert stamp.call_args[0][1] == "base"

    def test_missing_migrations_dir_exits(self, tmp_path, monkeypatch, capsys):
        app = _make_app()
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            _cmd_migrate(app, None, [])
        assert exc.value.code == 1
        assert "makemigrations" in capsys.readouterr().err

    def test_cli_dispatches_migrate(self, tmp_path, monkeypatch):
        app = _make_app()
        (tmp_path / "migrations").mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("spiderweb.cli._load_app", lambda spec: app)
        with patch("alembic.command.upgrade") as mock_upgrade:
            main(["--app", "fake:app", "migrate"])
        mock_upgrade.assert_called_once()
