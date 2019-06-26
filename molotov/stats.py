from urllib.parse import urlparse
from aiodogstatsd import Client


def get_statsd_client(address="udp://127.0.0.1:8125", **kw):
    res = urlparse(address)
    return Client(host=res.hostname, port=res.port, **kw)
