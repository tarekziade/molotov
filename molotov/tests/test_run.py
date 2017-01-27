import asyncio
from collections import namedtuple
from molotov.api import scenario
from molotov.tests.support import TestLoop
from molotov.run import run


class TestRunner(TestLoop):

    def test_runner(self):

        _RES = []

        @scenario(10)
        async def here_one(self):
            _RES.append(1)

        @scenario(90)
        async def here_two(self):
            _RES.append(2)

        args = namedtuple('args', 'verbose quiet duration exception')
        args.verbose = True
        args.quiet = False
        args.duration = 1
        args.exception = True
        args.console = True
        args.processes = 1
        args.workers = 1
        args.debug = True
        args.scenario = 'molotov.tests.test_run'
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(True)

        try:
            run(args)
        finally:
            loop.close()

        self.assertTrue(len(_RES) > 0)
