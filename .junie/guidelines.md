Spiderweb framework — Development Guidelines

0) What is this?
Spiderweb is a minimalist Python web framework that blends Django- and Flask-like patterns. It provides function-based views, routing (Flask-style and Django-style, with variable converters), middleware, templating (Jinja2), static files, cookies, sessions, CSRF and CORS middleware, optional Pydantic validation, and a simple built-in WSGI dev server. The codebase targets Python 3.11–3.13.

1) Build/Configuration Instructions
- Supported Python: 3.11–3.13 (see pyproject.toml). The library itself has minimal runtime deps (peewee, jinja2, cryptography, email-validator, pydantic). Dev tooling uses pytest, hypothesis, coverage, ruff, black.
- Dependency management:
  - With Poetry (recommended):
    - Install: poetry install
    - Run commands: poetry run python -m spiderweb (if you expose an entry point) or poetry run python example.py
  - Without Poetry:
    - Create venv and install: python -m venv .venv && .venv\Scripts\activate (Windows) or source .venv/bin/activate (POSIX); then pip install -e .[dev]
      Note: If extras aren’t configured, pip install -e . and then pip install the dev tools you need (pytest, coverage, black, ruff).

- Running an example app:
  - Minimal app:
    from spiderweb import SpiderwebRouter
    from spiderweb.response import HttpResponse

    app = SpiderwebRouter(append_slash=True)

    @app.route("/")
    def index(request):
        return HttpResponse("HELLO, WORLD!")

    if __name__ == "__main__":
        app.start()
  - Alternatively, run the provided examples: python example.py or python example2.py.

- Configuration surface (high-signal items; see SpiderwebRouter.__init__ in spiderweb/main.py):
  - append_slash: If True, auto-redirects /path to /path/ with 301/302 semantics in tests. This affects route matching; be explicit in tests.
  - templates_dirs: List of directories for Jinja2 FileSystemLoader. Required for TemplateResponse with template paths.
  - staticfiles_dirs/static_url: Configure static files serving.
  - allowed_hosts: List or regex patterns for host checking.
  - CORS: cors_* options mirror standard CORS settings, with sane defaults (see constants.py and main.py for defaults and behavior).
  - Sessions/CSRF: session_* options define cookie properties and expiry; CSRF relies on session middleware (ordering matters; see below).
  - DB: pass a Peewee Database (defaults to a local Sqlite file during tests via helpers.setup()).

2) Testing Information
- Test runner: pytest (configured in pyproject.toml; addopts sets --maxfail=2 -rf).
  - Run all tests: python -m pytest
  - Quiet mode: python -m pytest -q
  - Run a subset by keyword: python -m pytest -k some_keyword
  - Run a specific file (note: when shell path resolution is finicky, prefer -k):
    - python -m pytest -k test_function_name

- Coverage:
  - Run: python -m coverage run -m pytest
  - Report: python -m coverage report -m
  - Omit rules: configured in pyproject.toml; conftest.py and spiderweb/tests/* are omitted from coverage.

- Project-specific fixtures/helpers:
  - conftest.py defines a session-scoped autouse fixture that deletes spiderweb-tests.db before and after the test session. Do not rely on persistent data between tests.
  - spiderweb.tests.helpers.setup() returns (app, environ, start_response):
    - app is a SpiderwebRouter with a default SqliteDatabase("spiderweb-tests.db").
    - environ is a WSGI environ seeded via wsgiref.util.setup_testing_defaults.
    - start_response is a helper capturing status and headers.
  - Use this to simulate WSGI calls without a real server.

- Adding new tests:
  - Place tests under spiderweb/tests, named test_*.py; standard pytest discovery applies.
  - Use separate files to manage tests by topic. Do not group unrelated tests under a single file.
  - Prefer black/ruff-compliant style; avoid side effects that depend on execution order.
  - For routes, define them on a local SpiderwebRouter instance inside the test to avoid cross-test pollution.
  - Example pattern:
    from spiderweb.response import HttpResponse
    from spiderweb.tests.helpers import setup

    def test_example():
        app, environ, start_response = setup()

        @app.route("/ping")
        def ping(request):
            return HttpResponse("pong")

        environ["PATH_INFO"] = "/ping"
        environ["REQUEST_METHOD"] = "GET"

        body_iter = app(environ, start_response)
        assert start_response.status.startswith("200")
        assert b"".join(body_iter) == b"pong"

- Demo test flow (validated during guideline creation):
  - A temporary test using helpers.setup() and a trivial route was created, executed with python -m pytest -k minimal_route_responds_200 (1 test passed), then removed. This demonstrates the idiomatic testing flow for this codebase.

3) Additional Development Information
- Code style and tooling:
  - Black (24.8+) and Ruff are configured; run ruff check . and black . to lint/format. CI expects black formatting; badges in README indicate Black usage.
  - Keep functions small and explicit; favor pure functions for components that can be tested without I/O.

- Middleware ordering and constraints (important):
  - Session middleware must run before CSRF middleware. Instantiating CSRF without Session middleware, or ordering CSRF above Session, raises configuration errors (see tests in spiderweb/tests/test_middleware.py).
  - GZip middleware has a minimum response length threshold (gzip_minimum_response_length) and will skip small payloads; tests assert that tiny responses are not compressed.
  - CORS middleware honors allow lists, regexes, and credentials flags; ensure preflight (OPTIONS) and actual requests align with cors_allow_methods/headers.

- Routing tips:
  - You can mix Flask-style decorators (@app.route("/path")) and Django-style mappings; variable URLs use converters defined in converters.py.
  - append_slash=True triggers redirects to slash-suffixed routes; tests may expect a 301/302 with Location header.
  - Error routes can be overridden via error_routes={code: view} when constructing SpiderwebRouter.

- Responses:
  - HttpResponse defaults content-type to text/html; JsonResponse forces application/json and serializes data via json.dumps.
  - TemplateResponse requires either template_path or template_string; if using template_path, ensure templates_dirs is set on the router so the loader can resolve the template.
  - FileResponse sets content-type via mimetypes and streams body as bytes via wsgiref FileWrapper.

- Database:
  - spiderweb.db exposes SpiderwebModel. When using a custom Peewee database, pass it into SpiderwebRouter(db=...). In tests, a throwaway Sqlite DB is used via helpers.setup.

- Debugging tips:
  - Use the StartResponse helper to inspect status and headers easily: dict(start_response.get_headers()).
  - Examine SpiderwebRouter.prepare_and_fire_response and fire_response for how headers/body are constructed when troubleshooting.
  - Host validation (allowed_hosts) happens per-request; misconfigurations will yield 400/403 depending on tests.

- Windows/WSL notes:
  - Paths in docs/tests often assume POSIX; when invoking pytest from Windows shells, prefer selecting tests by -k rather than path strings to avoid escaping issues.
  - The project runs fine under WSL; database file paths are relative to the CWD (see spiderweb-tests.db in conftest).

- Releases and versioning:
  - Version is sourced from spiderweb/constants.py and surfaced via __version__ in spiderweb/__init__.py; the makefile is configured to update it.

4) Quick checklist for contributors
- Ensure new middleware documents ordering requirements and provides clear config errors if preconditions aren’t met.
- Add tests for:
  - Success and failure paths
  - Edge cases (empty bodies, small vs large responses for GZip, invalid cookie attributes)
  - Redirect and header semantics (Location, Set-Cookie, Content-Type)
- Run: python -m pytest and, optionally, coverage to keep coverage high.
- Keep temporary files out of the repo; tests should not write outside the project root and should clean up after themselves.
