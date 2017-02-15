import tempfile
import unittest
import shutil
import sys
import os

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

    def test_generate(self):
        quickstart._input = self._input
        old = list(sys.argv)
        sys.argv[:] = ['molostart']
        try:
            quickstart.main()
        finally:
            sys.argv[:] = old

        result = os.listdir(self.tempdir)
        result.sort()
        self.assertEqual(result, ['Makefile', 'loadtest.py', 'molotov.json'])
