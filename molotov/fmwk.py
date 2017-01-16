import functools
import random
import time
import sys
import traceback
from concurrent.futures import (ThreadPoolExecutor, as_completed,
                                ProcessPoolExecutor)

import requests as _requests
import statsd


_statsd = statsd.StatsClient('localhost', 8125)


class Session(_requests.Session):
    verbose = False
    _stream = sys.stdout

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

        stats_key = 'loads.%s.%s' % (method, url)
        _statsd.timing(stats_key, resp.elapsed.total_seconds())
        _statsd.incr('loads.request')
        return resp

    def post_json(self, url, data=None, json=None, **kwargs):
        if data is not None:
            data = json.dumps(data)
        if 'headers' in kwargs:
            headers = kwargs['headers']
        else:
            headers = {}
        headers['Content-Type'] = 'application/json'
        kwargs['headers'] = headers
        return self.post(url, data=None, json=None, **kwargs)

    def print_request(self, req, stream=sys.stdout):
        raw = '\n' + req.method + ' ' + req.url
        if len(req.headers) > 0:
            headers = '\n'.join('%s: %s' % (k, v) for k, v in
                                req.headers.items())
            raw += '\n' + headers
        if req.body:
            raw += '\n\n' + req.body + '\n'
        stream.write(raw)

    def print_response(self, resp, stream=sys.stdout):
        raw = 'HTTP/1.1 %s %s\n' % (resp.status_code, resp.reason)
        items = resp.headers.items()
        headers = '\n'.join('{}: {}'.format(k, v) for k, v in items)
        raw += headers

        if resp.content:
            raw += '\n\n' + resp.content.decode()
        stream.write(raw)


requests = Session()
_SCENARIO = []
_STOP = False


def get_scenarios():
    return _SCENARIO


def scenario(weight):
    def _scenario(func, *args, **kw):
        _SCENARIO.append((weight, func, args, kw))

        @functools.wraps(func)
        def __scenario():
            return func(requests, *args, **kw)
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


def worker(args):
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
        try:
            func(requests, *args_, **kw)
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
    global _STOP
    if args.processes:
        executor = ProcessPoolExecutor(max_workers=args.users)
    else:
        executor = ThreadPoolExecutor(max_workers=args.users)

    future_to_resp = []

    for i in range(args.users):
        future = executor.submit(worker, args)
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
