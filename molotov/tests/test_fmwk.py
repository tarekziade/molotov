import asyncio

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
            result = await step(session, False, False, stream)
            self.assertTrue(result, 1)
            self.assertEqual(len(res), 1)

    @async_test
    async def test_failing_step(self, loop):

        @scenario(100)
        async def test_two(session):
            raise ValueError()

        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream) as session:
            result = await step(session, False, False, stream)
            self.assertTrue(result, -1)

    @async_test
    async def test_aworker(self, loop):

        @scenario(50)
        async def test_one(session):
            pass

        @scenario(100)
        async def test_two(session):
            pass

        results = {'OK': 0, 'FAILED': 0}
        stream = asyncio.Queue()
        args = self.get_args()

        await worker(loop, results, args, stream)

        self.assertTrue(results['OK'] > 0)
        self.assertEqual(results['FAILED'], 0)

    @async_test
    async def test_failure(self, loop):

        @scenario(100)
        async def test_failing(session):
            raise ValueError()

        results = {'OK': 0, 'FAILED': 0}
        stream = asyncio.Queue()
        args = self.get_args()

        await worker(loop, results, args, stream)

        self.assertEqual(results['OK'], 0)
        self.assertTrue(results['FAILED'] > 0)
