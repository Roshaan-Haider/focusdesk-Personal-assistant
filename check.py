"""Run: python check.py. Finds missing functions/imports without starting the app."""
import importlib
import re
import sys
from pathlib import Path

from core.db import init_db

init_db()
ROOT = Path(__file__).parent
problems: list[str] = []

for mod in sorted(p.stem for p in (ROOT / "pages").glob("*.py") if p.stem != "__init__"):
    try:
        importlib.import_module(f"pages.{mod}")
    except Exception as e:  # noqa: BLE001
        problems.append(f"pages/{mod}.py failed to import: {e!r}")

from core import repository, services  # noqa: E402

aliases = {"repo": repository, "services": services}
files = list((ROOT / "pages").glob("*.py")) + list((ROOT / "core").glob("*.py")) + [ROOT / "main.py"]
for f in files:
    text = f.read_text(encoding="utf-8")
    for alias, module in aliases.items():
        for name in sorted(set(re.findall(rf"\b{alias}\.(\w+)\(", text))):
            if not hasattr(module, name):
                problems.append(f"{f.relative_to(ROOT)} calls {alias}.{name}() but it doesn't exist")

if problems:
    print("PROBLEMS FOUND:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("All good: every page imports and every repo/services function exists.")