import functools
import random
import time
import sys
import traceback
from concurrent.futures import (ThreadPoolExecutor, as_completed,
                                ProcessPoolExecutor)

import requests as _requests
import statsd as _statsd


class Session(_requests.Session):

    def __init__(self, verbose=False, stream=sys.stdout, statsd=None):
        super(Session, self).__init__()
        self.verbose = verbose
        self._stream = stream
        if statsd is not None:
            self._stats = _statsd.StatsClient(*statsd)
        else:
            self._stats = None

    def request(self, method, url, **kw):
        reqkws = {}
        for field in ('headers', 'files', 'data', 'json', 'params', 'auth',
                      'cookies', 'hooks'):
            if field in kw:
                reqkws[field] = kw.pop(field)

        req = _requests.Request(method, url, **reqkws).prepare()

        if self.verbose:
            self.print_request(req, self._stream)
            self._stream.write('\n>>>\n')

        resp = self.send(req, **kw)
        if self.verbose:
            self.print_response(resp, self._stream)
            self._stream.write('\n<<<\n')

        if self._stats is not None:
            stats_key = 'molotov.%s.%s' % (method, url)
            self._stats.timing(stats_key, resp.elapsed.total_seconds())
            self._stats.incr('motolov.request')

        return resp

    def print_request(self, req, stream=sys.stdout):
        raw = '\n' + req.method + ' ' + req.url
        if len(req.headers) > 0:
            headers = '\n'.join('%s: %s' % (k, v) for k, v in
                                req.headers.items())
            raw += '\n' + headers
        if req.body:
            raw += '\n\n' + str(req.body, 'utf8') + '\n'
        stream.write(raw)

    def print_response(self, resp, stream=sys.stdout):
        raw = 'HTTP/1.1 %s %s\n' % (resp.status_code, resp.reason)
        items = resp.headers.items()
        headers = '\n'.join('{}: {}'.format(k, v) for k, v in items)
        raw += headers

        if resp.content:
            raw += '\n\n' + resp.content.decode()
        stream.write(raw)


_SCENARIO = []
_STOP = False


def get_scenarios():
    return _SCENARIO


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


def worker(session, args):
    quiet = args.quiet
    duration = args.duration
    verbose = args.verbose

    if verbose:
        if args.processes:
            sys.stdout.write('[p]')
        else:
            sys.stdout.write('[th]')
        sys.stdout.flush()

    count = 1
    ok = failed = 0
    start = _now()

    while _now() - start < duration and not _STOP:
        func, args_, kw = _pick_scenario()
        if session._stats is not None:
            kw['statsd'] = session._stats
        try:
            func(session, *args_, **kw)
            if not quiet:
                sys.stdout.write('.')
            ok += 1
        except Exception as exc:
            if verbose:
                print(repr(exc))
                traceback.print_tb(sys.exc_info()[2])
            elif not quiet:
                sys.stdout.write('-')
            failed += 1
            if args.exception:
                if not verbose:
                    print(repr(exc))
                    traceback.print_tb(sys.exc_info()[2])
                break

        if not quiet:
            sys.stdout.flush()
        count += 1

    # worker is done
    if verbose:
        if args.processes:
            sys.stdout.write('[-p]')
        else:
            sys.stdout.write('[-th]')
        sys.stdout.flush()

    return ok, failed


def runner(args):

    if args.statsd:
        stats = args.statsd_host, args.statsd_port
    else:
        stats = None

    session = Session(verbose=args.verbose, statsd=stats)

    global _STOP
    if args.processes:
        executor = ProcessPoolExecutor(max_workers=args.users)
    else:
        executor = ThreadPoolExecutor(max_workers=args.users)

    future_to_resp = []

    for i in range(args.users):
        future = executor.submit(worker, session, args)
        future_to_resp.append(future)

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
