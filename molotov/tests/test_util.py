from io import StringIO
from tempfile import mkstemp
import json
import unittest
import os
from molotov.util import expand_options, OptionError, set_var, get_var, _VARS


_HERE = os.path.dirname(__file__)
config = os.path.join(_HERE, "..", "..", "molotov.json")


class Args:
    pass


class TestUtil(unittest.TestCase):
    def setUp(self):
        super(TestUtil, self).setUp()
        _VARS.clear()

    def test_config(self):
        args = Args()
        expand_options(config, "test", args)
        self.assertEqual(args.duration, 1)

    def _get_config(self, data):
        data = json.dumps(data)
        data = StringIO(data)
        data.seek(0)
        return data

    def test_bad_config(self):
        args = Args()
        fd, badfile = mkstemp()
        os.close(fd)

        with open(badfile, "w") as f:
            f.write("'1")

        try:
            self.assertRaises(OptionError, expand_options, badfile, "", args)
        finally:
            os.remove(badfile)

        self.assertRaises(OptionError, expand_options, 1, "", args)
        self.assertRaises(OptionError, expand_options, "", "", args)

        bad_data = [
            ({}, "test"),
            ({"molotov": {}}, "test"),
            ({"molotov": {"tests": {}}}, "test"),
        ]

        for data, scenario in bad_data:
            self.assertRaises(
                OptionError, expand_options, self._get_config(data), scenario, args
            )

    def test_setget_var(self):
        me = object()
        set_var("me", me)
        self.assertTrue(get_var("me") is me)

    def test_get_var_factory(self):
        me = object()

        def factory():
            return me

        self.assertTrue(get_var("me", factory) is me)
