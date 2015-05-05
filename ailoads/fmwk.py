import functools
import random
import time
import sys
import statsd
from concurrent.futures import ThreadPoolExecutor, as_completed

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
_STOP = False


def scenario(weight):
    def _scenario(func, *args, **kw):
        _SCENARIO.append((weight, func, args, kw))

        @functools.wraps(func)
        def __scenario():
            return func(*args, **kw)
        return __scenario

    return _scenario


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
    sys.stdout.write('*')
    sys.stdout.flush()
    duration = options.get('duration', 60)
    verbose = options.get('verbose', True)
    count = 1
    ok = failed = 0

    start = _now()

    while _now() - start < duration and not _STOP:
        func, args, kw = _pick_scenario()
        try:
            func(*args, **kw)
            sys.stdout.write('.')
            ok += 1
        except Exception as exc:
            if verbose:
                print(exc)
            else:
                sys.stdout.write('-')
            failed += 1
        sys.stdout.flush()
        count += 1

    # worker is done
    return ok, failed


def runner(users=1, duration=100):
    global _STOP
    print('Creating workers')
    executor = ThreadPoolExecutor(max_workers=users)
    future_to_resp = []

    for i in range(users):
        future = executor.submit(worker, duration=duration)
        future_to_resp.append(future)

    print('')
    print("Let's go")
    results = []

    def _grab_results():
        for future in as_completed(future_to_resp):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(exc)

    try:
        _grab_results()
    except KeyboardInterrupt:
        _STOP = True
        executor.shutdown()
        _grab_results()
        print('Bye')

    return results
