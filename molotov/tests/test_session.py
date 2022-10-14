import gzip
from aiohttp.client_reqrep import ClientRequest
from yarl import URL
from unittest.mock import patch

from molotov.listeners import BaseListener
import molotov.session
from molotov.session import get_eventer
from molotov.tests.support import coserver, Response, Request
from molotov.tests.support import TestLoop, async_test, patch_print, patch_errors


class TestLoggedClientSession(TestLoop):
    def _get_session(self, *args, **kw):
        return molotov.session.get_session(*args, **kw)

    @async_test
    async def test_add_listener(self, loop, console, results):
        class MyListener(BaseListener):
            def __init__(self):
                self.responses = []

            def on_response_received(self, **options):
                self.responses.append(options["response"])

        lis = MyListener()
        async with self._get_session(loop, console, verbose=2) as session:
            get_eventer(session).add_listener(lis)
            request = Request()
            binary_body = b""
            response = Response(body=binary_body)
            await get_eventer(session).send_event(
                "response_received", response=response, request=request
            )

        self.assertEqual(lis.responses, [response])

    @async_test
    async def test_empty_response(self, loop, console, results):
        async with self._get_session(loop, console, verbose=2) as session:
            request = Request()
            binary_body = b""
            response = Response(body=binary_body)
            await get_eventer(session).send_event(
                "response_received", response=response, request=request
            )

    @patch_errors
    @async_test
    async def test_encoding(self, console_print, loop, console, results):

        async with self._get_session(loop, console, verbose=2) as session:
            request = Request()
            binary_body = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00"
            response = Response(body=binary_body)
            await get_eventer(session).send_event(
                "response_received", response=response, request=request
            )

        res = console_print()
        wanted = "can't display this body"
        self.assertTrue(wanted in res)

    @patch_errors
    @async_test
    async def test_request(self, console_print, loop, console, results):
        with coserver() as port:
            async with self._get_session(loop, console, verbose=2) as session:
                async with session.get(f"http://localhost:{port}") as resp:
                    self.assertEqual(resp.status, 200)

            res = console_print()
            self.assertTrue("Directory listing" in res, res)

    @patch_print
    @async_test
    async def test_not_verbose(self, console_print, loop, console, results):
        async with self._get_session(loop, console, verbose=1) as session:
            req = ClientRequest("GET", URL("http://example.com"), loop=loop)
            await get_eventer(session).send_event("sending_request", request=req)

            response = Response(body="")
            request = Request()
            await get_eventer(session).send_event(
                "response_received", response=response, request=request
            )

        self.assertEqual(console_print(), "")

    @patch_errors
    @async_test
    async def test_gzipped_request(self, console_print, loop, console, results):
        async with self._get_session(loop, console, verbose=2) as session:
            binary_body = gzip.compress(b"some gzipped data")
            req = ClientRequest(
                "GET", URL("http://example.com"), data=binary_body, loop=loop
            )
            req.headers["Content-Encoding"] = "gzip"
            await get_eventer(session).send_event("sending_request", request=req)

        res = console_print()
        self.assertTrue("Binary" in res, res)

    @patch_errors
    @async_test
    async def test_file_request(self, console_print, loop, console, results):
        async with self._get_session(loop, console, verbose=2) as session:
            with open(__file__) as f:
                req = ClientRequest(
                    "POST", URL("http://example.com"), data=f, loop=loop
                )
                req.headers["Content-Encoding"] = "something/bin"
                await get_eventer(session).send_event("sending_request", request=req)

        res = console_print()
        self.assertTrue("File" in res, res)

    @patch_errors
    @async_test
    async def test_binary_file_request(self, console_print, loop, console, results):
        async with self._get_session(loop, console, verbose=2) as session:
            with open(__file__, "rb") as f:
                req = ClientRequest(
                    "POST", URL("http://example.com"), data=f, loop=loop
                )
                req.headers["Content-Encoding"] = "something/bin"
                await get_eventer(session).send_event("sending_request", request=req)

        calls = console_print()
        self.assertTrue("File" in calls, calls)

    @patch_errors
    @async_test
    async def test_gzipped_response(self, console_print, loop, console, results):
        async with self._get_session(loop, console, verbose=2) as session:
            request = Request()
            binary_body = gzip.compress(b"some gzipped data")
            response = Response(body=binary_body)
            response.headers["Content-Encoding"] = "gzip"
            await get_eventer(session).send_event(
                "response_received", response=response, request=request
            )

        res = console_print()
        self.assertTrue("Binary" in res, res)

    @patch_errors
    @async_test
    async def test_cantread_request(self, console_print, loop, console, results):
        async with self._get_session(loop, console, verbose=2) as session:
            binary_body = gzip.compress(b"some gzipped data")
            req = ClientRequest(
                "GET", URL("http://example.com"), data=binary_body, loop=loop
            )
            await get_eventer(session).send_event("sending_request", request=req)

        res = console_print()
        self.assertTrue("display this body" in res, res)

    @patch_errors
    @async_test
    async def test_old_request_version(self, console_print, loop, console, results):

        orig_import = __import__

        def import_mock(name, *args, **kw):
            if name == "aiohttp.payload":
                raise ImportError()
            return orig_import(name, *args, **kw)

        with patch("builtins.__import__", side_effect=import_mock):
            async with self._get_session(loop, console, verbose=2) as session:
                body = "ok man"
                req = ClientRequest(
                    "GET", URL("http://example.com"), data=body, loop=loop
                )
                req.body = req.body._value
                await get_eventer(session).send_event("sending_request", request=req)

        res = console_print()
        self.assertTrue("ok man" in res, res)
