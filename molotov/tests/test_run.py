import asyncio
from collections import namedtuple
from molotov.api import scenario
from molotov.tests.support import TestLoop, coserver
from molotov.tests.statsd import UDPServer
from molotov.run import run


class TestRunner(TestLoop):

    def test_runner(self):
        test_loop = asyncio.get_event_loop()
        test_loop.set_debug(True)
        test_loop._close = test_loop.close
        test_loop.close = lambda: None
        _RES = []

        @scenario(10)
        async def here_one(session):
            async with session.get('http://localhost:8888') as resp:
                await resp.text()
            _RES.append(1)

        @scenario(90)
        async def here_two(session):
            session.statsd.incr('yopla')
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
        args.statsd = True
        args.statsd_server = '127.0.0.1'
        args.statsd_port = 9999
        args.scenario = 'molotov.tests.test_run'

        server = UDPServer('127.0.0.1', 9999, loop=test_loop)
        _stop = asyncio.Future()

        async def stop():
            await _stop
            await server.stop()

        server_task = asyncio.ensure_future(server.run())
        stop_task = asyncio.ensure_future(stop())

        with coserver():
            run(args)

        _stop.set_result(True)
        test_loop.run_until_complete(asyncio.gather(server_task, stop_task))

        self.assertTrue(len(_RES) > 0)

        udp = server.flush()
        self.assertTrue(len(udp) > 0)

        test_loop._close()
