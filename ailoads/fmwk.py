import socket
from requests.packages.urllib3.util import connection as urllib3_conn
import functools

_GLOBAL_DEFAULT_TIMEOUT = object()
_cached = {}


def create_connection(address, timeout=_GLOBAL_DEFAULT_TIMEOUT,
                      source_address=None, socket_options=None):
    host, port = address
    err = None
    if address in _cached:
        addrinfo = [_cached[address]]
    else:
        addrinfo = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)

    for res in addrinfo:
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket.socket(af, socktype, proto)
            if socket_options:
                urllib3_conn._set_socket_options(sock, socket_options)

            if timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sa)
            # success, let's use this next time
            _cached[address] = res
            return sock
        except socket.error as _:
            err = _
            if sock is not None:
                sock.close()

    if err is not None:
        raise err
    else:
        raise socket.error("getaddrinfo returns an empty list")


socket.create_connection = create_connection
urllib3_conn.create_connection = create_connection

import asyncio
import requests
import functools
import random
import time
import sys
import statsd

from concurrent.futures import (ThreadPoolExecutor, as_completed,
                                ProcessPoolExecutor)

import requests as _requests


_statsd = statsd.StatsClient('localhost', 8125)

class Session(_requests.Session):
    def request(self, method, url, **kw):
        resp = _requests.Session.request(self, method, url, **kw)
        stats_key = 'loads.%s.%s' % (method, url)
        _statsd.timing(stats_key, resp.elapsed.total_seconds())
        _statsd.incr('loads.request')
        return resp


requests = Session()


_SCENARIO = []


def scenario(weight):
    def _scenario(func, *args, **kw):
        _SCENARIO.append((weight, func, args, kw))
        @functools.wraps
        def __scenario():
            return func(*args, **kw)
        return __scenario
    return _scenario


@scenario(5)
def _scenario_one():
    """Calls Google.
    """
    return requests.get('http://localhost:8000')


@scenario(30)
def _scenario_two():
    """Calls Yahoo.
    """
    return requests.get('http://localhost:8000')


def _pick_scenario():
    total = sum(item[0] for item in _SCENARIO)
    selection = random.uniform(0, total)
    upto = 0
    for item in _SCENARIO:
        weight = item[0]
        if upto + item[0] > selection:
            func, args, kw = item[1:]
            return func, args, kw
        upto += weight
    raise Exception('What')


def _now():
    return int(time.time())


def worker(**options):
    print('worker started')
    duration = options.get('duration', 60)
    count = 1
    ok = failed = 0

    start = _now()

    while _now() - start < duration:
        func, args, kw = _pick_scenario()
        try:
            res = func(*args, **kw)
            sys.stdout.write('.')
            ok += 1
        except Exception as exc:
            sys.stdout.write('-')
            failed += 1
        sys.stdout.flush()
        count += 1

    # worker is done
    return ok, failed


def runner(users=1, duration=100):
    print('Creating pool')
    executor = ThreadPoolExecutor(max_workers=users)
    print('Pool ready, adding tasks')

    future_to_resp = []

    start = time.time()

    for i in range(users):
        future = executor.submit(worker, duration=duration)
        future_to_resp.append(future)

    print('Lets go')
    results = []

    for future in as_completed(future_to_resp):
        try:
            results.append(future.result())
        except Exception as exc:
            results.append(exc)

    return results
