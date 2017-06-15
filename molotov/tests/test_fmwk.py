import asyncio
import os
import signal
from unittest.mock import patch

from molotov.session import LoggedClientSession
from molotov.fmwk import step, worker, runner
from molotov.api import (scenario, setup, global_setup, teardown,
                         global_teardown, setup_session, teardown_session)
from molotov.tests.support import TestLoop, async_test, dedicatedloop


class init_screen:
    def __init__(self, *args, **kw):
        self.loop = asyncio.get_event_loop()

    def set_alarm_in(self, when, func):
        self.loop.call_later(when, func)

    start = stop = run = __init__


class TestFmwk(TestLoop):

    @async_test
    async def test_step(self, loop):
        res = []

        @scenario(weight=0)
        async def test_one(session):
            res.append('1')

        @scenario(weight=100, delay=1.5)
        async def test_two(session):
            res.append('2')

        async def _slept(time):
            res.append(time)

        with patch('asyncio.sleep', _slept):
            stream = asyncio.Queue()
            async with LoggedClientSession(loop, stream) as session:
                result = await step(session, False, False, stream)
                self.assertTrue(result, 1)
                self.assertEqual(len(res), 2)
                self.assertEqual(res[1], 1.5)

    @async_test
    async def test_failing_step(self, loop):

        @scenario(weight=100)
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

        @scenario(weight=50)
        async def test_one(session):
            pass

        @scenario(weight=100)
        async def test_two(session):
            pass

        results = {'OK': 0, 'FAILED': 0}
        stream = asyncio.Queue()
        args = self.get_args()
        statsd = None

        await worker(1, loop, results, args, stream, statsd, delay=0)

        self.assertTrue(results['OK'] > 0)
        self.assertEqual(results['FAILED'], 0)
        self.assertEqual(len(res), 1)

    def _runner(self, console, screen=None):
        res = []

        @global_setup()
        def init(args):
            res.append('SETUP')

        @setup_session()
        async def _session(wid, session):
            session.some = 1
            res.append('SESSION')

        @setup()
        async def setuptest(num, args):
            res.append('0')

        @scenario(weight=50)
        async def test_one(session):
            pass

        @scenario(weight=100)
        async def test_two(session):
            pass

        @teardown_session()
        async def _teardown_session(wid, session):
            self.assertEqual(session.some, 1)
            res.append('SESSION_TEARDOWN')

        args = self.get_args()
        args.console = console
        args.verbose = 1
        results = runner(args, screen=screen)
        self.assertTrue(results['OK'] > 0)
        self.assertEqual(results['FAILED'], 0)
        self.assertEqual(res, ['SETUP', '0', 'SESSION', 'SESSION_TEARDOWN'])

    @dedicatedloop
    def test_runner(self):
        return self._runner(console=False, screen=init_screen)

    @dedicatedloop
    def test_runner_console(self):
        return self._runner(console=True)

    @dedicatedloop
    def _multiprocess(self, console, nosetup=False):
        res = []

        if not nosetup:
            @setup()
            async def setuptest(num, args):
                res.append('0')

        @scenario(weight=50)
        async def test_one(session):
            pass

        @scenario(weight=100)
        async def test_two(session):
            pass

        args = self.get_args()
        args.processes = 2
        args.workers = 5
        args.console = console
        results = runner(args, screen=init_screen)
        self.assertTrue(results['OK'] > 0)
        self.assertEqual(results['FAILED'], 0)

    @dedicatedloop
    def test_runner_multiprocess_console(self):
        self._multiprocess(console=True)
        self._multiprocess(console=False, nosetup=True)

    @async_test
    async def test_aworker_noexc(self, loop):

        res = []

        @setup()
        async def setuptest(num, args):
            res.append('0')

        @scenario(weight=50)
        async def test_one(session):
            pass

        @scenario(weight=100)
        async def test_two(session):
            pass

        results = {'OK': 0, 'FAILED': 0}
        stream = asyncio.Queue()
        args = self.get_args()
        args.exception = False
        statsd = None

        await worker(1, loop, results, args, stream, statsd, delay=0)

        self.assertTrue(results['OK'] > 0)
        self.assertEqual(results['FAILED'], 0)
        self.assertEqual(len(res), 1)

    @async_test
    async def test_failure(self, loop):

        @scenario(weight=100)
        async def test_failing(session):
            raise ValueError()

        results = {'OK': 0, 'FAILED': 0}
        stream = asyncio.Queue()
        args = self.get_args()
        statsd = None

        await worker(1, loop, results, args, stream, statsd, delay=0)

        self.assertEqual(results['OK'], 0)
        self.assertTrue(results['FAILED'] > 0)

    @dedicatedloop
    def test_shutdown(self):
        res = []

        @teardown()
        def _worker_teardown(num):
            res.append('BYE WORKER')

        @global_teardown()
        def _teardown():
            res.append('BYE')

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = runner(args)

        self.assertEqual(results['OK'], 1)
        self.assertEqual(results['FAILED'], 0)
        self.assertEqual(res, ['BYE WORKER', 'BYE'])

    @dedicatedloop
    def test_shutdown_exception(self):

        @teardown()
        def _worker_teardown(num):
            raise Exception('bleh')

        @global_teardown()
        def _teardown():
            raise Exception('bleh')

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = runner(args)

        self.assertEqual(results['OK'], 1)

    @dedicatedloop
    def test_session_shutdown_exception(self):

        @teardown_session()
        async def _teardown_session(wid, session):
            raise Exception('bleh')

        @global_teardown()
        def _teardown():
            raise Exception('bleh')

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = runner(args)
        self.assertEqual(results['OK'], 1)

    @dedicatedloop
    def test_setup_exception(self):

        @setup()
        async def _worker_setup(num, args):
            raise Exception('bleh')

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = runner(args)
        self.assertEqual(results['OK'], 0)

    @dedicatedloop
    def test_global_setup_exception(self):

        @global_setup()
        def _setup(args):
            raise Exception('bleh')

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        self.assertRaises(Exception, runner, args)

    @dedicatedloop
    def test_setup_not_dict(self):

        @setup()
        async def _worker_setup(num, args):
            return 1

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = runner(args)
        self.assertEqual(results['OK'], 0)
