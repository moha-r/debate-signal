"""Run workflow contracts and persist their actual result, independent of model quality."""

import json
from pathlib import Path
import sys
import unittest


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover("tests", pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    destination = Path("results/expanded_audit/workflow_unit_checks.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({
        "tests_run": result.testsRun,
        "failures": [{"test": str(test), "traceback": trace} for test, trace in result.failures],
        "errors": [{"test": str(test), "traceback": trace} for test, trace in result.errors],
        "skipped": [{"test": str(test), "reason": reason} for test, reason in result.skipped],
        "passed": result.wasSuccessful(),
        "scope": "Deterministic test doubles validate session logic, alert decisions, preprocessing and rendering. These are not language-accuracy observations.",
    }, indent=2) + "\n")
    sys.exit(0 if result.wasSuccessful() else 1)
