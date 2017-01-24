import signal
try:
    import redis
except ImportError:
    redis = None

import multiprocessing
import asyncio
import functools
import random
import time
import sys
import os
from io import StringIO

from molotov.util import log, stream_log, resolve
from aiohttp.client import ClientSession, ClientRequest

import urwid   # meh..


class LoggedClientRequest(ClientRequest):
    session = None

    def send(self, writer, reader):
        if self.session and self.verbose:
            info = self.session.print_request(self)
            asyncio.ensure_future(info)
        return super(LoggedClientRequest, self).send(writer, reader)


class LoggedClientSession(ClientSession):

    def __init__(self, loop, stream, verbose=False):
        super(LoggedClientSession,
              self).__init__(loop=loop, request_class=LoggedClientRequest)
        self.stream = stream
        self.request_class = LoggedClientRequest
        self.request_class.verbose = verbose
        self.verbose = verbose
        self.request_class.session = self

    def _dns_lookup(self, url):
        return resolve(url)[0]

    async def _request(self, *args, **kw):
        args = list(args)
        args[1] = self._dns_lookup(args[1])
        args = tuple(args)
        resp = await super(LoggedClientSession, self)._request(*args, **kw)
        await self.print_response(resp)
        return resp

    async def print_request(self, req):
        if not self.verbose:
            return
        await self.stream.put('>' * 45)
        raw = '\n' + req.method + ' ' + str(req.url)
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
        await self.stream.put(raw)

    async def print_response(self, resp):
        if not self.verbose:
            return
        await self.stream.put('\n' + '=' * 45 + '\n')
        raw = 'HTTP/1.1 %d %s\n' % (resp.status, resp.reason)
        items = resp.headers.items()
        headers = '\n'.join('{}: {}'.format(k, v) for k, v in items)
        raw += headers
        if resp.content:
            content = await resp.content.read()
            raw += '\n\n' + content.decode()
        await self.stream.put(raw)
        await self.stream.put('\n' + '<' * 45 + '\n')


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


class LiveResults:
    def __init__(self, pid=os.getpid()):
        self.pid = pid
        self.OK = 0
        self.FAILED = 0
        self.last_tb = StringIO()
        self.stream = StringIO()
        self.start = _now()
        if redis is not None:
            self.r = redis.StrictRedis(host='localhost', port=6379, db=0)
        else:
            self.r = None

    def get_successes(self):
        if self.pid == os.getpid() or self.r is None:
            return self.OK
        res = self.r.get('motolov:%d:OK' % self.pid)
        if res is None:
            return 0
        return int(res)

    def get_failures(self):
        if self.pid == os.getpid() or self.r is None:
            return self.FAILED
        res = self.r.get('motolov:%d:FAILED' % self.pid)
        if res is None:
            return 0
        return int(res)

    def incr_success(self):
        self.OK += 1
        self.r.incr('motolov:%d:OK' % os.getpid())

    def incr_failure(self):
        self.FAILED += 1
        self.r.incr('motolov:%d:FAILED' % os.getpid())

    def howlong(self):
        return _now() - self.start

    def __str__(self):
        # XXX display TB or Stream
        stream = self.stream.read()
        if stream != '':
            return stream

        last_tb = self.last_tb.read()
        if last_tb != '':
            return last_tb

        return 'SUCCESSES: %s | FAILURES: %s' % (self.get_successes(),
                                                 self.get_failures())


_GLOBAL = {}


def get_live_results(pid=os.getpid()):
    if _STOP:
        raise OSError('Stopped')
    if pid not in _GLOBAL:
        _GLOBAL[pid] = LiveResults(pid)
    return _GLOBAL[pid]


async def consume(queue, numworkers, console=False):
    worker_stopped = 0
    while True and worker_stopped < numworkers:
        try:
            item = await queue.get()
        except RuntimeError:
            break
        if item == 'WORKER_STOPPED':
            worker_stopped += 1
        elif item == 'STOP':
            break

        elif isinstance(item, str):
            if not console:
                try:
                    results = get_live_results()
                except OSError:
                    break
                if item == '.':
                    results.incr_success()
                elif item == '-':
                    results.incr_failure()
                else:
                    results.stream.write(item)
            else:
                sys.stdout.write(item)
        else:
            if not console:
                file = results.last_tb
            else:
                file = sys.stdout

            import traceback
            traceback.print_tb(item, file=file)

        if console:
            sys.stdout.flush()


def ui_updater(procid, *args):
    return get_live_results(procid)


async def step(session, quiet, verbose, exception, stream):
    global _STOP
    func, args_, kw = _pick_scenario()
    try:
        await func(session, *args_, **kw)
        if not quiet and not verbose:
            await stream.put('.')
        return 1
    except asyncio.CancelledError:
        return 0
    except Exception as exc:
        if _STOP:
            return 0
        if verbose:
            await stream.put(repr(exc))
            await stream.put(sys.exc_info()[2])
        elif not quiet and not verbose:
            await stream.put('-')
        if exception:
            _STOP = True
            await stream.put('STOP')
            return 0
    return -1


_HOWLONG = 0


async def worker(loop, results, args, stream):
    quiet = args.quiet
    duration = args.duration
    verbose = args.verbose
    exception = args.exception
    count = 1
    start = _now()
    howlong = 0

    async with LoggedClientSession(loop, stream, verbose) as session:
        while howlong < duration and not _STOP:
            howlong = _now() - start
            result = await step(session, quiet, verbose, exception, stream)
            if result == 1:
                results['OK'] += 1
            elif result == -1:
                results['FAILED'] += 1
            elif result == 0:
                break
            count += 1

    if not _STOP:
        await stream.put('WORKER_STOPPED')


def _runner(loop, args, results, stream):
    tasks = []
    with stream_log('Preparing %d workers' % args.workers):
        for i in range(args.workers):
            future = asyncio.ensure_future(worker(loop, results, args, stream))
            tasks.append(future)

    return tasks


def _process(args):
    global _STOP
    if args.processes > 1:
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    if args.debug:
        log('**** RUNNING IN DEBUG MODE == SLOW ****')
        loop.set_debug(True)

    results = {'OK': 0, 'FAILED': 0}
    stream = asyncio.Queue()
    consumer = asyncio.ensure_future(consume(stream, args.workers,
                                     args.console))
    tasks = _runner(loop, args, results, stream)
    tasks = asyncio.gather(*tasks, loop=loop, return_exceptions=True)

    _TASKS.append(tasks)
    _TASKS.append(consumer)
    try:
        loop.run_until_complete(tasks)
        loop.run_until_complete(consumer)
    except asyncio.CancelledError:
        _STOP = True
        consumer.cancel()
        tasks.cancel()
        loop.run_until_complete(tasks)
    finally:
        loop.close()
        _TASKS.remove(tasks)
        _TASKS.remove(consumer)

    return results


_PIDTOINT = {}
_INTTOPID = {}

_PROCESSES = []
_TASKS = []


def _shutdown(signal, frame):
    global _STOP
    _STOP = True

    for task in _TASKS:
        task.cancel()

    # send sigterms
    for proc in _PROCESSES:
        proc.terminate()


def _launch_processes(args, screen):
    results = {'FAILED': 0, 'OK': 0}
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if args.processes > 1:
        log('Forking %d processes' % args.processes, pid=False)
        result_queue = multiprocessing.Queue()
        ui = None

        def _pprocess(result_queue):
            result_queue.put(_process(args))

        jobs = []
        for i in range(args.processes):
            p = multiprocessing.Process(target=_pprocess,
                                        args=(result_queue,))
            jobs.append(p)
            p.start()
            _PIDTOINT[p.pid] = i
            _INTTOPID[i] = p.pid

        for job in jobs:
            _PROCESSES.append(job)

        if screen is not None and not args.console:
            if args.processes == 1:
                pids = [os.getpid()]
            else:
                pids = [job.pid for job in jobs]

            ui = screen(pids, ui_updater)

            def check_procs(*args):
                dead = [not p.is_alive() for p in _PROCESSES]
                if all(dead):
                    raise urwid.ExitMainLoop()

            ui.set_alarm_in(1, check_procs)
            ui.run()

        for job in jobs:
            job.join()
            _PROCESSES.remove(job)

        for job in jobs:
            proc_result = result_queue.get()
            results['FAILED'] += proc_result['FAILED']
            results['OK'] += proc_result['OK']
    else:
        if screen is not None and not args.console:
            loop = asyncio.get_event_loop()
            ui = screen([os.getpid()], ui_updater, loop)
            ui.start()

        else:
            ui = None

        results = _process(args)

        if ui is not None:
            ui.stop()

    return results


def runner(args, screen=None):
    global _STOP
    global _GLOBAL
    args.mainpid = os.getpid()
    results = _launch_processes(args, screen)
    return results
