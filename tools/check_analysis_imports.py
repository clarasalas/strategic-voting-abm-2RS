#!/usr/bin/env python3
"""
Import every module under analysis/ and report the ones that fail.

The analysis scripts are not covered by the test suite as modules.  Most are
exercised only through the handful of functions the tests reach into, so a
broken import at the top of a script -- a renamed core_model symbol, a
dependency that is not actually installed, a stale path -- can sit there
undetected until someone runs the script months later.

This imports each one the way it is actually run: the script's own directory on
sys.path, plus the repository root so that ``core_model`` resolves.  Importing
must not do any work; every script guards its entry point behind
``if __name__ == "__main__"``, and a module that starts computing on import
will show up here as a very slow check rather than a failure, which is the
reason the per-module timing is printed.

Exit status is 0 when every module imports, 1 otherwise.

Usage
-----
    python tools/check_analysis_imports.py
"""

import importlib
import pathlib
import sys
import time
import traceback

REPO = pathlib.Path(__file__).resolve().parent.parent
ANALYSIS = REPO / "analysis"


def main() -> int:
    if not ANALYSIS.is_dir():
        print(f"no analysis/ directory at {ANALYSIS}", file=sys.stderr)
        return 1

    # Repository root first, so `import core_model.model` resolves without the
    # package needing to be pip-installed.
    sys.path.insert(0, str(REPO))

    modules = sorted(
        p for p in ANALYSIS.rglob("*.py") if "__pycache__" not in p.parts
    )
    if not modules:
        print(f"no modules found under {ANALYSIS}", file=sys.stderr)
        return 1

    failures = []
    for path in modules:
        rel = path.relative_to(REPO)
        # Each script's own directory, matching how the scripts import their
        # siblings when run directly.
        sys.path.insert(0, str(path.parent))
        start = time.perf_counter()
        try:
            importlib.import_module(path.stem)
        except BaseException:
            print(f"FAIL  {rel}")
            traceback.print_exc()
            failures.append(rel)
        else:
            print(f"ok    {rel}  ({time.perf_counter() - start:.2f}s)")

    print()
    print(f"{len(modules) - len(failures)}/{len(modules)} modules imported")
    if failures:
        print("failed:")
        for rel in failures:
            print(f"  {rel}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
