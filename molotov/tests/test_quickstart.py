import tempfile
import unittest
import shutil
import sys
import os
import contextlib

from molotov import quickstart


class TestQuickStart(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _input(self, text):
        if 'Target directory' in text:
            return self.tempdir
        return 'y'

    @contextlib.contextmanager
    def set_args(self, *args):
        old = list(sys.argv)
        sys.argv[:] = args
        try:
            yield
        finally:
            sys.argv[:] = old

    def test_generate(self):
        quickstart._input = self._input

        with self.set_args('molostart'):
            quickstart.main()

        result = os.listdir(self.tempdir)
        result.sort()
        self.assertEqual(result, ['Makefile', 'loadtest.py', 'molotov.json'])

        # second runs stops
        with self.set_args('molostart'):
            try:
                quickstart.main()
                raise AssertionError()
            except SystemExit:
                pass
