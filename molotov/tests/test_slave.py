import os
import pytest
from unittest import mock
import tempfile
import subprocess
from shutil import copytree, copyfile

from molotov import __version__
from molotov.slave import main
from molotov.tests.support import TestLoop, dedicatedloop, set_args


_REPO = "https://github.com/loads/molotov"
NO_INTERNET = os.environ.get("NO_INTERNET") is not None
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CALLS = [0]


def check_call(cmd, *args, **kw):
    if CALLS[0] == 3:
        return
    if not cmd.startswith("git clone"):
        subprocess.check_call(cmd, *args, **kw)
    CALLS[0] += 1


@pytest.mark.skipif(NO_INTERNET, reason="This test requires internet access")
class TestSlave(TestLoop):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        copytree(os.path.join(ROOT, "molotov"), os.path.join(cls.dir, "molotov"))
        for f in ("setup.py", "molotov.json", "requirements.txt"):
            copyfile(os.path.join(ROOT, f), os.path.join(cls.dir, f))

    @dedicatedloop
    @mock.patch("molotov.slave.check_call", new=check_call)
    def test_main(self):
        with set_args("moloslave", _REPO, "test", "--directory", self.dir) as out:
            main()
        if os.environ.get("TRAVIS") is not None:
            return
        output = out[0].read()
        self.assertTrue("Preparing 1 worker..." in output, output)
        self.assertTrue("OK" in output, output)

    @dedicatedloop
    @mock.patch("molotov.slave.check_call", new=check_call)
    def test_fail(self):
        with set_args("moloslave", _REPO, "fail", "--directory", self.dir):
            self.assertRaises(Exception, main)

    @dedicatedloop
    @mock.patch("molotov.slave.check_call", new=check_call)
    def test_version(self):
        with set_args("moloslave", "--version", "--directory", self.dir) as out:
            try:
                main()
            except SystemExit:
                pass
        version = out[0].read().strip()
        self.assertTrue(version, __version__)
