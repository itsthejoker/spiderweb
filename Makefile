.PHONY: test pretty bump-patch bump-minor bump-major docs

# Run the test suite
test:
	uv run python -m pytest

# Lint and format the codebase
pretty:
	uv run ruff check --fix .
	uv run black .

# Bump versions and keep spiderweb/constants.py in sync with pyproject.toml
bump-patch:
	uv version --bump patch

bump-minor:
	uv version --bump minor

bump-major:
	uv version --bump major

docs:
	@retype --version >/dev/null 2>&1 || npm i retype-cli -g
	@retype start
