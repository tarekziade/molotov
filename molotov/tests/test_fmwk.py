import unittest
import asyncio

from molotov.session import LoggedClientSession
from molotov.fmwk import step
from molotov.api import _SCENARIO, scenario


class TestFmwk(unittest.TestCase):
    def setUp(self):
        self.old = list(_SCENARIO)

    def tearDown(self):
        _SCENARIO[:] = self.old

    def test_step(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(True)

        @scenario(0)
        def test_one(session):
            pass

        @scenario(100)
        def test_two(session):
            pass

        async def _test_step():
            stream = asyncio.Queue()
            async with LoggedClientSession(loop, stream) as session:
                await step(session, False, False, False, stream)

        loop.run_until_complete(_test_step())
