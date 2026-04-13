"""
Spiderweb management CLI — the equivalent of Django's manage.py.

Usage::

    spiderweb [--app MODULE:ATTR] COMMAND [options]

The ``--app`` value is resolved in this order (first match wins):

1. ``--app MODULE:ATTR`` flag passed on the command line.
2. ``SPIDERWEB_APP`` environment variable.
3. ``app`` key inside a ``[tool.spiderweb]`` section of the nearest
   ``pyproject.toml`` found by walking up from the current directory::

       [tool.spiderweb]
       app = "myapp:app"
       asgi = true   # makes `serve` default to ASGI mode

Built-in commands
-----------------
``version``
    Print the spiderweb-framework version and exit.  Does not need ``--app``.

``serve``
    Start the development server (WSGI by default; ``--asgi`` for ASGI mode,
    ``--wsgi`` to force WSGI when ``asgi=true`` is set in pyproject.toml).
    Optional ``--addr`` and ``--port`` override the values stored in the app.

``shell``
    Drop into an interactive Python interpreter with the app pre-loaded as the
    variable ``app``.  Uses IPython if available, otherwise stdlib ``code``.

``routes``
    Print a table of every registered URL route.

``check``
    Re-run all middleware startup checks and report pass/fail.

Custom commands
---------------
Register project-specific management commands with the ``@app.command()``
decorator::

    @app.command("seed")
    def seed_database(app, args, extra):
        with app.get_db_session() as session:
            ...

Then call them with::

    spiderweb --app mymodule:app seed
"""

import argparse
import importlib
import os
import pathlib
import sys
import tomllib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spiderweb.main import SpiderwebRouter


# ---------------------------------------------------------------------------
# pyproject.toml discovery
# ---------------------------------------------------------------------------


def _read_pyproject_config() -> dict:
    """Return the ``[tool.spiderweb]`` section from the nearest ``pyproject.toml``.

    Walks up from the current working directory until the filesystem root is
    reached.  Returns an empty dict if no file is found, the section is absent,
    or the file cannot be parsed.
    """
    directory = pathlib.Path.cwd()
    while True:
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            try:
                with candidate.open("rb") as fh:
                    data = tomllib.load(fh)
                return data.get("tool", {}).get("spiderweb", {})
            except Exception:
                return {}
        parent = directory.parent
        if parent == directory:
            return {}
        directory = parent


def _find_pyproject_app() -> str | None:
    """Return the ``[tool.spiderweb] app`` value from the nearest pyproject.toml."""
    return _read_pyproject_config().get("app")


# ---------------------------------------------------------------------------
# App loader
# ---------------------------------------------------------------------------


def _load_app(app_spec: str) -> "SpiderwebRouter":
    """Import and return a ``SpiderwebRouter`` from a ``'module:attr'`` spec."""
    if ":" not in app_spec:
        print(
            f"error: --app must be in 'module:attribute' format, got '{app_spec}'",
            file=sys.stderr,
        )
        sys.exit(1)

    module_path, attr = app_spec.rsplit(":", 1)

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        print(
            f"error: could not import module '{module_path}': {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not hasattr(module, attr):
        print(
            f"error: module '{module_path}' has no attribute '{attr}'",
            file=sys.stderr,
        )
        sys.exit(1)

    return getattr(module, attr)


# ---------------------------------------------------------------------------
# Built-in command implementations
# ---------------------------------------------------------------------------


def _cmd_version(_app, _args, _extra):
    from spiderweb.constants import __version__

    print(f"spiderweb-framework {__version__}")


def _cmd_serve(app, args, _extra):
    if args.addr:
        app.addr = args.addr
        app.server_address = (app.addr, app.port)
    if args.port:
        app.port = args.port
        app.server_address = (app.addr, app.port)
    if args.asgi:
        app.start_asgi(blocking=True)
    else:
        app.start(blocking=True)


def _cmd_shell(app, _args, _extra):
    import code as _code

    from spiderweb.constants import __version__

    banner = (
        f"Spiderweb {__version__} shell\n"
        "Available names: app\n"
        'Type "exit()" or Ctrl-D to quit.\n'
    )
    local_vars = {"app": app}

    try:
        import IPython  # type: ignore[import]

        IPython.start_ipython(argv=[], user_ns=local_vars)
    except ImportError:
        _code.interact(banner=banner, local=local_vars, exitmsg="")


def _cmd_routes(app, _args, _extra):
    routes = app._routes
    if not routes:
        print("No routes registered.")
        return

    rows = []
    for _pattern, data in routes.items():
        path = data.get("reverse", "")
        methods = ", ".join(data.get("allowed_methods") or [])
        name = data.get("name") or ""
        func = data.get("func")
        view = getattr(func, "__name__", repr(func))
        rows.append((path, methods, name, view))

    # Column widths (at least as wide as the header label)
    path_w = max(len("path"), *(len(r[0]) for r in rows))
    method_w = max(len("methods"), *(len(r[1]) for r in rows))
    name_w = max(len("name"), *(len(r[2]) for r in rows))
    view_w = max(len("view"), *(len(r[3]) for r in rows))

    sep = "-" * (path_w + method_w + name_w + view_w + 6)
    header = (
        f"{'path':<{path_w}}  {'methods':<{method_w}}  "
        f"{'name':<{name_w}}  {'view':<{view_w}}"
    )
    print(header)
    print(sep)
    for path, methods, name, view in sorted(rows, key=lambda r: r[0]):
        print(
            f"{path:<{path_w}}  {methods:<{method_w}}  "
            f"{name:<{name_w}}  {view:<{view_w}}"
        )


def _cmd_check(app, _args, _extra):
    app.run_middleware_checks()
    print("System check passed.")


# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------

_BUILTIN_COMMANDS: dict[str, callable] = {
    "version": _cmd_version,
    "serve": _cmd_serve,
    "shell": _cmd_shell,
    "routes": _cmd_routes,
    "check": _cmd_check,
}


# ---------------------------------------------------------------------------
# Argument parsers
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return the full help parser (for ``--help`` and usage display)."""
    parser = argparse.ArgumentParser(
        prog="spiderweb",
        description="Spiderweb framework management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Set SPIDERWEB_APP in your environment to avoid passing --app every time.\n"
            "\nExamples:\n"
            "  spiderweb version\n"
            "  spiderweb --app myapp:app serve\n"
            "  spiderweb --app myapp:app serve --asgi --port 9000\n"
            "  spiderweb --app myapp:app shell\n"
            "  spiderweb --app myapp:app routes\n"
            "  spiderweb --app myapp:app check\n"
        ),
    )
    parser.add_argument(
        "--app",
        metavar="MODULE:ATTR",
        default=os.environ.get("SPIDERWEB_APP"),
        help=(
            "App to use, as 'module:attribute' (e.g. myapp:app). "
            "Falls back to SPIDERWEB_APP env var, then [tool.spiderweb] app "
            "in the nearest pyproject.toml."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        metavar="COMMAND",
        help="Command to run (version, serve, shell, routes, check, or a custom command)",
    )
    return parser


def _build_serve_parser(asgi_default: bool = False) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spiderweb serve", add_help=False)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--asgi",
        dest="asgi",
        action="store_true",
        help="Use ASGI mode via uvicorn.",
    )
    mode.add_argument(
        "--wsgi",
        dest="asgi",
        action="store_false",
        help="Force WSGI mode even when asgi=true is set in pyproject.toml.",
    )
    p.set_defaults(asgi=asgi_default)
    p.add_argument(
        "--addr",
        metavar="ADDR",
        help="Bind address (overrides the value stored in the app)",
    )
    p.add_argument(
        "--port",
        metavar="PORT",
        type=int,
        help="Port number (overrides the value stored in the app)",
    )
    return p


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv=None):
    # Read pyproject.toml once so both --app and serve's asgi_default can use it.
    pyproject = _read_pyproject_config()

    # Stage 1: extract --app and the bare command name; leave the rest for the
    # command-specific parser so that e.g. ``serve --asgi`` works without
    # argparse rejecting ``--asgi`` at the top level.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument(
        "--app",
        default=os.environ.get("SPIDERWEB_APP") or pyproject.get("app"),
    )
    pre.add_argument("command", nargs="?")
    pre_args, remaining = pre.parse_known_args(argv)

    command = pre_args.command

    if not command:
        _build_parser().print_help()
        sys.exit(0)

    # `version` is the only command that doesn't need an app.
    if command == "version":
        _cmd_version(None, pre_args, remaining)
        return

    if not pre_args.app:
        print(
            "error: --app is required (or set SPIDERWEB_APP). "
            "Example: spiderweb --app mymodule:app serve",
            file=sys.stderr,
        )
        sys.exit(1)

    app = _load_app(pre_args.app)

    # Built-in commands (parse their own flags from *remaining*)
    if command == "serve":
        asgi_default = bool(pyproject.get("asgi", False))
        serve_args, extra = _build_serve_parser(asgi_default).parse_known_args(remaining)
        _cmd_serve(app, serve_args, extra)
        return

    if command in _BUILTIN_COMMANDS:
        _BUILTIN_COMMANDS[command](app, pre_args, remaining)
        return

    # User-defined management commands registered via @app.command()
    user_cmds: dict = getattr(app, "_management_commands", {})
    if command in user_cmds:
        user_cmds[command](app, pre_args, remaining)
        return

    print(f"error: unknown command '{command}'", file=sys.stderr)
    _build_parser().print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
