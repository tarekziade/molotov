import asyncio
import functools
import random
import time
import sys
import traceback
from functools import partial
from concurrent.futures import ThreadPoolExecutor

import requests as _requests
import statsd as _statsd


class Session(_requests.Session):

    def __init__(self, verbose=False, stream=sys.stdout, statsd=None,
                 executor=None, loop=None, timeout=5.):
        super(Session, self).__init__()
        self.loop = loop
        self.verbose = verbose
        self._stream = stream
        # XXX maybe we could use aiostatsd
        if statsd is not None:
            self._stats = _statsd.StatsClient(*statsd)
        else:
            self._stats = None
        self.executor = executor
        self.timeout = timeout

    async def statsd_incr(self, counter):
        if self._stats is None:
            return
        func = partial(self._stats.incr, counter)
        future = self.loop.run_in_executor(self.executor, func)
        result = await asyncio.wait_for(future, self.timeout, loop=self.loop)
        return result

    async def statsd_timing(self, name, value):
        if self._stats is None:
            return
        func = partial(self._stats.timing, name, value)
        future = self.loop.run_in_executor(self.executor, func)
        result = await asyncio.wait_for(future, self.timeout, loop=self.loop)
        return result

    async def request(self, method, url, **kw):
        func = partial(self._async_request, method, url, **kw)
        future = self.loop.run_in_executor(self.executor, func)
        result = await asyncio.wait_for(future, self.timeout, loop=self.loop)
        return result

    def _async_request(self, method, url, **kw):
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
            if isinstance(req.body, bytes):
                body = str(req.body, 'utf8')
            else:
                body = req.body

            raw += '\n\n' + body + '\n'
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


async def worker(session, results, args):
    quiet = args.quiet
    duration = args.duration
    verbose = args.verbose

    if verbose:
        sys.stdout.write('[th]')
        sys.stdout.flush()

    count = 1
    start = _now()

    while _now() - start < duration and not _STOP:
        func, args_, kw = _pick_scenario()
        try:
            await func(session, *args_, **kw)
            if not quiet:
                sys.stdout.write('.')
            results['OK'] += 1
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if verbose:
                print(repr(exc))
                traceback.print_tb(sys.exc_info()[2])
            elif not quiet:
                sys.stdout.write('-')

            results['FAILED'] += 1

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
        sys.stdout.write('[-th]')
        sys.stdout.flush()


def _runner(loop, executor, args, results):
    if args.statsd:
        stats = args.statsd_host, args.statsd_port
    else:
        stats = None

    session = Session(verbose=args.verbose, statsd=stats, executor=executor,
                      loop=loop)
    tasks = []

    for i in range(args.users):
        future = asyncio.ensure_future(worker(session, results, args))
        tasks.append(future)

    return asyncio.gather(*tasks, loop=loop, return_exceptions=True)


def runner(args):
    global _STOP
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=args.users)
    results = {'OK': 0, 'FAILED': 0}
    tasks = _runner(loop, executor, args, results)
    try:
        loop.run_until_complete(tasks)
    except KeyboardInterrupt:
        _STOP = True
        tasks.cancel()
        loop.run_forever()
        executor.shutdown()
    finally:
        loop.close()

    return results
