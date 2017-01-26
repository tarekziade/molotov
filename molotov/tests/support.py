import multiprocessing
import time
from contextlib import contextmanager

from aiohttp.client_reqrep import ClientResponse, URL
from multidict import CIMultiDict


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
