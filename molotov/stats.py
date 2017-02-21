

def get_statsd_client(server="127.0.0.1", port=8125, packet_size=512,
                      flush_interval=.01):
    from aiostatsd.client import StatsdClient
    client = StatsdClient(server, port, packet_size=packet_size,
                          flush_interval=flush_interval)
    return client
