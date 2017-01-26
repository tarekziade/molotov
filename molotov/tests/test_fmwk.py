import asyncio
from molotov.session import LoggedClientSession
from molotov.fmwk import step
from molotov.api import scenario
from molotov.tests.support import TestLoop, async_test


class TestFmwk(TestLoop):

    @async_test
    async def test_step(self, loop):
        res = []

        @scenario(0)
        def test_one(session):
            res.append('1')

        @scenario(100)
        def test_two(session):
            res.append('2')

        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream) as session:
            await step(session, False, False, False, stream)
            self.assertEqual(len(res), 1)
