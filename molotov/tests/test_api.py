from molotov.api import pick_scenario, scenario
from molotov.tests.support import TestLoop


class TestUtil(TestLoop):
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
