import random
import os
import signal
import asyncio
from unittest.mock import patch

from molotov.api import scenario, global_setup
from molotov.tests.support import (TestLoop, coserver, dedicatedloop, set_args,
                                   skip_pypy, only_pypy, catch_sleep)
from molotov.tests.statsd import UDPServer
from molotov.run import run, main
from molotov import fmwk
from molotov.sharedcounter import SharedCounters
from molotov.util import request, json_request
from molotov import __version__


_CONFIG = os.path.join(os.path.dirname(__file__), 'molotov.json')
_RES = []
_RES2 = {}


class TestRunner(TestLoop):
    def setUp(self):
        super(TestRunner, self).setUp()
        _RES[:] = []
        _RES2.clear()

    def _get_args(self):
        args = self.get_args()
        args.statsd = True
        args.statsd_address = 'udp://127.0.0.1:9999'
        args.scenario = 'molotov.tests.test_run'
        return args

    @dedicatedloop
    def test_redirect(self):
        test_loop = asyncio.get_event_loop()
        test_loop.set_debug(True)
        test_loop._close = test_loop.close
        test_loop.close = lambda: None

        @scenario(weight=10)
        async def _one(session):
            # redirected
            async with session.get('http://localhost:8888/redirect') as resp:
                redirect = resp.history
                assert redirect[0].status == 302
                assert resp.status == 200

            # not redirected
            async with session.get('http://localhost:8888/redirect',
                                   allow_redirects=False) as resp:
                redirect = resp.history
                assert len(redirect) == 0
                assert resp.status == 302
                content = await resp.text()
                assert content == ''

            _RES.append(1)

        args = self._get_args()
        args.verbose = 2
        with coserver():
            run(args)

        self.assertTrue(len(_RES) > 0)
        test_loop._close()

    @dedicatedloop
    def test_runner(self):
        test_loop = asyncio.get_event_loop()
        test_loop.set_debug(True)
        test_loop._close = test_loop.close
        test_loop.close = lambda: None

        @global_setup()
        def something_sync(args):
            grab = request('http://localhost:8888')
            self.assertEqual(grab['status'], 200)
            grab_json = json_request('http://localhost:8888/molotov.json')
            self.assertTrue('molotov' in grab_json['content'])

        @scenario(weight=10)
        async def here_one(session):
            async with session.get('http://localhost:8888') as resp:
                await resp.text()
            _RES.append(1)

        @scenario(weight=90)
        async def here_two(session):
            if session.statsd is not None:
                session.statsd.incr('yopla')
            _RES.append(2)

        args = self._get_args()
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
    def test_config_verbose_quiet(self):
        stdout, stderr = self._test_molotov('-qv', '--config', _CONFIG)
        wanted = "You can't"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_config_no_scenario_found(self):
        stdout, stderr = self._test_molotov('-c', 'molotov.tests.test_run')
        wanted = "No scenario was found"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_config_no_single_mode_found(self):

        @scenario(weight=10)
        async def not_me(session):
            _RES.append(3)

        stdout, stderr = self._test_molotov('-c', '-s', 'blah',
                                            'molotov.tests.test_run')
        wanted = "Can't find"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_name(self):

        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        @scenario(weight=30, name='me')
        async def here_four(session):
            _RES.append(4)

        stdout, stderr = self._test_molotov('-cx', '--max-runs', '2', '-s',
                                            'me',
                                            'molotov.tests.test_run')
        wanted = "SUCCESSES: 2"
        self.assertTrue(wanted in stdout)
        self.assertTrue(_RES, [4, 4])

    @dedicatedloop
    def test_single_mode(self):

        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        stdout, stderr = self._test_molotov('-cx', '--max-runs', '2', '-s',
                                            'here_three',
                                            'molotov.tests.test_run')
        wanted = "SUCCESSES: 2"
        self.assertTrue(wanted in stdout)

    @only_pypy
    @dedicatedloop
    def test_uvloop_pypy(self):

        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        orig_import = __import__

        def import_mock(name, *args):
            if name == 'uvloop':
                raise ImportError()
            return orig_import(name, *args)

        with patch('builtins.__import__', side_effect=import_mock):
            stdout, stderr = self._test_molotov('-cx', '--max-runs', '2',
                                                '-s',
                                                'here_three', '--uvloop',
                                                'molotov.tests.test_run')
        wanted = "You can't use uvloop"
        self.assertTrue(wanted in stdout)

    @skip_pypy
    @dedicatedloop
    def test_uvloop_import_error(self):

        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        orig_import = __import__

        def import_mock(name, *args):
            if name == 'uvloop':
                raise ImportError()
            return orig_import(name, *args)

        with patch('builtins.__import__', side_effect=import_mock):
            stdout, stderr = self._test_molotov('-cx', '--max-runs', '2',
                                                '--console-update', '0',
                                                '-s',
                                                'here_three', '--uvloop',
                                                'molotov.tests.test_run')
        wanted = "You need to install uvloop"
        self.assertTrue(wanted in stdout)

    @skip_pypy
    @dedicatedloop
    def test_uvloop(self):

        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        stdout, stderr = self._test_molotov('-cx', '--max-runs', '2', '-s',
                                            'here_three', '--uvloop',
                                            'molotov.tests.test_run')
        wanted = "SUCCESSES: 2"
        self.assertTrue(wanted in stdout, stdout)

    @dedicatedloop
    def test_delay(self):
        with catch_sleep() as delay:
            @scenario(weight=10, delay=.1)
            async def here_three(session):
                _RES.append(3)

            stdout, stderr = self._test_molotov('--delay', '.6',
                                                '--console-update', '0',
                                                '-cx', '--max-runs', '2', '-s',
                                                'here_three',
                                                'molotov.tests.test_run')
            wanted = "SUCCESSES: 2"
            self.assertTrue(wanted in stdout, stdout)
            self.assertEqual(delay, [.1, .6] * 2)

    @dedicatedloop
    def test_rampup(self):
        with catch_sleep() as delay:
            @scenario(weight=10)
            async def here_three(session):
                _RES.append(3)

            stdout, stderr = self._test_molotov('--ramp-up', '10',
                                                '--workers', '5',
                                                '--console-update', '0',
                                                '-cx', '--max-runs', '2', '-s',
                                                'here_three',
                                                'molotov.tests.test_run')
            # workers should start every 2 seconds since
            # we have 5 workers and a ramp-up
            # the first one starts immediatly, then each worker
            # sleeps 2 seconds more.
            delay = [d for d in delay if d != 0]
            self.assertEqual(delay, [2.0, 4.0, 6.0, 8.0])
            wanted = "SUCCESSES: 10"
            self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_sizing(self):
        _RES2['fail'] = 0
        _RES2['succ'] = 0

        with catch_sleep():
            @scenario()
            async def sizer(session):
                if random.randint(0, 20) == 1:
                    _RES2['fail'] += 1
                    raise AssertionError()
                else:
                    _RES2['succ'] += 1

            stdout, stderr = self._test_molotov('--sizing',
                                                '--console-update', '0',
                                                '--sizing-tolerance', '5',
                                                '-s', 'sizer',
                                                'molotov.tests.test_run')

            ratio = float(_RES2['fail']) / float(_RES2['succ']) * 100.
            self.assertTrue(fmwk._RESULTS['REACHED'] == 1)
            self.assertEqual(int(ratio*100), fmwk._RESULTS['RATIO'].value)
            self.assertTrue(ratio < 10. and ratio >= 5., ratio)

    @dedicatedloop
    def test_sizing_multiprocess(self):
        counters = SharedCounters('OK', 'FAILED')

        with catch_sleep():
            @scenario()
            async def sizer(session):
                if random.randint(0, 10) == 1:
                    counters['FAILED'] += 1
                    raise AssertionError()
                else:
                    counters['OK'] += 1

            stdout, stderr = self._test_molotov('--sizing', '-p', '2',
                                                '--sizing-tolerance', '5',
                                                '--console-update', '0',
                                                '-s', 'sizer',
                                                'molotov.tests.test_run')
            ratio = (float(counters['FAILED'].value) /
                     float(counters['OK'].value) * 100.)
            self.assertTrue(fmwk._RESULTS['REACHED'] == 1)
            self.assertEqual(counters['FAILED'].value,
                             fmwk._RESULTS['FAILED'].value)
            self.assertEqual(counters['OK'].value,
                             fmwk._RESULTS['OK'].value)
            self.assertTrue(ratio >= 5., ratio)

    @dedicatedloop
    def test_timed_sizing(self):
        _RES2['fail'] = 0
        _RES2['succ'] = 0
        _RES2['messed'] = False

        with catch_sleep():
            @scenario()
            async def sizer(session):
                if session.worker_id == 200 and not _RES2['messed']:
                    # worker 2 will mess with fmwk._TOLERANCE
                    # so we can test a _TOLERANCE reset
                    # since we're faking all timers, the current
                    # time in the test is always around 0
                    # so to have now() - _TOLERANCE > 60
                    # we need to set a negative value here
                    # to trick it
                    fmwk._TOLERANCE = - 61
                    _RES2['messed'] = True
                    _RES2['fail'] = _RES2['succ'] = 0

                if session.worker_id > 100:
                    # starting to introduce errors passed the 100th
                    if random.randint(0, 10) == 1:
                        _RES2['fail'] += 1
                        raise AssertionError()
                    else:
                        _RES2['succ'] += 1

                # forces a switch
                await asyncio.sleep(0)

            stdout, stderr = self._test_molotov('--sizing',
                                                '--sizing-tolerance', '5',
                                                '--console-update', '0',
                                                '-cs', 'sizer',
                                                'molotov.tests.test_run')

            ratio = float(_RES2['fail']) / float(_RES2['succ']) * 100.
            self.assertTrue(ratio < 15. and ratio > 5., ratio)

    @dedicatedloop
    def test_sizing_multiprocess_interrupted(self):

        counters = SharedCounters('OK', 'FAILED')

        @scenario()
        async def sizer(session):
            if random.randint(0, 10) == 1:
                counters['FAILED'] += 1
                raise AssertionError()
            else:
                counters['OK'] += 1

        async def _stop():
            await asyncio.sleep(2.)
            os.kill(os.getpid(), signal.SIGINT)

        asyncio.ensure_future(_stop())
        stdout, stderr = self._test_molotov('--sizing', '-p', '3',
                                            '--sizing-tolerance', '90',
                                            '--console-update', '0',
                                            '-s', 'sizer',
                                            'molotov.tests.test_run')
        self.assertTrue(fmwk._RESULTS['REACHED'] == 0)
        self.assertTrue("Sizing was not finished" in stdout)
