from aiomeasures import StatsD


def get_statsd_client(address="udp://127.0.0.1:8125", **kw):
    return StatsD(address, **kw)
