import multiprocess
import asyncio
import signal
import functools
import os


def debug(data):
    with open("/tmp/yeah.txt", "a+") as f:
        f.write(data + "\n")


# taken from aiostatsd.tests.test_client
class ServerProto:
    def __init__(self, conn):
        self.conn = conn
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        debug(data.decode("utf8"))
        self.conn.send(data)

    def disconnect(self):
        if self.transport is None:
            return
        self.transport.close()

    def error_received(self, exc):
        raise Exception(exc)

    def connection_lost(self, exc):
        if exc is not None:
            print(exc)


class UDPServer(object):
    def __init__(self, host, port, conn):
        self.host = host
        self.port = port
        self.incoming = asyncio.Queue()
        self.conn = conn
        self.running = False

    def stop(self, *args, **kw):
        self.running = False

    async def run(self):
        ctx = {}

        def make_proto():
            proto = ServerProto(self.conn)
            ctx["proto"] = proto
            return proto

        debug("starting")
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            make_proto, local_addr=(self.host, self.port)
        )

        if self.port == 0:
            self.port = transport.get_extra_info("socket").getsockname()[1]
        self.conn.send(self.port)

        debug(f"waiting on port {self.port}")
        self.running = True
        try:
            while self.running:
                await asyncio.sleep(1.0)
        finally:
            debug("disco")
            ctx["proto"].disconnect()


def run_server():
    parent, child = multiprocess.Pipe()
    p = multiprocess.Process(target=functools.partial(_run, child))
    p.start()
    port = parent.recv()
    print(f"Running on port {port}")
    debug(f"Running on port {port}")
    return p, port, parent


def stop_server(p, conn):
    debug("Stopping server pipe")
    debug("killing process")
    os.kill(p.pid, signal.SIGINT)
    p.join(timeout=1.0)
    res = []
    for data in conn.recv():
        res.append(data)
    conn.close()
    return res


def _run(conn):
    server = UDPServer("localhost", 0, conn)
    signal.signal(signal.SIGINT, server.stop)
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        debug("killed")
    conn.send("STOPPED")
    conn.close()


if __name__ == "__main__":
    try:
        p, port, conn = run_server()
        while True:
            print(conn.recv())
    finally:
        print(stop_server(p, conn))
