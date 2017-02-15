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

    def _prompt(self, text, validator=None, default=None):
        if text.startswith('Target'):
            return self.tempdir
        return True

    def test_generate(self):
        quickstart._prompt = self._prompt
        old = list(sys.argv)
        sys.argv[:] = ['molostart']
        try:
            quickstart.main()
        finally:
            sys.argv[:] = old

        result = os.listdir(self.tempdir)
        result.sort()
        self.assertEqual(result, ['Makefile', 'loadtest.py', 'molotov.json'])
