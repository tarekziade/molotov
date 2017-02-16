import tempfile
import unittest
import shutil
import os

from molotov import quickstart
from molotov.tests.support import set_args


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

        with set_args('molostart'):
            quickstart.main()

        result = os.listdir(self.tempdir)
        result.sort()
        self.assertEqual(result, ['Makefile', 'loadtest.py', 'molotov.json'])

        # second runs stops
        with set_args('molostart'):
            try:
                quickstart.main()
                raise AssertionError()
            except SystemExit:
                pass
