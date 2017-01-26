import unittest
import asyncio
from io import StringIO

from aiohttp.client_reqrep import ClientResponse, URL
from molotov.session import LoggedClientSession


class TestLoggedClientSession(unittest.TestCase):

    def test_encoding(self):

        loop = asyncio.get_event_loop()

        async def _test_encoding():
            stream = asyncio.Queue()
            session = LoggedClientSession(loop, stream, verbose=True)
            response = ClientResponse('GET', URL('/'))
            response.status = 200
            response.reason = ''
            response.headers = {}

            class BinaryBody:
                async def read(self):
                    return b'MZ\x90\x00\x03\x00\x00\x00\x04\x00'

            response.content = BinaryBody()
            await session.print_response(response)
            res = []
            while stream.qsize() > 0:
                line = await stream.get()
                res.append(line)

            self.assertTrue('Could not decode body' in res[1])

        loop.run_until_complete(_test_encoding())
