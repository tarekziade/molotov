from molotov.api import pick_scenario, scenario, get_scenarios, setup
from molotov.tests.support import TestLoop


class TestUtil(TestLoop):
    def test_pick_scenario(self):

        @scenario(10)
        async def _one(self):
            pass

        @scenario(90)
        async def _two(self):
            pass

        picked = [pick_scenario()[0].__name__ for i in range(100)]
        ones = len([f for f in picked if f == '_one'])
        self.assertTrue(ones < 20)

    def test_no_scenario(self):
        @scenario(0)
        async def _one(self):
            pass

        @scenario(0)
        async def _two(self):
            pass

        self.assertEqual(get_scenarios(), [])

    def test_scenario_not_coroutine(self):
        try:
            @scenario(1)
            def _one(self):
                pass
        except TypeError:
            return
        raise AssertionError("Should raise")

    def test_setup_not_coroutine(self):
        try:
            @setup()
            def _setup(self):
                pass

            @scenario(90)
            async def _two(self):
                pass
        except TypeError:
            return
        raise AssertionError("Should raise")
