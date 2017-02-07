import asyncio


# taken from aiostatsd.tests.test_client
class ServerProto:
    def __init__(self, received_queue):
        self.received_queue = received_queue
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.received_queue.put_nowait(data)

    def disconnect(self):
        self.transport.close()

    def error_received(self, exc):
        raise Exception(exc)

    def connection_lost(self, exc):
        print(exc)


class UDPServer(object):
    def __init__(self, host, port, loop=None):
        self.host = host
        self.port = port
        if loop is None:
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        self._stop = asyncio.Future(loop=self.loop)
        self._done = asyncio.Future(loop=self.loop)
        self.incoming = asyncio.Queue(loop=self.loop)

    async def run(self):
        ctx = {}

        def make_proto():
            proto = ServerProto(self.incoming)
            ctx['proto'] = proto
            return proto

        conn = self.loop.create_datagram_endpoint(
            make_proto, local_addr=(self.host, self.port)
        )

        async def listen_for_stop():
            await self._stop
            ctx['proto'].disconnect()

        await asyncio.gather(conn, listen_for_stop(), loop=self.loop)
        self._done.set_result(True)

    def flush(self):
        out = []
        while not self.incoming.empty():
            out.append(self.incoming.get_nowait())
        return out

    async def stop(self):
        self._stop.set_result(True)
        await self._done
