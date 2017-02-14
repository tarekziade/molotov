import gzip
import asyncio

from aiohttp.client_reqrep import ClientRequest
from yarl import URL

from molotov.session import LoggedClientSession
from molotov.tests.support import coserver, Response
from molotov.tests.support import TestLoop, async_test


class TestLoggedClientSession(TestLoop):

    @async_test
    async def test_encoding(self, loop):
        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream,
                                       verbose=True) as session:
            binary_body = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00'
            response = Response(body=binary_body)
            await session.print_response(response)

        res = []
        while stream.qsize() > 0:
            line = await stream.get()
            res.append(line)

        wanted = "can't display this body"
        self.assertTrue(wanted in res[1])

    @async_test
    async def test_request(self, loop):
        with coserver():
            stream = asyncio.Queue()
            async with LoggedClientSession(loop, stream,
                                           verbose=True) as session:
                async with session.get('http://localhost:8888') as resp:
                    self.assertEqual(resp.status, 200)

            res = []
            while stream.qsize() > 0:
                line = await stream.get()
                res.append(line)

            self.assertTrue('GET http://127.0.0.1:8888' in res[1])

    @async_test
    async def test_gzipped_request(self, loop):
        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream,
                                       verbose=True) as session:
            binary_body = gzip.compress(b'some gzipped data')
            req = ClientRequest('GET', URL('http://example.com'),
                                data=binary_body)
            req.headers['Content-Encoding'] = 'gzip'
            await session.print_request(req)

        res = []
        while stream.qsize() > 0:
            line = await stream.get()
            res.append(line)

        self.assertTrue("Binary" in res[1], res)

    @async_test
    async def test_cantread_request(self, loop):
        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream,
                                       verbose=True) as session:
            binary_body = gzip.compress(b'some gzipped data')
            req = ClientRequest('GET', URL('http://example.com'),
                                data=binary_body)
            await session.print_request(req)

        res = []
        while stream.qsize() > 0:
            line = await stream.get()
            res.append(line)

        self.assertTrue("display this body" in res[1], res)
