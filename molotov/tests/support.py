import sys
import signal
import os
import asyncio
import unittest
import multiprocessing
import time
from contextlib import contextmanager
import functools
from collections import namedtuple
from http.client import HTTPConnection
from io import StringIO
import http.server
import socketserver
import pytest
from queue import Empty
from unittest.mock import patch

from aiohttp.helpers import TimerNoop
from aiohttp.client_reqrep import URL
from multidict import CIMultiDict
from molotov.api import _SCENARIO, _FIXTURES
from molotov import util
from molotov.run import PYPY
from molotov.session import LoggedClientRequest, LoggedClientResponse
from molotov.sharedconsole import SharedConsole
from molotov.sharedcounter import SharedCounters


HERE = os.path.dirname(__file__)

skip_pypy = pytest.mark.skipif(PYPY,
                               reason='could not make work on pypy')
only_pypy = pytest.mark.skipif(not PYPY, reason='only pypy')

if os.environ.get('HAS_JOSH_K_SEAL_OF_APPROVAL', False):
    _TIMEOUT = 1.
else:
    _TIMEOUT = .2


async def serialize(console):
    res = []
    while True:
        try:
            res.append(console._stream.get(block=True, timeout=_TIMEOUT))
        except Empty:
            break
    return ''.join(res)


class HandlerRedirect(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header('Location', '/')
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
        return super(HandlerRedirect, self).do_GET()


def run_server(port=8888):
    """Running in a subprocess to avoid any interference
    """
    def _run():
        os.chdir(HERE)
        socketserver.TCPServer.allow_reuse_address = True
        attempts = 0
        httpd = None

        while attempts < 3:
            try:
                httpd = socketserver.TCPServer(("", port), HandlerRedirect)
                break
            except Exception:
                attempts += 1
                time.sleep(.1)

        if httpd is None:
            raise OSError("Could not start the coserver")

        def _shutdown(*args, **kw):
            httpd.server_close()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)
        httpd.serve_forever()

    p = multiprocessing.Process(target=_run)
    p.start()
    start = time.time()
    connected = False

    while time.time() - start < 5 and not connected:
        try:
            conn = HTTPConnection('localhost', 8888)
            conn.request("GET", "/")
            conn.getresponse()
            connected = True
        except Exception:
            time.sleep(.1)
    if not connected:
        os.kill(p.pid, signal.SIGTERM)
        p.join(timeout=1.)
        raise OSError('Could not connect to coserver')
    return p


_CO = {'clients': 0, 'server': None}


@contextmanager
def coserver(port=8888):
    if _CO['clients'] == 0:
        _CO['server'] = run_server(port)

    _CO['clients'] += 1
    try:
        yield
    finally:
        _CO['clients'] -= 1
        if _CO['clients'] == 0:
            os.kill(_CO['server'].pid, signal.SIGTERM)
            _CO['server'].join(timeout=1.)
            _CO['server'].terminate()
            _CO['server'] = None


def _respkw():
    return {'request_info': None,
            'writer': None,
            'continue100': None,
            'timer': TimerNoop(),
            'auto_decompress': True,
            'traces': [],
            'loop': asyncio.get_event_loop(),
            'session': None}


def Response(method='GET', status=200, body=b'***'):
    response = LoggedClientResponse(method, URL('/'), **_respkw())
    response.status = status
    response.reason = ''
    response.code = status
    response.should_close = False
    response.headers = CIMultiDict({})
    response.raw_headers = []

    class Body:
        async def read(self):
            return body

        def unread_data(self, data):
            if body == b'':
                err = AttributeError("'EmptyStreamReader' object has no "
                                     "attribute 'unread_data'")
                raise err
            pass

    response.content = Body()
    response._content = body

    return response


def Request(url="http://127.0.0.1/", method='GET', body=b'***'):
    request = LoggedClientRequest(method, URL(url))
    request.body = body
    return request


class TestLoop(unittest.TestCase):
    def setUp(self):
        self.old = dict(_SCENARIO)
        self.oldsetup = dict(_FIXTURES)
        util._STOP = False
        util._TIMER = None
        self.policy = asyncio.get_event_loop_policy()

    def tearDown(self):
        _SCENARIO.clear()
        _FIXTURES.clear()
        _FIXTURES.update(self.oldsetup)
        asyncio.set_event_loop_policy(self.policy)

    def get_args(self, console=None):
        args = namedtuple('args', 'verbose quiet duration exception')
        args.force_shutdown = False
        args.ramp_up = .0
        args.verbose = 1
        args.quiet = False
        args.duration = 5
        args.exception = True
        args.processes = 1
        args.debug = True
        args.workers = 1
        args.console = True
        args.statsd = False
        args.single_mode = None
        args.max_runs = None
        args.delay = .0
        args.sizing = False
        args.sizing_tolerance = .0
        args.console_update = 0
        args.use_extension = []
        args.fail = None
        args.force_reconnection = False

        if console is None:
            console = SharedConsole(interval=0)
        args.shared_console = console
        return args


def async_test(func):
    @functools.wraps(func)
    def _async_test(*args, **kw):
        cofunc = asyncio.coroutine(func)
        oldloop = asyncio.get_event_loop()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(True)
        console = SharedConsole(interval=0)
        results = SharedCounters('WORKER', 'REACHED', 'RATIO', 'OK',
                                 'FAILED', 'MINUTE_OK', 'MINUTE_FAILED')
        kw['loop'] = loop
        kw['console'] = console
        kw['results'] = results
        try:
            loop.run_until_complete(cofunc(*args, **kw))
        finally:
            loop.stop()
            loop.close()
            asyncio.set_event_loop(oldloop)
    return _async_test


def dedicatedloop(func):
    @functools.wraps(func)
    def _loop(*args, **kw):
        old_loop = asyncio.get_event_loop()
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
        old_loop = asyncio.get_event_loop()
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

    with patch('asyncio.sleep', _slept):
        yield calls
