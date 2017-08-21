import gzip
from aiohttp.client_reqrep import ClientRequest
from yarl import URL
from unittest.mock import patch

import molotov.session
from molotov.tests.support import coserver, Response
from molotov.tests.support import TestLoop, async_test, serialize


class TestLoggedClientSession(TestLoop):

    def _get_session(self, *args, **kw):
        return molotov.session.LoggedClientSession(*args, **kw)

    @async_test
    async def test_empty_response(self, loop, console, results):
        async with self._get_session(loop, console,
                                     verbose=2) as session:
            binary_body = b''
            response = Response(body=binary_body)
            await session.print_response(response)

        await serialize(console)

    @async_test
    async def test_encoding(self, loop, console, results):
        async with self._get_session(loop, console,
                                     verbose=2) as session:
            binary_body = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00'
            response = Response(body=binary_body)
            await session.print_response(response)

        res = await serialize(console)
        wanted = "can't display this body"
        self.assertTrue(wanted in res)

    @async_test
    async def test_request(self, loop, console, results):
        with coserver():
            async with self._get_session(loop, console,
                                         verbose=2) as session:
                async with session.get('http://localhost:8888') as resp:
                    self.assertEqual(resp.status, 200)

            res = await serialize(console)
            self.assertTrue('GET http://127.0.0.1:8888' in res)

    @async_test
    async def test_not_verbose(self, loop, console, results):
        async with self._get_session(loop, console,
                                     verbose=1) as session:
            req = ClientRequest('GET', URL('http://example.com'))
            await session.print_request(req)

            response = Response(body='')
            await session.print_response(response)

        res = await serialize(console)
        self.assertEqual(res, '')

    @async_test
    async def test_gzipped_request(self, loop, console, results):
        async with self._get_session(loop, console,
                                     verbose=2) as session:
            binary_body = gzip.compress(b'some gzipped data')
            req = ClientRequest('GET', URL('http://example.com'),
                                data=binary_body)
            req.headers['Content-Encoding'] = 'gzip'
            await session.print_request(req)

        res = await serialize(console)
        self.assertTrue("Binary" in res, res)

    @async_test
    async def test_file_request(self, loop, console, results):
        async with self._get_session(loop, console,
                                     verbose=2) as session:
            with open(__file__) as f:
                req = ClientRequest('POST', URL('http://example.com'),
                                    data=f)
                req.headers['Content-Encoding'] = 'something/bin'
                await session.print_request(req)

        res = await serialize(console)
        self.assertTrue("File" in res, res)

    @async_test
    async def test_binary_file_request(self, loop, console, results):
        async with self._get_session(loop, console,
                                     verbose=2) as session:
            with open(__file__, 'rb') as f:
                req = ClientRequest('POST', URL('http://example.com'),
                                    data=f)
                req.headers['Content-Encoding'] = 'something/bin'
                await session.print_request(req)

        res = await serialize(console)
        self.assertTrue("File" in res, res)

    @async_test
    async def test_gzipped_response(self, loop, console, results):
        async with self._get_session(loop, console,
                                     verbose=2) as session:
            binary_body = gzip.compress(b'some gzipped data')
            response = Response(body=binary_body)
            response.headers['Content-Encoding'] = 'gzip'
            await session.print_response(response)

        res = await serialize(console)
        self.assertTrue("Binary" in res, res)

    @async_test
    async def test_cantread_request(self, loop, console, results):
        async with self._get_session(loop, console,
                                     verbose=2) as session:
            binary_body = gzip.compress(b'some gzipped data')
            req = ClientRequest('GET', URL('http://example.com'),
                                data=binary_body)
            await session.print_request(req)

        res = await serialize(console)
        self.assertTrue("display this body" in res, res)

    @async_test
    async def test_old_request_version(self, loop, console, results):

        orig_import = __import__

        def import_mock(name, *args, **kw):
            if name == 'aiohttp.payload':
                raise ImportError()
            return orig_import(name, *args, **kw)

        with patch('builtins.__import__', side_effect=import_mock):
            async with self._get_session(loop, console,
                                         verbose=2) as session:
                body = "ok man"
                req = ClientRequest('GET', URL('http://example.com'),
                                    data=body)
                req.body = req.body._value
                await session.print_request(req)

        res = await serialize(console)
        self.assertTrue("ok man" in res, res)
