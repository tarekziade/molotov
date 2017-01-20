import asyncio
import functools
import random
import time
import sys
import traceback

from aiohttp.client import ClientSession


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


async def consume(queue, numworkers):
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
            sys.stdout.write(item)
        else:
            traceback.print_tb(item, file=sys.stdout)
        sys.stdout.flush()


async def step(session, quiet, verbose, exception, stream):
    global _STOP
    func, args_, kw = _pick_scenario()
    try:
        await func(session, *args_, **kw)
        if not quiet:
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
        elif not quiet:
            await stream.put('-')
        if exception:
            _STOP = True
            await stream.put('STOP')
            return 0
    return -1


async def worker(results, args, stream):
    quiet = args.quiet
    duration = args.duration
    verbose = args.verbose
    exception = args.exception
    count = 1
    start = _now()

    async with ClientSession() as session:
        while _now() - start < duration and not _STOP:
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
    sys.stdout.write('Preparing %d workers...' % args.workers)
    sys.stdout.flush()
    for i in range(args.workers):
        future = asyncio.ensure_future(worker(results, args, stream))
        tasks.append(future)
    print('OK')
    return tasks


def runner(args):
    global _STOP
    results = {'OK': 0, 'FAILED': 0}
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    stream = asyncio.Queue()
    consumer = asyncio.ensure_future(consume(stream, args.workers))
    tasks = _runner(loop, args, results, stream)
    tasks = asyncio.gather(*tasks, loop=loop, return_exceptions=True)

    try:
        loop.run_until_complete(tasks)
        loop.run_until_complete(consumer)
    except (KeyboardInterrupt, asyncio.CancelledError):
        _STOP = True
        consumer.cancel()
        tasks.cancel()
        loop.run_until_complete(tasks)
    finally:
        loop.close()

    return results
