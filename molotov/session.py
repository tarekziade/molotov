import socket
from urllib.parse import urlparse
import asyncio
from aiohttp.client import ClientSession, ClientRequest, ClientResponse
from aiohttp import TCPConnector

from molotov.util import resolve
from molotov.listeners import StdoutListener, CustomListener
from molotov.api import get_fixture


_HOST = socket.gethostname()


class LoggedClientRequest(ClientRequest):
    """Printable Request.
    """
    session = None

    def send(self, *args, **kw):
        if self.session:
            event = self.session.send_event('sending_request', request=self)
            asyncio.ensure_future(event)
        response = super(LoggedClientRequest, self).send(*args, **kw)
        response.request = self
        return response


class LoggedClientResponse(ClientResponse):
    request = None


class LoggedClientSession(ClientSession):
    """Session with printable requests and responses.
    """
    def __init__(self, loop, console, verbose=0, statsd=None, **kw):
        connector = kw.pop('connector', None)
        if connector is None:
            connector = TCPConnector(loop=loop, limit=None)
        super(LoggedClientSession,
              self).__init__(loop=loop,
                             request_class=LoggedClientRequest,
                             response_class=LoggedClientResponse,
                             connector=connector,  **kw)
        self.console = console
        self.request_class = LoggedClientRequest
        self.request_class.verbose = verbose
        self.verbose = verbose
        self.request_class.session = self
        self.request_class.response_class = LoggedClientResponse
        self.statsd = statsd
        self.listeners = [StdoutListener(verbose=self.verbose,
                                         console=self.console)]
        listeners = get_fixture('events')
        if listeners is not None:
            for listener in listeners:
                self.add_listener(CustomListener(listener))

    def add_listener(self, listener):
        self.listeners.append(listener)

    async def send_event(self, event, **options):
        for listener in self.listeners:
            try:
                await listener(event, session=self, **options)
            except Exception as e:
                self.console.print_error(e)

    def _dns_lookup(self, url):
        return resolve(url)[0]

    async def _request(self, *args, **kw):
        args = list(args)
        args[1] = self._dns_lookup(args[1])
        args = tuple(args)
        req = super(LoggedClientSession, self)._request

        if self.statsd:
            prefix = 'molotov.%(hostname)s.%(method)s.%(host)s.%(path)s'
            meth, url = args[:2]
            url = urlparse(url)
            path = url.path != '' and url.path or '/'

            data = {'method': meth,
                    'hostname': _HOST,
                    'host': url.netloc.split(":")[0],
                    'path': path}

            label = prefix % data

            @self.statsd.timer(label)
            async def request():
                resp = await req(*args, **kw)
                self.statsd.incr(label + '.' + str(resp.status))
                return resp

            resp = await request()
        else:
            resp = await req(*args, **kw)

        await self.send_event('response_received', response=resp, request=resp.request)
        return resp
