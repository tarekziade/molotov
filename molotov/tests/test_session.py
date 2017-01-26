import unittest
import asyncio
from molotov.session import LoggedClientSession
from molotov.tests.support import coserver, Response


class TestLoggedClientSession(unittest.TestCase):

    def test_encoding(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_debug(True)

        async def _test_encoding():
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

        loop.run_until_complete(_test_encoding())

    def test_request(self):
        with coserver():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.set_debug(True)

            async def _test_request():
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

            loop.run_until_complete(_test_request())
