import unittest
import time
import random
import os
import signal
import asyncio
from unittest.mock import patch
import re
from collections import defaultdict
import json
import io

import aiohttp

from molotov.api import scenario, global_setup
from molotov.tests.support import (
    TestLoop,
    coserver,
    dedicatedloop,
    set_args,
    skip_pypy,
    only_pypy,
    catch_sleep,
    dedicatedloop_noclose,
    co_catch_output,
)
from molotov.tests.statsd import run_server, stop_server
from molotov.run import run, main
from molotov.shared.counter import Counters
from molotov.util import request, json_request, set_timer
from molotov.session import get_context
from molotov import __version__


_HERE = os.path.dirname(__file__)
_CONFIG = os.path.join(_HERE, "molotov.json")
_RES = []
_RES2 = {}


class TestRunner(TestLoop):
    def setUp(self):
        super(TestRunner, self).setUp()
        _RES[:] = []
        _RES2.clear()

    def _get_args(self, udp_port=None):
        args = self.get_args()
        if udp_port is not None:
            args.statsd = True
            args.statsd_address = "udp://localhost:%s" % udp_port
        args.scenario = "molotov.tests.test_run"
        return args

    @co_catch_output
    @dedicatedloop_noclose
    def test_redirect(self):

        with coserver() as port:

            @scenario(weight=10)
            async def _one(session):
                # redirected
                async with session.get("http://localhost:%s/redirect" % port) as resp:
                    redirect = resp.history
                    assert redirect[0].status == 302
                    assert resp.status == 200

                # not redirected
                async with session.get(
                    "http://localhost:%s/redirect" % port, allow_redirects=False
                ) as resp:
                    redirect = resp.history
                    assert len(redirect) == 0
                    assert resp.status == 302
                    content = await resp.text()
                    assert content == ""

                _RES.append(1)

            args = self._get_args()
            args.verbose = 2
            args.max_runs = 2
            run(args)

        self.assertTrue(len(_RES) > 0)

    @co_catch_output
    @dedicatedloop_noclose
    def test_runner(self):
        with coserver() as port:

            @global_setup()
            def something_sync(args):
                grab = request("http://localhost:%s" % port)
                self.assertEqual(grab["status"], 200)
                grab_json = json_request("http://localhost:%s/molotov.json" % port)
                self.assertTrue("molotov" in grab_json["content"])

            @scenario(weight=10)
            async def here_one(session):
                async with session.get("http://localhost:%s" % port) as resp:
                    await resp.text()
                _RES.append(1)

            @scenario(weight=90)
            async def here_two(session):
                statsd = get_context(session).statsd
                if statsd is not None:
                    for i in range(10):
                        statsd.increment("user.online")
                    await asyncio.sleep(0)

                await asyncio.sleep(0.1)

                _RES.append(2)

            udp_proc, udp_port, udp_conn = run_server()
            args = self._get_args(udp_port)
            args.max_runs = 3
            args.duration = 9999

            run(args)

            self.assertTrue(len(_RES) > 0)
            received = stop_server(udp_proc, udp_conn)
            self.assertTrue(len(received) > 0)

    @dedicatedloop
    def test_main(self):
        with set_args("molotov", "-q", "-d", "1", "molotov/tests/example.py"):
            main()

    def _test_molotov(self, *args):
        if "--duration" not in args and "-d" not in args:
            args = list(args) + ["--duration", "10"]
        rc = 0
        with set_args("molotov", *args) as (stdout, stderr):
            try:
                main()
            except SystemExit as e:
                rc = e.code
        return stdout.read().strip(), stderr.read().strip(), rc

    @dedicatedloop
    def test_version(self):
        stdout, stderr, rc = self._test_molotov("--version")
        self.assertEqual(stdout, __version__)

    @dedicatedloop
    def test_empty_scenario(self):
        stdout, stderr, rc = self._test_molotov("")
        self.assertTrue("Cannot import" in stdout)

    @dedicatedloop
    def test_config_no_scenario(self):
        stdout, stderr, rc = self._test_molotov("--config", _CONFIG, "DONTEXIST")
        wanted = "Can't find 'DONTEXIST' in the config"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_config_verbose_quiet(self):
        stdout, stderr, rc = self._test_molotov("-qv", "--config", _CONFIG)
        wanted = "You can't"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_config_no_scenario_found(self):
        stdout, stderr, rc = self._test_molotov("molotov.tests.test_run")
        wanted = "No scenario was found"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_config_no_single_mode_found(self):
        @scenario(weight=10)
        async def not_me(session):
            _RES.append(3)

        stdout, stderr, rc = self._test_molotov("-s", "blah", "molotov.tests.test_run")
        wanted = "Can't find"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_name(self):
        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        @scenario(weight=30, name="me")
        async def here_four(session):
            _RES.append(4)

        stdout, stderr, rc = self._test_molotov(
            "-x", "--max-runs", "2", "-s", "me", "molotov.tests.test_run"
        )
        wanted = "SUCCESSES: 2"
        self.assertTrue(wanted in stdout)
        self.assertTrue(_RES, [4, 4])

    @dedicatedloop
    def test_single_mode(self):
        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        stdout, stderr, rc = self._test_molotov(
            "-x", "--max-runs", "2", "-s", "here_three", "molotov.tests.test_run"
        )
        wanted = "SUCCESSES: 2"
        self.assertTrue(wanted in stdout)

    @dedicatedloop
    def test_fail_mode_pass(self):
        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        stdout, stderr, rc = self._test_molotov(
            "-x",
            "--max-runs",
            "2",
            "--fail",
            "1",
            "-s",
            "here_three",
            "molotov.tests.test_run",
        )
        wanted = "SUCCESSES: 2"
        self.assertTrue(wanted in stdout)
        self.assertEqual(rc, 0)

    @dedicatedloop
    def test_fail_mode_fail(self):
        @scenario(weight=10)
        async def here_three(session):
            assert False

        stdout, stderr, rc = self._test_molotov(
            "-x",
            "--max-runs",
            "2",
            "--fail",
            "1",
            "-s",
            "here_three",
            "molotov.tests.test_run",
        )
        self.assertEqual(rc, 1)

    @only_pypy
    @dedicatedloop
    def test_uvloop_pypy(self):
        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        orig_import = __import__

        def import_mock(name, *args):
            if name == "uvloop":
                raise ImportError()
            return orig_import(name, *args)

        with patch("builtins.__import__", side_effect=import_mock):
            stdout, stderr, rc = self._test_molotov(
                "-x",
                "--max-runs",
                "2",
                "-s",
                "here_three",
                "--uvloop",
                "molotov.tests.test_run",
            )
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
            if name == "uvloop":
                raise ImportError()
            return orig_import(name, *args)

        with patch("builtins.__import__", side_effect=import_mock):
            stdout, stderr, rc = self._test_molotov(
                "-x",
                "--max-runs",
                "2",
                "--console-update",
                "0",
                "-s",
                "here_three",
                "--uvloop",
                "molotov.tests.test_run",
            )
        wanted = "You need to install uvloop"
        self.assertTrue(wanted in stdout)

    @skip_pypy
    @dedicatedloop
    def test_uvloop(self):
        try:
            import uvloop  # noqa
        except ImportError:
            return

        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        stdout, stderr, rc = self._test_molotov(
            "-x",
            "--max-runs",
            "2",
            "-s",
            "here_three",
            "--uvloop",
            "molotov.tests.test_run",
        )
        wanted = "SUCCESSES: 2"
        self.assertTrue(wanted in stdout, stdout)

    @dedicatedloop
    def test_delay(self):
        with catch_sleep() as delay:

            @scenario(weight=10, delay=0.1)
            async def here_three(session):
                _RES.append(3)

            stdout, stderr, rc = self._test_molotov(
                "--delay",
                "0.21",
                "-x",
                "--max-runs",
                "3",
                "-s",
                "here_three",
                "molotov.tests.test_run",
            )
            wanted = "SUCCESSES: 3"
            self.assertTrue(wanted in stdout, stdout)
            self.assertEqual(delay.count(0.21), 3)

    @dedicatedloop
    def test_rampup(self):
        with catch_sleep() as delay:

            @scenario(weight=10)
            async def here_three(session):
                _RES.append(3)

            stdout, stderr, rc = self._test_molotov(
                "--ramp-up",
                "10",
                "--workers",
                "5",
                "--console-update",
                "0",
                "-x",
                "--max-runs",
                "2",
                "-s",
                "here_three",
                "molotov.tests.test_run",
            )
            # workers should start every 2 seconds since
            # we have 5 workers and a ramp-up
            # the first one starts immediatly, then each worker
            # sleeps 2 seconds more.
            self.assertTrue(set([2.0, 4.0, 6.0, 8.0]).issubset(set(delay)))
            wanted = "SUCCESSES: 10"
            self.assertTrue(wanted in stdout, stdout)

    @dedicatedloop
    def test_sizing(self):
        _RES2["fail"] = 0
        _RES2["succ"] = 0

        with catch_sleep():

            @scenario()
            async def sizer(session):
                if random.randint(0, 20) == 1:
                    _RES2["fail"] += 1
                    raise AssertionError()
                else:
                    _RES2["succ"] += 1

            stdout, stderr, rc = self._test_molotov(
                "--sizing",
                "--console-update",
                "0",
                "--sizing-tolerance",
                "5",
                "-s",
                "sizer",
                "molotov.tests.test_run",
            )

        ratio = float(_RES2["fail"]) / float(_RES2["succ"]) * 100.0
        self.assertTrue(ratio < 14.75 and ratio >= 4.75, ratio)
        found = re.findall(r"obtained with (\d+) workers", stdout)
        assert int(found[0]) > 50

    @unittest.skipIf(os.name == "nt", "win32")
    @dedicatedloop
    def test_sizing_multiprocess(self):
        counters = Counters("OK", "FAILED")

        with catch_sleep():

            @scenario()
            async def sizer(session):
                if random.randint(0, 10) == 1:
                    counters["FAILED"] += 1
                    raise AssertionError()
                else:
                    counters["OK"] += 1

            with set_args(
                "molotov",
                "--sizing",
                "-p",
                "2",
                "--sizing-tolerance",
                "5",
                "--console-update",
                "0",
                "-s",
                "sizer",
                "molotov.tests.test_run",
            ) as (stdout, stderr):
                try:
                    main()
                except SystemExit:
                    pass
            stdout, stderr = stdout.read().strip(), stderr.read().strip()

            # stdout, stderr, rc = self._test_molotov()
            ratio = (
                float(counters["FAILED"].value) / float(counters["OK"].value) * 100.0
            )
            self.assertTrue(ratio >= 4.75, ratio)

    @co_catch_output
    @unittest.skipIf(os.name == "nt", "win32")
    @dedicatedloop_noclose
    def test_statsd_multiprocess(self):
        @scenario()
        async def staty(session):
            get_context(session).statsd.increment("yopla")

        udp_proc, udp_port, udp_conn = run_server()
        args = self._get_args(udp_port)
        args.verbose = 2
        args.processes = 2
        args.max_runs = 5
        args.duration = 1000
        args.statsd = True
        args.single_mode = "staty"
        args.scenario = "molotov.tests.test_run"

        stream = io.StringIO()

        run(args, stream=stream)

        received = stop_server(udp_proc, udp_conn)

        # two processes making 5 run each
        # we want at least 5  here
        self.assertTrue(len(received) > 5)

        stream.seek(0)
        output = stream.read()
        self.assertTrue("Happy breaking!" in output, output)

    @dedicatedloop
    def test_timed_sizing(self):
        _RES2["fail"] = 0
        _RES2["succ"] = 0
        _RES2["messed"] = False

        with catch_sleep():

            @scenario()
            async def sizer(session):
                if get_context(session).worker_id == 200 and not _RES2["messed"]:
                    # worker 2 will mess with the timer
                    # since we're faking all timers, the current
                    # time in the test is always around 0
                    # so to have now() - get_timer() > 60
                    # we need to set a negative value here
                    # to trick it
                    set_timer(-61)
                    _RES2["messed"] = True
                    _RES2["fail"] = _RES2["succ"] = 0

                if get_context(session).worker_id > 100:
                    # starting to introduce errors passed the 100th
                    if random.randint(0, 10) == 1:
                        _RES2["fail"] += 1
                        raise AssertionError()
                    else:
                        _RES2["succ"] += 1

                # forces a switch
                await asyncio.sleep(0)

            stdout, stderr, rc = self._test_molotov(
                "--sizing",
                "--sizing-tolerance",
                "5",
                "--console-update",
                "0",
                "-cs",
                "sizer",
                "molotov.tests.test_run",
            )

        ratio = float(_RES2["fail"]) / float(_RES2["succ"]) * 100.0
        self.assertTrue(ratio < 20.0 and ratio > 4.75, ratio)

    @unittest.skipIf(os.name == "nt", "win32")
    @dedicatedloop
    def _test_sizing_multiprocess_interrupted(self):

        counters = Counters("OK", "FAILED")

        @scenario()
        async def sizer(session):
            if random.randint(0, 10) == 1:
                counters["FAILED"] += 1
                raise AssertionError()
            else:
                counters["OK"] += 1

        async def _stop():
            await asyncio.sleep(2.0)
            os.kill(os.getpid(), signal.SIGINT)

        asyncio.ensure_future(_stop())
        stdout, stderr, rc = self._test_molotov(
            "--sizing",
            "-p",
            "3",
            "--sizing-tolerance",
            "90",
            "--console-update",
            "0",
            "-s",
            "sizer",
            "molotov.tests.test_run",
        )
        self.assertTrue("Sizing was not finished" in stdout)

    @co_catch_output
    @dedicatedloop
    def test_use_extension(self):
        ext = os.path.join(_HERE, "example5.py")
        with coserver() as port:

            @scenario(weight=10)
            async def simpletest(session):
                async with session.get("http://localhost:%s" % port) as resp:
                    assert resp.status == 200

            stdout, stderr, rc = self._test_molotov(
                "-cx",
                "--max-runs",
                "1",
                "--use-extension=" + ext,
                "-s",
                "simpletest",
                "molotov.tests.test_run",
            )
        self.assertTrue("=>" in stdout)
        self.assertTrue("<=" in stdout)

    @co_catch_output
    @dedicatedloop
    def test_use_extension_fail(self):
        ext = os.path.join(_HERE, "exampleIDONTEXIST.py")

        @scenario(weight=10)
        async def simpletest(session):
            async with session.get("http://localhost:8888") as resp:
                assert resp.status == 200

        with coserver():
            stdout, stderr, rc = self._test_molotov(
                "-cx",
                "--max-runs",
                "1",
                "--use-extension=" + ext,
                "-s",
                "simpletest",
                "molotov.tests.test_run",
            )
        self.assertTrue("Cannot import" in stdout)

    @co_catch_output
    @dedicatedloop
    def test_use_extension_module_name(self):
        ext = "molotov.tests.example5"

        with coserver() as port:

            @scenario(weight=10)
            async def simpletest(session):
                async with session.get(f"http://localhost:{port}") as resp:
                    assert resp.status == 200

            stdout, stderr, rc = self._test_molotov(
                "-cx",
                "--max-runs",
                "1",
                "--use-extension=" + ext,
                "-s",
                "simpletest",
                "molotov.tests.test_run",
            )
        self.assertTrue("=>" in stdout)
        self.assertTrue("<=" in stdout)

    @co_catch_output
    @dedicatedloop
    def test_use_extension_module_name_fail(self):
        ext = "IDONTEXTSIST"

        with coserver() as port:

            @scenario(weight=10)
            async def simpletest(session):
                async with session.get(f"http://localhost:{port}") as resp:
                    assert resp.status == 200

            stdout, stderr, rc = self._test_molotov(
                "-cx",
                "--max-runs",
                "1",
                "--use-extension=" + ext,
                "-s",
                "simpletest",
                "molotov.tests.test_run",
            )
        self.assertTrue("Cannot import" in stdout)

    @dedicatedloop
    def test_quiet(self):
        @scenario(weight=10)
        async def here_three(session):
            _RES.append(3)

        stdout, stderr, rc = self._test_molotov(
            "-cx", "--max-runs", "1", "-q", "-s", "here_three", "molotov.tests.test_run"
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    @co_catch_output
    @dedicatedloop_noclose
    def test_slow_server_force_shutdown(self):
        @scenario(weight=10)
        async def _one(session):
            async with session.get("http://localhost:8888/slow") as resp:
                assert resp.status == 200
                _RES.append(1)

        args = self._get_args()
        args.duration = 0.1
        args.verbose = 2
        args.max_runs = 1
        args.force_shutdown = True
        start = time.time()
        with coserver():
            run(args)

        # makes sure the test is stopped even if the server
        # hangs a socket
        self.assertTrue(time.time() - start < 4)
        self.assertTrue(len(_RES) == 0)

    @co_catch_output
    @dedicatedloop_noclose
    def test_slow_server_graceful(self):
        args = self._get_args()
        args.duration = 0.1
        args.verbose = 2
        args.max_runs = 1
        # graceful shutdown on the other hand will wait
        # for the worker completion
        args.graceful_shutdown = True

        start = time.time()
        with coserver() as port:

            @scenario(weight=10)
            async def _one(session):
                async with session.get(f"http://localhost:{port}/slow") as resp:
                    assert resp.status == 200
                    _RES.append(1)

            run(args)

        # makes sure the test finishes
        self.assertTrue(time.time() - start > 5)
        self.assertTrue(len(_RES) == 1)

    @dedicatedloop
    def test_single_run(self):
        _RES = defaultdict(int)

        with catch_sleep():

            @scenario()
            async def one(session):
                _RES["one"] += 1

            @scenario()
            async def two(session):
                _RES["two"] += 1

            @scenario()
            async def three(session):
                _RES["three"] += 1

            stdout, stderr, rc = self._test_molotov(
                "--single-run",
                "molotov.tests.test_run",
            )

        assert rc == 0
        assert _RES["one"] == 1
        assert _RES["two"] == 1
        assert _RES["three"] == 1

    @dedicatedloop
    def _XXX_test_enable_dns(self, m_resolve):

        m_resolve.return_value = ("http://localhost", "http://localhost", "localhost")

        with catch_sleep():

            @scenario()
            async def one(session):
                async with session.get("http://localhost"):
                    pass

            stdout, stderr, rc = self._test_molotov(
                "--single-run",
                "molotov.tests.test_run",
            )

        m_resolve.assert_called()

    @dedicatedloop
    def xxx_test_disable_dns(self, m_resolve):

        with catch_sleep():

            @scenario()
            async def one(session):
                async with session.get("http://localhost"):
                    pass

            stdout, stderr, rc = self._test_molotov(
                "--disable-dns-resolve",
                "--single-run",
                "molotov.tests.test_run",
            )

        m_resolve.assert_not_called()

    @co_catch_output
    @dedicatedloop
    def test_bug_121(self):

        PASSED = [0]

        with catch_sleep(), coserver() as port:

            @scenario()
            async def scenario_one(session):

                cookies = {
                    "csrftoken": "sometoken",
                    "dtk": "1234",
                    "djdt": "hide",
                    "sessionid": "5678",
                }
                boundary = "----WebKitFormBoundaryFTE"
                headers = {
                    "X-CSRFToken": "sometoken",
                    "Content-Type": "multipart/form-data; boundary={}".format(boundary),
                }
                data = json.dumps({"1": "xxx"})

                with aiohttp.MultipartWriter(
                    "form-data", boundary=boundary
                ) as mpwriter:
                    mpwriter.append(
                        data,
                        {
                            "Content-Disposition": 'form-data; name="json"; filename="blob"',
                            "Content-Type": "application/json",
                        },
                    )
                    async with session.post(
                        "http://localhost:%s" % port,
                        data=mpwriter,
                        headers=headers,
                        cookies=cookies,
                    ) as resp:
                        res = await resp.text()
                        assert data in res
                        PASSED[0] += 1

            args = self._get_args()
            args.verbose = 2
            args.max_runs = 1
            res = run(args)

            assert PASSED[0] == 1
            assert res["OK"] == 1

    @co_catch_output
    @dedicatedloop
    def test_local_import(self):
        test = os.path.join(_HERE, "example9.py")

        with coserver():
            stdout, stderr, rc = self._test_molotov("--max-runs", "1", test)
        self.assertTrue("SUCCESSES: 1" in stdout, stdout)
