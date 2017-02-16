import asyncio
import os
import signal

from molotov.session import LoggedClientSession
from molotov.fmwk import step, worker, runner
from molotov.api import (scenario, setup, global_setup, teardown,
                         global_teardown)
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

        res = []

        @setup()
        async def setuptest(num, args):
            res.append('0')

        @scenario(50)
        async def test_one(session):
            pass

        @scenario(100)
        async def test_two(session):
            pass

        results = {'OK': 0, 'FAILED': 0}
        stream = asyncio.Queue()
        args = self.get_args()
        statsd = None

        await worker(1, loop, results, args, stream, statsd)

        self.assertTrue(results['OK'] > 0)
        self.assertEqual(results['FAILED'], 0)
        self.assertEqual(len(res), 1)

    def test_runner(self):
        res = []

        @global_setup()
        def init(args):
            res.append('SETUP')

        @setup()
        async def setuptest(num, args):
            res.append('0')

        @scenario(50)
        async def test_one(session):
            pass

        @scenario(100)
        async def test_two(session):
            pass

        args = self.get_args()
        results = runner(args)
        self.assertTrue(results['OK'] > 0)
        self.assertEqual(results['FAILED'], 0)
        self.assertEqual(len(res), 2)

    def test_runner_multiprocess(self):
        res = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        @setup()
        async def setuptest(num, args):
            res.append('0')

        @scenario(50)
        async def test_one(session):
            pass

        @scenario(100)
        async def test_two(session):
            pass

        args = self.get_args()
        args.processes = 2
        args.workers = 5
        results = runner(args)
        self.assertTrue(results['OK'] > 0)
        self.assertEqual(results['FAILED'], 0)

    @async_test
    async def test_aworker_noexc(self, loop):

        res = []

        @setup()
        async def setuptest(num, args):
            res.append('0')

        @scenario(50)
        async def test_one(session):
            pass

        @scenario(100)
        async def test_two(session):
            pass

        results = {'OK': 0, 'FAILED': 0}
        stream = asyncio.Queue()
        args = self.get_args()
        args.exception = False
        statsd = None

        await worker(1, loop, results, args, stream, statsd)

        self.assertTrue(results['OK'] > 0)
        self.assertEqual(results['FAILED'], 0)
        self.assertEqual(len(res), 1)

    @async_test
    async def test_failure(self, loop):

        @scenario(100)
        async def test_failing(session):
            raise ValueError()

        results = {'OK': 0, 'FAILED': 0}
        stream = asyncio.Queue()
        args = self.get_args()
        statsd = None

        await worker(1, loop, results, args, stream, statsd)

        self.assertEqual(results['OK'], 0)
        self.assertTrue(results['FAILED'] > 0)

    def test_shutdown(self):
        res = []

        @teardown()
        def _worker_teardown(num):
            res.append('BYE WORKER')

        @global_teardown()
        def _teardown():
            res.append('BYE')

        @scenario(100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = runner(args)

        self.assertEqual(results['OK'], 1)
        self.assertEqual(results['FAILED'], 0)
        self.assertEqual(res, ['BYE WORKER', 'BYE'])
