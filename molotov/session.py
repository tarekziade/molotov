from time import perf_counter
import socket
from urllib.parse import urlparse
import asyncio
from aiohttp.client import ClientSession, ClientRequest, ClientResponse
from aiohttp import TCPConnector

from molotov.util import resolve
from molotov.listeners import StdoutListener, EventSender


_HOST = socket.gethostname()


class LoggedClientRequest(ClientRequest):
    """Printable Request.
    """

    session = None

    async def send(self, *args, **kw):
        if self.session:
            event = self.session.send_event("sending_request", request=self)
            asyncio.ensure_future(event)
        response = await super(LoggedClientRequest, self).send(*args, **kw)
        response.request = self
        return response


class LoggedClientResponse(ClientResponse):
    request = None


class LoggedClientSession(ClientSession):
    """Session with printable requests and responses.
    """

    def __init__(self, loop, console, verbose=0, statsd=None, resolve_dns=True, **kw):
        connector = kw.pop("connector", None)
        if connector is None:
            connector = TCPConnector(loop=loop, limit=None)
        super(LoggedClientSession, self).__init__(
            loop=loop,
            request_class=LoggedClientRequest,
            response_class=LoggedClientResponse,
            connector=connector,
            **kw
        )
        self.console = console
        self.request_class = LoggedClientRequest
        self.request_class.verbose = verbose
        self.verbose = verbose
        self.request_class.session = self
        self.request_class.response_class = LoggedClientResponse
        self.statsd = statsd
        self.eventer = EventSender(
            console, [StdoutListener(verbose=self.verbose, console=self.console)]
        )
        self._resolve_dns = resolve_dns

    async def send_event(self, event, **options):
        await self.eventer.send_event(event, session=self, **options)

    def _dns_lookup(self, url):
        return resolve(url)[0]

    async def _request(self, *args, **kw):
        args = list(args)
        if self._resolve_dns:
            args[1] = self._dns_lookup(args[1])
        args = tuple(args)
        req = super(LoggedClientSession, self)._request

        if self.statsd:
            prefix = "molotov.%(hostname)s.%(method)s.%(host)s.%(path)s"
            meth, url = args[:2]
            url = urlparse(url)
            path = url.path != "" and url.path or "/"

            data = {
                "method": meth,
                "hostname": _HOST,
                "host": url.netloc.split(":")[0],
                "path": path,
            }

            label = prefix % data

            async def request():
                start = perf_counter()
                resp = await req(*args, **kw)
                duration = int((perf_counter() - start) * 1000)
                self.statsd.timing(label, value=duration)
                self.statsd.increment(label + "." + str(resp.status))
                return resp

            resp = await request()
        else:
            resp = await req(*args, **kw)

        await self.send_event("response_received", response=resp, request=resp.request)
        return resp
