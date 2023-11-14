from urllib.parse import urlparse

from aiodogstatsd import Client


def get_statsd_client(address="udp://127.0.0.1:8125", **kw):
    res = urlparse(address)
    if res.hostname is None:
        hostname = "127.0.0.1"
    else:
        hostname = res.hostname
    if res.port is None:
        port = 8125
    else:
        port = res.port
    return Client(host=hostname, port=port, **kw)
