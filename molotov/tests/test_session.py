import gzip
import asyncio

from aiohttp.client_reqrep import ClientRequest
from yarl import URL

from molotov.session import LoggedClientSession
from molotov.tests.support import coserver, Response
from molotov.tests.support import TestLoop, async_test


async def serialize(stream):
    res = []
    while stream.qsize() > 0:
        line = await stream.get()
        res.append(line)
    return res


class TestLoggedClientSession(TestLoop):

    @async_test
    async def test_empty_response(self, loop):
        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream,
                                       verbose=2) as session:
            binary_body = b''
            response = Response(body=binary_body)
            await session.print_response(response)

        await serialize(stream)

    @async_test
    async def test_encoding(self, loop):
        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream,
                                       verbose=2) as session:
            binary_body = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00'
            response = Response(body=binary_body)
            await session.print_response(response)

        res = await serialize(stream)
        wanted = "can't display this body"
        self.assertTrue(wanted in res[1])

    @async_test
    async def test_request(self, loop):
        with coserver():
            stream = asyncio.Queue()
            async with LoggedClientSession(loop, stream,
                                           verbose=2) as session:
                async with session.get('http://localhost:8888') as resp:
                    self.assertEqual(resp.status, 200)

            res = await serialize(stream)
            self.assertTrue('GET http://127.0.0.1:8888' in res[1])

    @async_test
    async def test_not_verbose(self, loop):
        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream,
                                       verbose=1) as session:
            req = ClientRequest('GET', URL('http://example.com'))
            await session.print_request(req)

            response = Response(body='')
            await session.print_response(response)

        res = await serialize(stream)
        self.assertEqual(res, [])

    @async_test
    async def test_gzipped_request(self, loop):
        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream,
                                       verbose=2) as session:
            binary_body = gzip.compress(b'some gzipped data')
            req = ClientRequest('GET', URL('http://example.com'),
                                data=binary_body)
            req.headers['Content-Encoding'] = 'gzip'
            await session.print_request(req)

        res = await serialize(stream)
        self.assertTrue("Binary" in res[1], res)

    @async_test
    async def test_gzipped_response(self, loop):
        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream,
                                       verbose=2) as session:
            binary_body = gzip.compress(b'some gzipped data')
            response = Response(body=binary_body)
            response.headers['Content-Encoding'] = 'gzip'
            await session.print_response(response)

        res = await serialize(stream)
        self.assertTrue("Binary" in res[1], res)

    @async_test
    async def test_cantread_request(self, loop):
        stream = asyncio.Queue()
        async with LoggedClientSession(loop, stream,
                                       verbose=2) as session:
            binary_body = gzip.compress(b'some gzipped data')
            req = ClientRequest('GET', URL('http://example.com'),
                                data=binary_body)
            await session.print_request(req)

        res = await serialize(stream)
        self.assertTrue("display this body" in res[1], res)
