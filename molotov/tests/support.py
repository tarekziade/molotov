import asyncio
import unittest
import multiprocessing
import time
from contextlib import contextmanager
import functools

from aiohttp.client_reqrep import ClientResponse, URL
from multidict import CIMultiDict
from molotov.api import _SCENARIO


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
        p.terminate()


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

    def tearDown(self):
        _SCENARIO[:] = self.old


def async_test(func):
    @functools.wraps(func)
    def _async_test(*args, **kw):
        cofunc = asyncio.coroutine(func)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(True)
        kw['loop'] = loop
        try:
            loop.run_until_complete(cofunc(*args, **kw))
        finally:
            loop.close()
    return _async_test
