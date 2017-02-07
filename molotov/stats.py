try:
    from aiostatsd.client import StatsdClient
except ImportError:
    StatsdClient = None


def get_statsd_client(server="127.0.0.1", port=8125, packet_size=512,
                      flush_interval=.01):
    if StatsdClient is None:
        raise ImportError("You need to install aiostatsd")
    client = StatsdClient(server, port, packet_size=packet_size,
                          flush_interval=flush_interval)
    return client
