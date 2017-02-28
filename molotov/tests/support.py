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

from aiohttp.client_reqrep import ClientResponse, URL
from multidict import CIMultiDict
from molotov.api import _SCENARIO, _FIXTURES
from molotov import fmwk


def run_server(port=8888):
    """Running in a subprocess to avoid any interference
    """
    def _run():
        import http.server
        import socketserver
        import signal
        import sys

        socketserver.TCPServer.allow_reuse_address = True
        Handler = http.server.SimpleHTTPRequestHandler
        attempts = 0
        httpd = None

        while attempts < 3:
            try:
                httpd = socketserver.TCPServer(("", port), Handler)
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
            _CO['server'] = None


def Response(method='GET', status=200, body=b'***'):
    response = ClientResponse(method, URL('/'))
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
            pass

    response.content = Body()
    response._content = body

    return response


class TestLoop(unittest.TestCase):
    def setUp(self):
        self.old = list(_SCENARIO)
        self.oldsetup = dict(_FIXTURES)
        fmwk._STOP = False

    def tearDown(self):
        _SCENARIO[:] = self.old
        _FIXTURES.clear()
        _FIXTURES.update(self.oldsetup)

    def get_args(self):
        args = namedtuple('args', 'verbose quiet duration exception')
        args.verbose = 1
        args.quiet = False
        args.duration = 1
        args.exception = True
        args.processes = 1
        args.debug = True
        args.workers = 1
        args.console = True
        args.statsd = False
        args.single_mode = None
        args.max_runs = None
        return args


def async_test(func):
    @functools.wraps(func)
    def _async_test(*args, **kw):
        cofunc = asyncio.coroutine(func)
        oldloop = asyncio.get_event_loop()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(True)
        kw['loop'] = loop
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
            asyncio.set_event_loop(old_loop)
    return _loop


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
