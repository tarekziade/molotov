import os
import asyncio
from collections import namedtuple

from molotov.api import scenario
from molotov.tests.support import TestLoop, coserver, dedicatedloop, set_args
from molotov.tests.statsd import UDPServer
from molotov.run import run, main
from molotov import __version__


_CONFIG = os.path.join(os.path.dirname(__file__), '..', '..', 'molotov.json')


class TestRunner(TestLoop):

    @dedicatedloop
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

    @dedicatedloop
    def test_main(self):
        with set_args('molotov', '-cq', '-d', '1', 'molotov/tests/example.py'):
            main()

    def _test_molotov(self, *args):
        with set_args('molotov', *args) as (stdout, stderr):
            try:
                main()
            except SystemExit:
                pass
        return stdout.read().strip(), stderr.read().strip()

    @dedicatedloop
    def test_version(self):
        stdout, stderr = self._test_molotov('--version')
        self.assertEqual(stdout, __version__)

    @dedicatedloop
    def test_empty_scenario(self):
        stdout, stderr = self._test_molotov('')
        self.assertTrue('Cannot import' in stdout)

    @dedicatedloop
    def test_no_scenario(self):
        stdout, stderr = self._test_molotov()
        self.assertTrue('Cannot import' in stdout)

    @dedicatedloop
    def test_config_no_scenario(self):
        stdout, stderr = self._test_molotov('-c', '--config', _CONFIG,
                                            'DONTEXIST')
        wanted = "Can't find 'DONTEXIST' in the config"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_config_verbose(self):
        stdout, stderr = self._test_molotov('-v', '--config', _CONFIG)
        wanted = "You have to be in console mode"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_config_verbose_quiet(self):
        stdout, stderr = self._test_molotov('-qv', '--config', _CONFIG)
        wanted = "You can't"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_config_no_secnario_found(self):
        stdout, stderr = self._test_molotov('-c', 'molotov.tests.test_run')
        wanted = "No scenario was found"
        self.assertTrue(wanted in stdout)
