"""Run INF1103 application workflow tests with a clear, grouped report.

Place at tests/run_application_tests.py and run from the project root:
    python -m tests.run_application_tests
    python -m tests.run_application_tests --details

Only Python's standard library is required. Existing tests are unchanged.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import time
import unittest


GROUPS = {
    "ApplicationWorkflowTests": "Application Workflow",
    "MainEntryPointTests": "Main Entry Point",
}


class SummaryResult(unittest.TestResult):
    """Track outcomes without dumping a test-by-test log to the terminal."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[str, str, str]] = []

    def _add(self, test: unittest.case.TestCase, status: str) -> None:
        group = GROUPS.get(type(test).__name__, type(test).__name__)
        self.records.append((group, test._testMethodName, status))

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        super().addSuccess(test)
        self._add(test, "PASS")

    def addFailure(self, test: unittest.case.TestCase, err: tuple) -> None:
        super().addFailure(test, err)
        self._add(test, "FAIL")

    def addError(self, test: unittest.case.TestCase, err: tuple) -> None:
        super().addError(test, err)
        self._add(test, "ERROR")

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self._add(test, "SKIP")

    def addExpectedFailure(self, test: unittest.case.TestCase, err: tuple) -> None:
        super().addExpectedFailure(test, err)
        self._add(test, "XFAIL")

    def addUnexpectedSuccess(self, test: unittest.case.TestCase) -> None:
        super().addUnexpectedSuccess(test)
        self._add(test, "XPASS")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run application integration tests with a clean report")
    parser.add_argument("--details", action="store_true", help="show each test name and its result")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_application_workflow")
    result = SummaryResult()
    captured = StringIO()
    start = time.perf_counter()

    # The mocked bad-backend/corrupt-storage tests intentionally print startup
    # errors. Hide those messages only when tests pass; preserve them on failure.
    with redirect_stdout(captured), redirect_stderr(captured):
        suite.run(result)

    duration = time.perf_counter() - start
    grouped = defaultdict(list)
    for group, name, outcome in result.records:
        grouped[group].append((name, outcome))

    passed = sum(outcome == "PASS" for _, _, outcome in result.records)
    width = 67
    print("=" * width)
    print(" INF1103 PART 2 | APPLICATION INTEGRATION TEST REPORT")
    print("=" * width)
    print(f" Total tests  : {result.testsRun}")
    print(f" Passed       : {passed}")
    print(f" Failed       : {len(result.failures)}")
    print(f" Errors       : {len(result.errors)}")
    print(f" Skipped      : {len(result.skipped)}")
    print(f" Duration     : {duration:.3f} seconds")
    print("-" * width)
    print(f" {'TEST GROUP':<30} {'PASSED / TOTAL':<19} RESULT")
    print("-" * width)
    for group in ("Application Workflow", "Main Entry Point"):
        cases = grouped.get(group, [])
        if not cases:
            continue
        num_passed = sum(status == "PASS" for _, status in cases)
        outcome = "PASS" if num_passed == len(cases) else "CHECK"
        print(f" {group:<30} {f'{num_passed}/{len(cases)}':<19} {outcome}")
        if args.details:
            for name, status in cases:
                label = name.removeprefix("test_").replace("_", " ")
                print(f"   [{status:<5}] {label}")
            print()
    print("=" * width)
    ok = result.wasSuccessful() and result.testsRun > 0
    print(" FINAL RESULT: " + ("ALL APPLICATION TESTS PASSED" if ok else "APPLICATION TEST ISSUES FOUND"))
    print("=" * width)

    if not ok:
        for label, items in (("FAILURES", result.failures), ("ERRORS", result.errors)):
            for test, traceback in items:
                print(f"\n{label}: {test.id()}\n{traceback}")
        if result.unexpectedSuccesses:
            print("\nUNEXPECTED SUCCESSES:")
            for test in result.unexpectedSuccesses:
                print(test.id())
        if captured.getvalue().strip():
            print("\nCAPTURED TEST OUTPUT:")
            print(captured.getvalue()[-8000:])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
