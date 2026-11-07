# FILE GUIDE: Formatted offline test runner for the AI Manager.
# Discovers and executes AI assessment validation tests.
# Displays individual results and an overall test summary.
# Runs without requiring a live Gemini API connection.

"""Formatted offline test runner for AI Manager validation."""

import io
import sys
import time
import unittest
from pathlib import Path


# Locate the tests folder and project root automatically.
# This avoids hard-coding a specific computer directory.
TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent


# Human-readable descriptions for the seven validation tests.
TEST_LABELS = {
    "test_valid_direct_construction": "Valid assessment construction",
    "test_direct_construction_rejects_invalid_category": "Invalid category rejection",
    "test_direct_construction_rejects_invalid_severity": "Invalid severity rejection",
    "test_direct_construction_rejects_invalid_impact": "Invalid impact rejection",
    "test_direct_construction_rejects_blank_and_non_string": "Blank and non-string validation",
    "test_direct_construction_trims_whitespace": "Whitespace normalization",
    "test_from_mapping_rejects_extra_fields": "Unexpected schema fields rejection",
}


def collect_tests(suite):
    """Extract individual test cases from a nested unittest suite."""
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from collect_tests(item)
        else:
            yield item


def get_failed_test_ids(results):
    """Extract failed test IDs, including failures inside subtests."""
    failed_ids = set()

    for test, _ in results:
        # A failed subtest belongs to its parent test case.
        parent_test = getattr(test, "test_case", test)
        failed_ids.add(parent_test.id())

    return failed_ids


def main():
    """Execute AI Manager tests and display a formatted report."""

    # ----------------------------------------------------------
    # STEP 1: Discover AI Manager validation tests.
    # ----------------------------------------------------------
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TESTS_DIR),
        pattern="test_ai_assessment_validation.py",
        top_level_dir=str(PROJECT_ROOT),
    )

    tests = list(collect_tests(suite))

    # Capture standard unittest output.
    output = io.StringIO()

    # ----------------------------------------------------------
    # STEP 2: Execute the tests and measure execution time.
    # ----------------------------------------------------------
    start = time.perf_counter()

    result = unittest.TextTestRunner(
        stream=output,
        verbosity=2,
    ).run(suite)

    elapsed = time.perf_counter() - start

    # ----------------------------------------------------------
    # STEP 3: Collect test results.
    # ----------------------------------------------------------
    failures = get_failed_test_ids(result.failures)
    errors = get_failed_test_ids(result.errors)

    skipped = {
        test.id()
        for test, _ in result.skipped
    }

    expected_failures = get_failed_test_ids(
        result.expectedFailures
    )

    unexpected_successes = {
        test.id()
        for test in result.unexpectedSuccesses
    }

    # ----------------------------------------------------------
    # STEP 4: Display the formatted test report.
    # ----------------------------------------------------------
    width = 72

    print("\n" + "=" * width)
    print("INF1103 - AI MANAGER TEST REPORT".center(width))
    print("=" * width)

    print(f"{'NO.':<5} {'TEST CASE':<54} {'RESULT'}")
    print("-" * width)

    for number, test in enumerate(tests, start=1):
        test_id = test.id()

        name = TEST_LABELS.get(
            test._testMethodName,
            test._testMethodName.replace("_", " ").title(),
        )

        if test_id in errors:
            status = "ERROR"
        elif test_id in failures:
            status = "FAIL"
        elif test_id in unexpected_successes:
            status = "FAIL"
        elif test_id in skipped:
            status = "SKIP"
        elif test_id in expected_failures:
            status = "EXPECTED FAIL"
        else:
            status = "PASS"

        print(f"{number:<5} {name:<54} {status}")

    # ----------------------------------------------------------
    # STEP 5: Calculate the final summary.
    # ----------------------------------------------------------
    failed_count = len(result.failures) + len(
        result.unexpectedSuccesses
    )

    error_count = len(result.errors)
    skipped_count = len(result.skipped)
    expected_failure_count = len(result.expectedFailures)

    passed_count = (
        result.testsRun
        - failed_count
        - error_count
        - skipped_count
        - expected_failure_count
    )

    print("-" * width)

    print(f"Total Tests       : {result.testsRun}")
    print(f"Passed            : {passed_count}")
    print(f"Failed            : {failed_count}")
    print(f"Errors            : {error_count}")
    print(f"Skipped           : {skipped_count}")
    print(f"Expected Failures : {expected_failure_count}")
    print(f"Duration          : {elapsed:.3f} seconds")

    print("=" * width)

    # ----------------------------------------------------------
    # STEP 6: Display the overall result.
    # ----------------------------------------------------------
    success = result.wasSuccessful() and result.testsRun > 0

    if success:
        print("OVERALL RESULT: ALL AI MANAGER TESTS PASSED".center(width))
    else:
        print("OVERALL RESULT: TESTS FAILED".center(width))

        # Display original unittest details for troubleshooting.
        print("\nDetailed Test Results:")
        print(output.getvalue())

    print("=" * width + "\n")

    # Exit code 0 = successful; exit code 1 = failure.
    # This is useful when running the tests through GitHub Actions.
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
