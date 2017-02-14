import socket
from urllib.parse import urlparse
import asyncio
from aiohttp.client import ClientSession, ClientRequest
from aiohttp import TCPConnector
from molotov.util import resolve


_HOST = socket.gethostname()
_UNREADABLE = "***WARNING: Molotov can't display this body***"
_BINARY = "**** Binary content ****"
_COMPRESSED = ('gzip', 'compress', 'deflate', 'identity', 'br')


class LoggedClientRequest(ClientRequest):
    session = None

    def send(self, writer, reader):
        if self.session and self.verbose:
            info = self.session.print_request(self)
            asyncio.ensure_future(info)
        return super(LoggedClientRequest, self).send(writer, reader)


class LoggedClientSession(ClientSession):

    def __init__(self, loop, stream, verbose=False, statsd=None, **kw):
        connector = kw.pop('connector', None)
        if connector is None:
            connector = TCPConnector(loop=loop, limit=None)
        super(LoggedClientSession,
              self).__init__(loop=loop, request_class=LoggedClientRequest,
                             connector=connector,  **kw)
        self.stream = stream
        self.request_class = LoggedClientRequest
        self.request_class.verbose = verbose
        self.verbose = verbose
        self.request_class.session = self
        self.statsd = statsd

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

        await self.print_response(resp)
        return resp

    async def print_request(self, req):
        if not self.verbose:
            return

        await self.stream.put('>' * 45)
        raw = '\n' + req.method + ' ' + str(req.url)
        if len(req.headers) > 0:
            headers = '\n'.join('%s: %s' % (k, v) for k, v in
                                req.headers.items())
            raw += '\n' + headers

        if req.headers.get('Content-Encoding') in _COMPRESSED:
            raw += '\n\n' + _BINARY + '\n'
        elif req.body:
            if isinstance(req.body, bytes):
                try:
                    body = str(req.body, 'utf8')
                except UnicodeDecodeError:
                    body = _UNREADABLE
            else:
                body = req.body

            raw += '\n\n' + body + '\n'
        await self.stream.put(raw)

    async def print_response(self, resp):
        if not self.verbose:
            return
        await self.stream.put('\n' + '=' * 45 + '\n')
        raw = 'HTTP/1.1 %d %s\n' % (resp.status, resp.reason)
        items = resp.headers.items()
        headers = '\n'.join('{}: {}'.format(k, v) for k, v in items)
        raw += headers
        if resp.headers.get('Content-Encoding') in _COMPRESSED:
            raw += '\n\n' + _BINARY
        elif resp.content:
            content = await resp.content.read()
            # put back the data in the content
            resp.content.unread_data(content)
            try:
                raw += '\n\n' + content.decode()
            except UnicodeDecodeError:
                raw += '\n\n' + _UNREADABLE

        await self.stream.put(raw)
        await self.stream.put('\n' + '<' * 45 + '\n')
