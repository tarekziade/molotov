import socket
from time import perf_counter
from types import SimpleNamespace

from aiohttp import TCPConnector, TraceConfig
from aiohttp.client import ClientRequest, ClientResponse, ClientSession

from molotov.api import create_session
from molotov.listeners import EventSender, StdoutListener

_HOST = socket.gethostname()


class LoggedClientResponse(ClientResponse):
    request = None


class Context:
    def __init__(self, statsd=None, args=None, worker_id=None, step=None):
        self.statsd = statsd
        self.args = args
        self.worker_id = worker_id
        self.step = step


class SessionTracer(TraceConfig):
    def __init__(self, loop, console, verbose, statsd):
        super().__init__(trace_config_ctx_factory=self._trace_config_ctx_factory)  # type: ignore
        self.loop = loop
        self.console = console
        self.verbose = verbose
        self.eventer = EventSender(
            console,
            [StdoutListener(verbose=self.verbose, console=self.console, loop=self.loop)],
        )
        self.on_request_start.append(self._request_start)
        self.on_request_end.append(self._request_end)
        self.context = Context(statsd=statsd)

    def _trace_config_ctx_factory(self, trace_request_ctx):
        return SimpleNamespace(trace_request_ctx=trace_request_ctx, context=self.context)

    def add_listener(self, listener):
        return self.eventer.add_listener(listener)

    async def send_event(self, event, **options):
        await self.eventer.send_event(event, session=self, **options)

    async def _request_start(self, session, trace_config_ctx, params):
        if self.context.statsd:
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
        if self.context.statsd:
            duration = int((perf_counter() - trace_config_ctx.start) * 1000)
            self.context.statsd.timing(trace_config_ctx.label, value=duration)
            self.context.statsd.increment(
                trace_config_ctx.label + "." + str(params.response.status)
            )
        await self.send_event(
            "response_received",
            response=params.response,
            request=params.response.request,
        )


class LoggedClientRequest(ClientRequest):
    """Printable Request."""

    tracer: SessionTracer
    verbose: int = 0
    response_class = LoggedClientResponse

    async def send(self, *args, **kw):
        if self.tracer:
            await self.tracer.send_event("sending_request", request=self)
        response = await super().send(*args, **kw)
        response.request = self  # type: ignore
        return response


def get_session(loop, console, verbose=0, statsd=None, kind="http", **kw):
    trace_config = SessionTracer(loop, console, verbose, statsd)

    if kind != "http":
        return create_session(kind, loop, console, verbose, statsd, trace_config, **kw)

    connector = kw.pop("connector", None)
    if connector is None:
        connector = TCPConnector(limit=None, ttl_dns_cache=None)  # type: ignore

    request_class = LoggedClientRequest
    request_class.verbose = verbose
    request_class.response_class = LoggedClientResponse
    request_class.tracer = trace_config

    # patching the class to avoid aiohttp warning
    def _print(self, data):
        if self.console is None:
            print(data)
        else:
            self.console.print(data)

    ClientSession.print = _print  # type: ignore

    session = ClientSession(
        request_class=request_class,
        response_class=LoggedClientResponse,
        connector=connector,
        trace_configs=[trace_config],
        **kw,
    )
    session.console = console

    return session


def get_eventer(session):
    for trace in session._trace_configs:
        if isinstance(trace, SessionTracer):
            return trace
    return None


def get_context(session):
    for trace in session._trace_configs:
        if isinstance(trace, SessionTracer):
            return trace.context
    return None
