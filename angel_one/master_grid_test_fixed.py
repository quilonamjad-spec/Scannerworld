"""
Compatibility runner for the Angel One Master Grid experiment.

The existing master_grid_test.py imports several scanner directories onto
sys.path. Scanner 1 and Scanner 2 both expose a module named indicators, so
Python can resolve the wrong one. This runner leaves the original experiment
unchanged and loads Scanner 1's indicators under a private module name before
executing the existing test source.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
ORIGINAL = HERE / "master_grid_test.py"
SCANNER1_INDICATORS = HERE.parent / "scanner1" / "indicators.py"


def load_scanner1_build_result():
    spec = importlib.util.spec_from_file_location(
        "scanner1_indicators_bridge",
        SCANNER1_INDICATORS,
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load Scanner 1 indicators from {SCANNER1_INDICATORS}"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_result


def main():
    source = ORIGINAL.read_text(encoding="utf-8")

    old_import = (
        "from indicators import build_result as scanner1_build_result"
    )

    new_import = """\n# Scanner 1 must be loaded by file path because Scanner 2 also has\n# an indicators.py module. The original experiment's remaining imports\n# are intentionally left unchanged.\nscanner1_build_result = load_scanner1_build_result()\n"""

    if old_import not in source:
        raise RuntimeError(
            "master_grid_test.py no longer contains the expected Scanner 1 import."
        )

    source = source.replace(old_import, new_import, 1)

    namespace = {
        "__name__": "__main__",
        "__file__": str(ORIGINAL),
        "__package__": "angel_one",
        "load_scanner1_build_result": load_scanner1_build_result,
    }

    exec(
        compile(source, str(ORIGINAL), "exec"),
        namespace,
    )


if __name__ == "__main__":
    main()
