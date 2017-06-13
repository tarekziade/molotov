from molotov.api import pick_scenario, scenario, get_scenarios, setup
from molotov.tests.support import TestLoop, async_test


class TestUtil(TestLoop):
    def test_pick_scenario(self):

        @scenario(weight=10)
        async def _one(self):
            pass

        @scenario(weight=90)
        async def _two(self):
            pass

        picked = [pick_scenario()[1].__name__ for i in range(100)]
        ones = len([f for f in picked if f == '_one'])
        self.assertTrue(ones < 20)

    @async_test
    async def test_can_call(self, loop):
        @setup()
        async def _setup(self):
            pass

        @scenario(weight=10)
        async def _one(self):
            pass

        # can still be called
        await _one(self)

        # same for fixtures
        await _setup(self)

    def test_default_weight(self):
        @scenario()
        async def _default_weight(self):
            pass

        self.assertEqual(len(get_scenarios()), 1)
        self.assertEqual(get_scenarios()[0][0], 1)

    def test_no_scenario(self):
        @scenario(weight=0)
        async def _one(self):
            pass

        @scenario(weight=0)
        async def _two(self):
            pass

        self.assertEqual(get_scenarios(), [])

    def test_scenario_not_coroutine(self):
        try:
            @scenario(weight=1)
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

            @scenario(weight=90)
            async def _two(self):
                pass
        except TypeError:
            return
        raise AssertionError("Should raise")

    def test_two_fixtures(self):
        try:
            @setup()
            async def _setup(self):
                pass

            @setup()
            async def _setup2(self):
                pass

            @scenario(weight=90)
            async def _two(self):
                pass
        except ValueError:
            return
        raise AssertionError("Should raise")
