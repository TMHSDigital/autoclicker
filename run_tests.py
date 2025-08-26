#!/usr/bin/env python3
"""
Test runner for the autoclicker application
Runs unit tests with coverage reporting
"""

import sys
import os
import unittest
from unittest.loader import TestLoader

# Add current directory to path so we can import autoclicker package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_tests():
    """Run all unit tests"""
    print("Running autoclicker unit tests...")
    print("=" * 50)

    # Discover and run tests
    loader = TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), 'tests')
    suite = loader.discover(start_dir, pattern='test_*.py')

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")

    # Return success/failure code
    return 0 if (result.wasSuccessful()) else 1

def run_coverage():
    """Run tests with coverage reporting"""
    try:
        import coverage
        print("Running tests with coverage...")
        print("=" * 50)

        # Start coverage
        cov = coverage.Coverage(
            source=['autoclicker'],
            omit=['*/tests/*', '*/test_*.py', '*/__pycache__/*']
        )
        cov.start()

        # Run tests
        exit_code = run_tests()

        # Stop coverage and generate report
        cov.stop()
        cov.save()

        print("\nCoverage Report:")
        print("-" * 30)
        cov.report()

        # Generate HTML report
        cov.html_report(directory='htmlcov')
        print("\nHTML coverage report generated in 'htmlcov' directory")

        return exit_code

    except ImportError:
        print("Coverage module not installed. Install with: pip install coverage")
        return run_tests()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--coverage':
        exit_code = run_coverage()
    else:
        exit_code = run_tests()

    sys.exit(exit_code)
