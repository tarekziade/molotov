from time import perf_counter
import socket
from urllib.parse import urlparse
import asyncio
import functools

from aiohttp.client import ClientSession, ClientRequest, ClientResponse
from aiohttp import TCPConnector

from molotov.util import resolve
from molotov.listeners import StdoutListener, EventSender


_HOST = socket.gethostname()


class LoggedClientRequest(ClientRequest):
    """Printable Request.
    """

    logged_session = None

    async def send(self, *args, **kw):
        if self.logged_session:
            event = self.logged_session.send_event("sending_request", request=self)
            asyncio.ensure_future(event)
        response = await super(LoggedClientRequest, self).send(*args, **kw)
        response.request = self
        return response


class LoggedClientResponse(ClientResponse):
    request = None


class RequestContext:
    def __init__(self, coro):
        self.coro = coro

    def send(self, arg):
        return self.coro.send(arg)

    def throw(self, arg):
        self.coro.throw(arg)

    def close(self):
        return self.coro.close()

    def __await__(self):
        ret = self.coro.__await__()
        return ret

    def __iter__(self):
        return self.__await__()

    async def __aenter__(self):
        self._resp = await self.coro
        return self._resp

    async def __aexit__(self, exc_type, exc, tb):
        self._resp.release()


class LoggedClientSession:
    def __init__(self, loop, console, verbose=0, statsd=None, resolve_dns=True, **kw):
        self.client_loop = loop
        connector = kw.pop("connector", None)
        if connector is None:
            connector = TCPConnector(loop=loop, limit=None)

        request_class = LoggedClientRequest
        request_class.logged_session = self
        request_class.verbose = verbose
        request_class.response_class = LoggedClientResponse

        self.session = ClientSession(
            loop=loop,
            request_class=request_class,
            response_class=LoggedClientResponse,
            connector=connector,
            **kw
        )
        self.console = console
        self.verbose = verbose
        self.statsd = statsd
        self.eventer = EventSender(
            console,
            [
                StdoutListener(
                    verbose=self.verbose, console=self.console, loop=self.client_loop
                )
            ],
        )
        self._resolve_dns = resolve_dns

    async def send_event(self, event, **options):
        await self.eventer.send_event(event, session=self, **options)

    def request(self, method, url, **kwargs):
        return RequestContext(self._request(method, url, **kwargs))

    async def _request(self, *args, **kw):
        args = list(args)
        if self._resolve_dns:
            resolved = await resolve(args[1], loop=self.client_loop)
            args[1] = resolved[0]
        args = tuple(args)
        req = self.session._request

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

    get = functools.partialmethod(request, "get")
    connect = functools.partialmethod(request, "connect")
    head = functools.partialmethod(request, "head")
    delete = functools.partialmethod(request, "delete")
    options = functools.partialmethod(request, "options")
    patch = functools.partialmethod(request, "patch")
    post = functools.partialmethod(request, "post")
    put = functools.partialmethod(request, "put")
    trace = functools.partialmethod(request, "trace")

    def __getattr__(self, name):
        return getattr(self.session, name)

    def __enter__(self):
        raise TypeError("Use async with instead")

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
