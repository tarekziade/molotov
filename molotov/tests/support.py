import sys
import signal
import os
import asyncio
import unittest
import time
from contextlib import contextmanager
import functools
from collections import namedtuple
from http.client import HTTPConnection
from io import StringIO
import http.server
import socketserver
import pytest
from unittest.mock import patch

import multiprocess
from aiohttp.client_reqrep import URL
from multidict import CIMultiDict
from molotov.api import _SCENARIO, _FIXTURES
from molotov import util
from molotov.run import PYPY
from molotov.session import LoggedClientRequest, LoggedClientResponse
from molotov.ui.console import SharedConsole
from molotov.shared.counter import Counters


HERE = os.path.dirname(__file__)

skip_pypy = pytest.mark.skipif(PYPY, reason="could not make work on pypy")
only_pypy = pytest.mark.skipif(not PYPY, reason="only pypy")

if os.environ.get("HAS_JOSH_K_SEAL_OF_APPROVAL", False):
    _TIMEOUT = 1.0
else:
    _TIMEOUT = 0.2


def event_loop(no_create=False):
    if sys.version_info.minor >= 10:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            if no_create:
                return None
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    return asyncio.get_event_loop()


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if self.path == "/slow":
            try:
                time.sleep(5)
                self.send_response(200)
                self.end_headers()
            except SystemExit:
                pass
            return
        return super(RequestHandler, self).do_GET()

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        body = self.rfile.read(content_length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def _run(conn):
    os.chdir(HERE)
    socketserver.TCPServer.allow_reuse_address = True
    attempts = 0
    httpd = None
    error = None

    while attempts < 3:
        try:
            httpd = socketserver.TCPServer(("", 0), RequestHandler)
            break
        except Exception as e:
            error = e
            attempts += 1
            time.sleep(0.1)

    if httpd is None:
        raise OSError("Could not start the coserver: %s" % str(error))

    def _shutdown(*args, **kw):
        httpd.server_close()
        sys.exit(0)

    conn.send(httpd.server_address[1])
    conn.close()
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    httpd.serve_forever()


def run_server():
    """Running in a subprocess to avoid any interference"""
    parent, child = multiprocess.Pipe()
    p = multiprocess.Process(target=functools.partial(_run, child))
    p.start()
    start = time.time()
    connected = False
    port = parent.recv()
    parent.close()
    os.environ["TEST_PORT"] = str(port)

    while time.time() - start < 5 and not connected:
        try:
            conn = HTTPConnection("localhost", port)
            conn.request("GET", "/")
            conn.getresponse()
            connected = True
        except Exception:
            time.sleep(0.1)
    if not connected:
        os.kill(p.pid, signal.SIGTERM)
        p.join(timeout=1.0)
        raise OSError("Could not connect to coserver")
    return p, port


@contextmanager
def coserver():
    process, port = run_server()
    try:
        yield port
    finally:
        os.kill(process.pid, signal.SIGTERM)
        process.join(timeout=1.0)
        process.terminate()


def _respkw():
    from aiohttp.helpers import TimerNoop

    return {
        "request_info": None,
        "writer": None,
        "continue100": None,
        "timer": TimerNoop(),
        "traces": [],
        "loop": event_loop(),
        "session": None,
    }


def Response(method="GET", status=200, body=b"***"):
    response = LoggedClientResponse(method, URL("/"), **_respkw())
    response.status = status
    response.reason = ""
    response.code = status
    response.should_close = False
    response._headers = CIMultiDict({})
    response._raw_headers = []

    class Body:
        async def read(self):
            return body

        def feed_data(self, data):
            if body == b"":
                err = AttributeError(
                    "'EmptyStreamReader' object has no " "attribute 'unread_data'"
                )
                raise err
            pass

    response.content = Body()
    response._content = body

    return response


def Request(url="http://127.0.0.1/", method="GET", body=b"***", loop=None):
    if loop is None:
        loop = event_loop()
    request = LoggedClientRequest(method, URL(url), loop=loop)
    request.body = body
    return request


class TestLoop(unittest.TestCase):
    def setUp(self):
        self.old = dict(_SCENARIO)
        self.oldsetup = dict(_FIXTURES)
        util._STOP = False
        util._STOP_WHY = []
        util._TIMER = None
        self.policy = asyncio.get_event_loop_policy()
        _SCENARIO.clear()
        _FIXTURES.clear()

    def tearDown(self):
        _SCENARIO.clear()
        _FIXTURES.clear()
        _FIXTURES.update(self.oldsetup)
        asyncio.set_event_loop_policy(self.policy)

    def get_args(self, console=None):
        args = namedtuple("args", "verbose quiet duration exception")
        args.force_shutdown = False
        args.ramp_up = 0.0
        args.verbose = 1
        args.quiet = False
        args.duration = 0.2
        args.exception = True
        args.processes = 1
        args.debug = True
        args.workers = 1
        args.console = False
        args.statsd = False
        args.single_mode = None
        args.single_run = False
        args.max_runs = None
        args.delay = 0.0
        args.sizing = False
        args.sizing_tolerance = 0.0
        args.console_update = 0
        args.use_extension = []
        args.fail = None
        args.force_reconnection = False
        args.disable_dns_resolve = False

        if console is None:
            console = SharedConsole(interval=0)
        args.shared_console = console
        return args


def async_test(func):
    @functools.wraps(func)
    def _async_test(*args, **kw):
        oldloop = event_loop(no_create=True)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(True)
        console = SharedConsole(interval=0)
        results = Counters(
            "WORKER",
            "REACHED",
            "RATIO",
            "OK",
            "FAILED",
            "MINUTE_OK",
            "MINUTE_FAILED",
            "MAX_WORKERS",
            "SETUP_FAILED",
            "SESSION_SETUP_FAILED",
        )
        kw["loop"] = loop
        kw["console"] = console
        kw["results"] = results
        fut = asyncio.ensure_future(func(*args, **kw))
        try:
            loop.run_until_complete(fut)
        finally:
            loop.stop()
            loop.close()
            asyncio.set_event_loop(oldloop)

        return fut.result()

    return _async_test


def dedicatedloop(func):
    @functools.wraps(func)
    def _loop(*args, **kw):
        old_loop = event_loop()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return func(*args, **kw)
        finally:
            if not loop.is_closed():
                loop.stop()
                loop.close()
            asyncio.set_event_loop(old_loop)

    return _loop


def dedicatedloop_noclose(func):
    @functools.wraps(func)
    def _loop(*args, **kw):
        old_loop = event_loop()
        loop = asyncio.new_event_loop()
        loop.set_debug(True)
        loop._close = loop.close
        loop.close = lambda: None
        asyncio.set_event_loop(loop)
        try:
            return func(*args, **kw)
        finally:
            loop._close()
            asyncio.set_event_loop(old_loop)

    return _loop


def co_catch_output(func):
    @functools.wraps(func)
    def _co(*args, **kw):
        oldout, olderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = StringIO(), StringIO()
        try:
            return func(*args, **kw)
        finally:
            sys.stdout.seek(0)
            sys.stderr.seek(0)
            sys.stdout, sys.stderr = oldout, olderr

    return _co


@contextmanager
def catch_output():
    oldout, olderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = StringIO(), StringIO()
    try:
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout.seek(0)
        sys.stderr.seek(0)
        sys.stdout, sys.stderr = oldout, olderr


@contextmanager
def set_args(*args):
    old = list(sys.argv)
    sys.argv[:] = args
    oldout, olderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = StringIO(), StringIO()
    try:
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout.seek(0)
        sys.stderr.seek(0)
        sys.argv[:] = old
        sys.stdout, sys.stderr = oldout, olderr


@contextmanager
def catch_sleep(calls=None):
    original = asyncio.sleep
    if calls is None:
        calls = []

    async def _slept(delay, result=None, *, loop=None):
        # 86400 is the duration timer
        if delay not in (0, 86400):
            calls.append(delay)
        # forces a context switch
        await original(0)

    with patch("asyncio.sleep", _slept):
        yield calls


def patch_print(func):
    @patch("molotov.ui.console.SharedConsole.print")
    def _test(self, console_print, *args, **kw):
        def _get_output():
            calls = []
            for call in console_print.call_args_list:
                args, kwargs = call
                calls.append(args[0])
            return "".join(calls)

        return func(self, _get_output, *args, **kw)

    return _test


def patch_errors(func):
    @patch("molotov.ui.console.SharedConsole.print_error")
    def _test(self, console_print, *args, **kw):
        def _get_output():
            calls = []
            for call in console_print.call_args_list:
                args, kwargs = call
                calls.append(str(args[0]))
            return "".join(calls)

        return func(self, _get_output, *args, **kw)

    return _test
