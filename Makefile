.PHONY: test pretty bump-patch bump-minor bump-major update-constants-version

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
	$(MAKE) update-constants-version

bump-minor:
	uv version --bump minor
	$(MAKE) update-constants-version

bump-major:
	uv version --bump major
	$(MAKE) update-constants-version

# Sync __version__ in spiderweb/constants.py to the version in pyproject.toml
update-constants-version:
	uv run python tools/update_version.py
