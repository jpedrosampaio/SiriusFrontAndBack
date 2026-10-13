"""Benchmark guards fail before importing persistence or opening any connection."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class BenchmarkBoundary(unittest.TestCase):
    def test_remote_non_test_and_missing_opt_in_are_refused_without_database_access(self):
        script = Path(__file__).resolve().parents[2] / 'tools' / 'benchmark_integrated.py'
        for url, enabled in [('postgresql://test@example.test/sirius_test', 'true'),
                             ('postgresql://test@localhost/sirius', 'true'),
                             ('postgresql://test@localhost/sirius_test?host=example.test', 'true'),
                             ('postgresql://test@localhost/sirius_test', 'false')]:
            with self.subTest(url=url, enabled=enabled):
                result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                    env={**os.environ, 'RUN_POSTGRES_TESTS': enabled, 'HARDENING_TEST_DATABASE_URL': url}, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Refusing benchmark', result.stderr)
                self.assertNotIn(url, result.stderr)
