import unittest
from molotov.api import pick_scenario, scenario, _SCENARIO


class TestUtil(unittest.TestCase):
    def setUp(self):
        self.old = list(_SCENARIO)

    def tearDown(self):
        _SCENARIO[:] = self.old

    def test_pick_scenario(self):

        @scenario(10)
        def _one(self):
            pass

        @scenario(90)
        def _two(self):
            pass

        picked = [pick_scenario()[0].__name__ for i in range(100)]
        ones = len([f for f in picked if f == '_one'])
        self.assertTrue(ones < 20)
