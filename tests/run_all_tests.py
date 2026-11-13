"""Run every unittest test with a compact, grouped INF1103 Part 2 report.

Place this file at tests/run_all_tests.py and run from the project root:
    python -m tests.run_all_tests
    python -m tests.run_all_tests --details

No additional dependencies. Does not modify the existing tests or CI.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import time
import unittest


GROUPS = (
    "AI Manager",
    "IO Manager",
    "Logic Manager",
    "Data Manager",
    "Domain & Models",
    "Application & Integration",
    "Dashboard",
    "Other",
)


def group_for(test_id: str) -> str:
    if ".ai_manager_test." in test_id:
        return "AI Manager"
    if "test_io_manager" in test_id:
        return "IO Manager"
    if "test_logic_manager" in test_id or "test_facilities_logic_manager" in test_id:
        return "Logic Manager"
    if "test_data_repositories" in test_id or "test_facilities_data_manager_search" in test_id:
        return "Data Manager"
    if "test_hazard_report_domain" in test_id or "test_facility_summary_domain" in test_id:
        return "Domain & Models"
    if "test_application_workflow" in test_id or "test_facilities_workflow_integration" in test_id:
        return "Application & Integration"
    if "test_dashboard_extensions" in test_id or "test_background_export_service" in test_id:
        return "Dashboard"
    return "Other"


class GroupedResult(unittest.TestResult):
    """Track each test's outcome so the report can be grouped by component."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[str, str, str]] = []

    def _record(self, test: unittest.case.TestCase, outcome: str) -> None:
        self.records.append((group_for(test.id()), test.id(), outcome))

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        super().addSuccess(test)
        self._record(test, "PASS")

    def addFailure(self, test: unittest.case.TestCase, err: tuple) -> None:
        super().addFailure(test, err)
        self._record(test, "FAIL")

    def addError(self, test: unittest.case.TestCase, err: tuple) -> None:
        super().addError(test, err)
        self._record(test, "ERROR")

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self._record(test, "SKIP")

    def addExpectedFailure(self, test: unittest.case.TestCase, err: tuple) -> None:
        super().addExpectedFailure(test, err)
        self._record(test, "XFAIL")

    def addUnexpectedSuccess(self, test: unittest.case.TestCase) -> None:
        super().addUnexpectedSuccess(test)
        self._record(test, "XPASS")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run INF1103 tests with grouped results")
    parser.add_argument("--details", action="store_true", help="show all test names")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    suite = unittest.defaultTestLoader.discover(
        start_dir=str(root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(root),
    )

    result = GroupedResult()
    captured = StringIO()
    began = time.perf_counter()
    # Simulated Gemini failures in tests can print expected retry warnings.
    # Capture them, but show diagnostic output if the suite fails.
    with redirect_stdout(captured), redirect_stderr(captured):
        suite.run(result)
    elapsed = time.perf_counter() - began

    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for group, test_id, outcome in result.records:
        grouped[group].append((test_id, outcome))

    print("=" * 70)
    print(" INF1103 PART 2 | AUTOMATED TEST REPORT")
    print("=" * 70)
    print(f" Total executed : {result.testsRun}")
    print(f" Passed         : {sum(s == 'PASS' for _, _, s in result.records)}")
    print(f" Failures       : {len(result.failures)}")
    print(f" Errors         : {len(result.errors)}")
    print(f" Skipped        : {len(result.skipped)}")
    print(f" Duration       : {elapsed:.2f} seconds")
    print("-" * 70)
    print(" COMPONENT                         PASSED/TOTAL       RESULT")
    print("-" * 70)

    for group in GROUPS:
        items = grouped.get(group, [])
        if not items:
            continue
        passed = sum(outcome == "PASS" for _, outcome in items)
        status = "PASS" if passed == len(items) else "CHECK"
        print(f" {group:<34}{passed:>3}/{len(items):<3}             {status}")
        if args.details:
            for test_id, outcome in items:
                short_name = test_id.rsplit(".", 1)[-1]
                print(f"    {outcome:<5} {short_name}")
            print()

    print("=" * 70)
    success = result.wasSuccessful() and result.testsRun > 0
    print(f" FINAL RESULT: {'ALL TESTS PASSED' if success else 'TEST ISSUES FOUND'}")
    print("=" * 70)

    if not success:
        for heading, issues in (("FAILURES", result.failures), ("ERRORS", result.errors)):
            if issues:
                print(f"\n{heading}")
                for test, details in issues:
                    print(test.id())
                    print(details)
        if result.unexpectedSuccesses:
            print("\nUNEXPECTED SUCCESSES:")
            for test in result.unexpectedSuccesses:
                print(test.id())
        noisy = captured.getvalue().strip()
        if noisy:
            print("\nCAPTURED TEST OUTPUT (for debugging)")
            print(noisy[-12000:])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
