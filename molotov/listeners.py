import io

import aiohttp
from aiohttp.streams import DataQueue

from molotov.api import get_fixture

_UNREADABLE = "***WARNING: Molotov can't display this body***"
_BINARY = "**** Binary content ****"
_FILE = "**** File content ****"
_COMPRESSED = ("gzip", "compress", "deflate", "identity", "br")


class BaseListener(object):
    async def __call__(self, event, **options):
        attr = getattr(self, "on_" + event, None)
        if attr is not None:
            await attr(**options)


class Writer:
    def __init__(self):
        self.buffer = bytearray()

    async def write(self, data):
        self.buffer.extend(data)


class StdoutListener(BaseListener):
    def __init__(self, **options):
        self.verbose = options.get("verbose", 0)
        self.loop = options.pop("loop", None)
        self.console = options["console"]

    async def _body2str(self, body):
        if body is None:
            return ""

        if isinstance(body, aiohttp.multipart.MultipartWriter):
            writer = Writer()
            await body.write(writer)
            body = writer.buffer.decode("utf8")

        try:
            from aiohttp.payload import Payload
        except ImportError:
            Payload = None

        if Payload is not None and isinstance(body, Payload):
            body = body._value

        if isinstance(body, io.IOBase):
            return _FILE

        if not isinstance(body, str):
            try:
                body = str(body, "utf8")
            except UnicodeDecodeError:
                return _UNREADABLE

        return body

    async def on_sending_request(self, session, request):
        if self.verbose < 2:
            return
        raw = ">" * 45
        raw += "\n" + request.method + " " + str(request.url)
        if len(request.headers) > 0:
            headers = "\n".join("%s: %s" % (k, v) for k, v in request.headers.items())
            raw += "\n" + headers
        if request.headers.get("Content-Encoding") in _COMPRESSED:
            raw += "\n\n" + _BINARY + "\n"
        elif request.body:
            str_body = await self._body2str(request.body)
            raw += "\n\n" + str_body + "\n"

        self.console.print(raw)

    async def on_response_received(self, session, response, request):
        if self.verbose < 2:
            return
        raw = "\n" + "=" * 45 + "\n"
        raw += "HTTP/1.1 %d %s\n" % (response.status, response.reason)
        items = response.headers.items()
        headers = "\n".join("{}: {}".format(k, v) for k, v in items)
        raw += headers
        if response.headers.get("Content-Encoding") in _COMPRESSED:
            raw += "\n\n" + _BINARY
        elif response.content:
            content = await response.content.read()
            if len(content) > 0:
                # put back the data in the content
                response.content = DataQueue(loop=self.loop)
                response.content.feed_data(content)
                response.content.feed_eof()
                try:
                    raw += "\n\n" + content.decode()
                except UnicodeDecodeError:
                    raw += "\n\n" + _UNREADABLE
            else:
                raw += "\n\n"

        raw += "\n" + "<" * 45 + "\n"
        self.console.print(raw)


class CustomListener(object):
    def __init__(self, fixture):
        self.fixture = fixture

    async def __call__(self, event, **options):
        await self.fixture(event, **options)


class EventSender(object):
    def __init__(self, console, listeners=None):
        self.console = console
        if listeners is None:
            listeners = []
        self._listeners = listeners
        self._stopped = False

        fixture_listeners = get_fixture("events")
        if fixture_listeners is not None:
            for listener in fixture_listeners:
                self.add_listener(CustomListener(listener))

    def add_listener(self, listener):
        self._listeners.append(listener)

    async def stop(self):
        self._stopped = True

    def stopped(self):
        return self._stopped

    async def send_event(self, event, *args, **options):
        for listener in self._listeners:
            try:
                await listener(event, *args, **options)
            except Exception as e:
                self.console.print_error(e)
