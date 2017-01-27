import asyncio
from collections import namedtuple

from molotov.session import LoggedClientSession
from molotov.fmwk import step, worker
from molotov.api import scenario
from molotov.tests.support import TestLoop, async_test


class TestFmwk(TestLoop):

    @async_test
    async def test_step(self, loop):
        res = []

        @scenario(0)
        async def test_one(session):
            res.append('1')

        @scenario(100)
        async def test_two(session):
            res.append('2')

        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream) as session:
            await step(session, False, False, False, stream)
            self.assertEqual(len(res), 1)

    @async_test
    async def test_worker(self, loop):

        @scenario(0)
        async def test_one(session):
            pass

        @scenario(100)
        async def test_two(session):
            pass

        results = {'OK': 0, 'FAILED': 0}
        stream = asyncio.Queue()
        args = namedtuple('args', 'verbose quiet duration exception')
        args.verbose = True
        args.quiet = False
        args.duration = 1
        args.exception = True

        await worker(loop, results, args, stream)
        self.assertTrue(results['OK'] > 0)
