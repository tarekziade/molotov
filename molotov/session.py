import asyncio
from aiohttp.client import ClientSession, ClientRequest
from aiohttp import TCPConnector

from molotov.util import resolve


class LoggedClientRequest(ClientRequest):
    session = None

    def send(self, writer, reader):
        if self.session and self.verbose:
            info = self.session.print_request(self)
            asyncio.ensure_future(info)
        return super(LoggedClientRequest, self).send(writer, reader)


class LoggedClientSession(ClientSession):

    def __init__(self, loop, stream, verbose=False, **kw):
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

    def _dns_lookup(self, url):
        return resolve(url)[0]

    async def _request(self, *args, **kw):
        args = list(args)
        args[1] = self._dns_lookup(args[1])
        args = tuple(args)
        resp = await super(LoggedClientSession, self)._request(*args, **kw)
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
        if req.body:
            if isinstance(req.body, bytes):
                body = str(req.body, 'utf8')
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
        if resp.content:
            content = await resp.content.read()
            try:
                raw += '\n\n' + content.decode()
            except UnicodeDecodeError:
                raw += "\n\n***WARNING: Molotov can't display this body***"

        await self.stream.put(raw)
        await self.stream.put('\n' + '<' * 45 + '\n')
