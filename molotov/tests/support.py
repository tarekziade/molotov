import os
import asyncio
import unittest
import multiprocessing
import time
from contextlib import contextmanager
import functools
from collections import namedtuple

from aiohttp.client_reqrep import ClientResponse, URL
from multidict import CIMultiDict
from molotov.api import _SCENARIO, _SETUP
from molotov import fmwk


def run_server(port=8888):
    def _run():
        import http.server
        import socketserver
        Handler = http.server.SimpleHTTPRequestHandler
        httpd = socketserver.TCPServer(("", port), Handler)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

    p = multiprocessing.Process(target=_run)
    p.start()
    time.sleep(1.)
    return p


@contextmanager
def coserver(port=8888):
    p = run_server(port)
    try:
        yield
    finally:
        os.kill(p.pid, 9)
        p.join()


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

    response.content = Body()
    response._content = body

    return response


class TestLoop(unittest.TestCase):
    def setUp(self):
        self.old = list(_SCENARIO)
        self.oldsetup = list(_SETUP)
        fmwk._STOP = False

    def tearDown(self):
        _SCENARIO[:] = self.old
        _SETUP[:] = self.oldsetup

    def get_args(self):
        args = namedtuple('args', 'verbose quiet duration exception')
        args.verbose = True
        args.quiet = False
        args.duration = 1
        args.exception = True
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
