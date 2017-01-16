import unittest
from molotov.fmwk import scenario, _pick_scenario


class TestFmwk(unittest.TestCase):

    def test_weights(self):

        @scenario(0)
        def test_one(session):
            pass

        @scenario(100)
        def test_two(session):
            pass

        for i in range(10):
            func, args, kw = _pick_scenario()
            self.assertTrue(func.__name__ is 'test_two', func)
