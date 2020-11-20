from time import perf_counter
import socket
from urllib.parse import urlparse
import asyncio
import functools
from types import SimpleNamespace

from aiohttp.client import ClientSession, ClientRequest, ClientResponse
from aiohttp import TCPConnector, TraceConfig

from molotov.util import resolve
from molotov.listeners import StdoutListener, EventSender


_HOST = socket.gethostname()


class LoggedClientRequest(ClientRequest):
    """Printable Request.
    """

    tracer = None

    async def send(self, *args, **kw):
        if self.tracer:
            event = self.tracer.send_event("sending_request", request=self)
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


class SessionTracer(TraceConfig):
    def __init__(self, loop, console, verbose, statsd, resolve_dns):
        super().__init__(trace_config_ctx_factory=self._trace_config_ctx_factory)
        self.loop = loop
        self.console = console
        self.verbose = verbose
        self.statsd = statsd
        self.worker_id = self.step = self.args = None
        self.eventer = EventSender(
            console,
            [
                StdoutListener(
                    verbose=self.verbose, console=self.console, loop=self.loop
                )
            ],
        )
        self._resolve_dns = resolve_dns
        self.on_request_start.append(self._request_start)
        self.on_request_end.append(self._request_end)

    def _trace_config_ctx_factory(self, trace_request_ctx):
        return SimpleNamespace(trace_request_ctx=trace_request_ctx, statsd=self.statsd)

    async def send_event(self, event, **options):
        await self.eventer.send_event(event, session=self, **options)

    async def _request_start(self, session, trace_config_ctx, params):
        print("Starting request")
        # if self._resolve_dns:
        #    params.url = await resolve(params.url, loop=self.loop)
        if trace_config_ctx.statsd:
            prefix = "molotov.%(hostname)s.%(method)s.%(host)s.%(path)s"
            data = {
                "method": params.method,
                "hostname": _HOST,
                "host": params.url.host,
                "path": params.url.path,
            }
            label = prefix % data
            trace_config_ctx.start = perf_counter()
            trace_config_ctx.label = label
            trace_config_ctx.data = data

    async def _request_end(self, session, trace_config_ctx, params):
        print("Ending request")
        if trace_config_ctx.statsd:
            duration = int((perf_counter() - trace_config_ctx.start) * 1000)
            trace_config_ctx.statsd.timing(trace_config_ctx.label, value=duration)
            trace_config_ctx.statsd.increment(
                trace_config_ctx.label + "." + str(params.response.status)
            )
        await self.send_event(
            "response_received",
            response=params.response,
            request=params.response.request,
        )


def get_session(loop, console, verbose=0, statsd=None, resolve_dns=True, **kw):
    trace_config = SessionTracer(loop, console, verbose, statsd, resolve_dns)

    connector = kw.pop("connector", None)
    if connector is None:
        connector = TCPConnector(loop=loop, limit=None)

    request_class = LoggedClientRequest
    request_class.verbose = verbose
    request_class.response_class = LoggedClientResponse
    request_class.tracer = trace_config
    session = ClientSession(
        loop=loop,
        request_class=request_class,
        response_class=LoggedClientResponse,
        connector=connector,
        trace_configs=[trace_config],
        **kw
    )

    return session


def get_context(session):
    for trace in session._trace_configs:
        if isinstance(trace, SessionTracer):
            return trace
    return None
