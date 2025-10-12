import re
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except Exception:  # pragma: no cover
    print("tomllib is required (Python 3.11+) to run this script.", file=sys.stderr)
    raise

PYPROJECT = Path("pyproject.toml")
CONSTANTS = Path("spiderweb/constants.py")

if not PYPROJECT.exists():
    print("pyproject.toml not found", file=sys.stderr)
    sys.exit(1)
if not CONSTANTS.exists():
    print("spiderweb/constants.py not found", file=sys.stderr)
    sys.exit(1)

with PYPROJECT.open("rb") as f:
    data = tomllib.load(f)
version = data.get("project", {}).get("version")
if not version:
    print("Version not found in pyproject.toml", file=sys.stderr)
    sys.exit(1)

text = CONSTANTS.read_text(encoding="utf-8")
new_text = re.sub(
    r'(__version__\s*=\s*")([^"]+)(")',
    lambda m: f"{m.group(1)}{version}{m.group(3)}",
    text,
)
if text != new_text:
    CONSTANTS.write_text(new_text, encoding="utf-8")
    print(f"Updated spiderweb/constants.py to version {version}")
else:
    print("No update needed; versions already match")
