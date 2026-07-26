"""
Import-smoke: import EVERY module under app/ (excluding _archive) and report
any that fail. Catches bad imports / undefined names at module scope that
py_compile misses (e.g. `from x import NameThatDoesNotExist`).

Run from backend/:
    python -m scripts.load.import_smoke
Exit code 1 if any module fails to import.
"""
import importlib
import os
import pkgutil
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_DIR = os.path.join(ROOT, "app")


def iter_modules():
    for dirpath, dirnames, filenames in os.walk(APP_DIR):
        if "_archive" in dirpath.replace("\\", "/").split("/"):
            continue
        dirnames[:] = [d for d in dirnames if d != "_archive" and d != "__pycache__"]
        for fn in filenames:
            if not fn.endswith(".py") or fn == "__init__.py":
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            mod = rel[:-3].replace(os.sep, ".")
            yield mod


def main() -> int:
    failures = []
    count = 0
    for mod in sorted(iter_modules()):
        count += 1
        try:
            importlib.import_module(mod)
        except Exception as e:  # noqa: BLE001 - we want every failure
            failures.append((mod, e, traceback.format_exc()))
            print(f"FAIL {mod}: {type(e).__name__}: {e}")

    print(f"\n--- imported {count} modules, {len(failures)} failed ---")
    if failures:
        print("\n===== FIRST TRACEBACK PER FAILURE =====")
        for mod, e, tb in failures:
            print(f"\n### {mod}\n{tb}")
        return 1
    print("ALL MODULES IMPORT CLEAN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
