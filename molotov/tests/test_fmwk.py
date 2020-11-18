import os
import signal
from molotov.session import LoggedClientSession
from molotov.runner import Runner
from molotov.worker import Worker
from molotov.util import json_request, request, stop_reason
from molotov.api import (
    scenario,
    setup,
    global_setup,
    teardown,
    global_teardown,
    setup_session,
    teardown_session,
    scenario_picker,
    events,
)
from molotov.tests.support import (
    TestLoop,
    async_test,
    dedicatedloop,
    serialize,
    catch_sleep,
    coserver,
)


class TestFmwk(TestLoop):
    def get_worker(self, console, results, loop=None, args=None):
        statsd = None
        delay = 0
        if args is None:
            args = self.get_args(console=console)
        return Worker(1, results, console, args, statsd=statsd, delay=delay, loop=loop)

    @async_test
    async def test_step(self, loop, console, results):
        res = []

        @scenario(weight=0)
        async def test_one(session):
            res.append("1")

        @scenario(weight=100, delay=1.5)
        async def test_two(session):
            res.append("2")

        async def _slept(time):
            res.append(time)

        w = self.get_worker(console, results, loop=loop)

        with catch_sleep(res):
            async with LoggedClientSession(loop, console) as session:
                result = await w.step(0, session)
                self.assertTrue(result, 1)
                self.assertEqual(len(res), 2)
                self.assertEqual(res[1], 1.5)

    @async_test
    async def test_picker(self, loop, console, results):
        res = []

        @scenario_picker()
        def picker(wid, sid):
            series = "_one", "_two", "_two", "_one"
            return series[sid]

        @scenario()
        async def _one(session):
            res.append("1")

        @scenario()
        async def _two(session):
            res.append("2")

        w = self.get_worker(console, results, loop=loop)

        for i in range(4):
            async with LoggedClientSession(loop, console) as session:
                await w.step(i, session)

        self.assertEqual(res, ["1", "2", "2", "1"])

    @async_test
    async def test_failing_step(self, loop, console, results):
        @scenario(weight=100)
        async def test_two(session):
            raise ValueError()

        w = self.get_worker(console, results, loop=loop)
        async with LoggedClientSession(loop, console) as session:
            result = await w.step(0, session)
            self.assertTrue(result, -1)

    @async_test
    async def test_aworker(self, loop, console, results):

        res = []

        @setup()
        async def setuptest(num, args):
            res.append("0")

        @scenario(weight=50)
        async def test_one(session):
            pass

        @scenario(weight=100)
        async def test_two(session):
            pass

        args = self.get_args(console=console)
        w = self.get_worker(console, results, loop=loop, args=args)
        await w.run()

        self.assertTrue(results["OK"] > 0)
        self.assertEqual(results["FAILED"], 0)
        self.assertEqual(len(res), 1)

    def _runner(self, console, screen=None):
        res = []
        _events = []

        @events()
        async def _event(event, **data):
            _events.append(event)

        @global_setup()
        def init(args):
            res.append("SETUP")

        @setup_session()
        async def _session(wid, session):
            session.some = 1
            res.append("SESSION")

        @setup()
        async def setuptest(num, args):
            res.append("0")

        @scenario(weight=50)
        async def test_one(session):
            async with session.get("http://localhost:8888") as resp:
                await resp.text()

        @scenario(weight=100)
        async def test_two(session):
            async with session.get("http://localhost:8888") as resp:
                await resp.text()

        @teardown_session()
        async def _teardown_session(wid, session):
            self.assertEqual(session.some, 1)
            res.append("SESSION_TEARDOWN")

        args = self.get_args()
        args.console = console
        args.verbose = 1
        if not args.sizing:
            args.max_runs = 5
        results = Runner(args)()
        self.assertTrue(results["OK"] > 0)
        self.assertEqual(results["FAILED"], 0)
        self.assertEqual(res, ["SETUP", "0", "SESSION", "SESSION_TEARDOWN"])
        self.assertTrue(len(_events) > 0)

    @dedicatedloop
    def test_runner(self):
        with coserver():
            return self._runner(console=False)

    @dedicatedloop
    def test_runner_console(self):
        with coserver():
            return self._runner(console=True)

    @dedicatedloop
    def _multiprocess(self, console, nosetup=False):
        res = []

        if not nosetup:

            @setup()
            async def setuptest(num, args):
                res.append("0")

        @scenario(weight=50)
        async def test_one(session):
            pass

        @scenario(weight=100)
        async def test_two(session):
            pass

        args = self.get_args()
        args.processes = 2
        args.workers = 2
        args.console = console
        results = Runner(args)()
        self.assertTrue(results["OK"] > 0)
        self.assertEqual(results["FAILED"], 0)

    def test_runner_multiprocess_console(self):
        self._multiprocess(console=True)

    def test_runner_multiprocess_no_console(self):
        self._multiprocess(console=False, nosetup=True)

    @async_test
    async def test_aworker_noexc(self, loop, console, results):

        res = []

        @setup()
        async def setuptest(num, args):
            res.append("0")

        @scenario(weight=50)
        async def test_one(session):
            pass

        @scenario(weight=100)
        async def test_two(session):
            pass

        args = self.get_args(console=console)
        args.exception = False
        w = self.get_worker(console, results, loop=loop, args=args)
        await w.run()

        self.assertTrue(results["OK"] > 0)
        self.assertEqual(results["FAILED"], 0)
        self.assertEqual(len(res), 1)

    @async_test
    async def test_setup_session_failure(self, loop, console, results):
        @setup_session()
        async def _setup_session(wid, session):
            json_request("http://invalid")

        @scenario(weight=100)
        async def test_working(session):
            pass

        args = self.get_args(console=console)
        w = self.get_worker(console, results, loop=loop, args=args)

        await w.run()
        output = await serialize(console)
        expected = (
            "Name or service not known" in output
            or "nodename nor servname provided" in output  # NOQA
        )
        self.assertTrue(expected, output)

    @async_test
    async def test_setup_session_fresh_loop(self, loop, console, results):
        content = []

        @setup_session()
        async def _setup_session(wid, session):
            with coserver():
                html = str(request("http://localhost:8888"))
                content.append(html)

        @scenario(weight=100)
        async def test_working(session):
            pass

        args = self.get_args(console=console)
        w = self.get_worker(console, results, loop=loop, args=args)
        await w.run()
        self.assertTrue("Directory listing" in content[0])

    @async_test
    async def test_failure(self, loop, console, results):
        @scenario(weight=100)
        async def test_failing(session):
            raise ValueError("XxX")

        args = self.get_args(console=console)
        w = self.get_worker(console, results, loop=loop, args=args)
        await w.run()

        self.assertTrue(results["OK"] == 0)
        self.assertTrue(results["FAILED"] > 0)
        self.assertEquals(stop_reason()[0].args, ("XxX",))

    @dedicatedloop
    def test_shutdown(self):
        res = []

        @teardown()
        def _worker_teardown(num):
            res.append("BYE WORKER")

        @global_teardown()
        def _teardown():
            res.append("BYE")

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = Runner(args)()

        self.assertEqual(results["OK"], 1)
        self.assertEqual(results["FAILED"], 0)
        self.assertEqual(res, ["BYE WORKER", "BYE"])

    @dedicatedloop
    def test_shutdown_exception(self):
        @teardown()
        def _worker_teardown(num):
            raise Exception("bleh")

        @global_teardown()
        def _teardown():
            raise Exception("bleh")

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = Runner(args)()
        self.assertEqual(results["OK"], 1)

    @async_test
    async def test_session_shutdown_exception(self, loop, console, results):
        @teardown_session()
        async def _teardown_session(wid, session):
            raise Exception("bleh")

        @scenario(weight=100)
        async def test_tds(session):
            pass

        args = self.get_args(console=console)
        w = self.get_worker(console, results, loop=loop, args=args)
        await w.run()

        output = await serialize(console)
        self.assertTrue("Exception" in output, output)
        self.assertEqual(results["FAILED"], 0)

    @dedicatedloop
    def test_setup_exception(self):
        @setup()
        async def _worker_setup(num, args):
            raise Exception("bleh")

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = Runner(args)()
        self.assertEqual(results["OK"], 0)
        self.assertEqual(results["SETUP_FAILED"], 1)

    @dedicatedloop
    def test_global_setup_exception(self):
        @global_setup()
        def _setup(args):
            raise Exception("bleh")

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        runner = Runner(args)
        self.assertRaises(Exception, runner)

    @dedicatedloop
    def test_teardown_exception(self):
        @teardown()
        def _teardown(args):
            raise Exception("bleh")

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = Runner(args)()
        self.assertEqual(results["FAILED"], 0)

    @dedicatedloop
    def test_setup_not_dict(self):
        @setup()
        async def _worker_setup(num, args):
            return 1

        @scenario(weight=100)
        async def test_two(session):
            os.kill(os.getpid(), signal.SIGTERM)

        args = self.get_args()
        results = Runner(args)()
        self.assertEqual(results["OK"], 0)
