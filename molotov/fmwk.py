from functools import partial
import signal
import multiprocessing
import asyncio
import time
import sys
import os

from molotov.util import log, stream_log
from molotov.session import LoggedClientSession as Session
from molotov.result import LiveResults, ClosedError
from molotov.api import get_fixture, pick_scenario, get_scenario
from molotov.stats import get_statsd_client


_REACHED_TOLERANCE = _STOP = False
_STARTED_AT = _TOLERANCE = None
_REFRESH = .3
_HOWLONG = 0
_SIZING_RES = {'workers': 0}


def get_sizing_results():
    if _REACHED_TOLERANCE:
        return _SIZING_RES
    return None


def _now():
    return int(time.time())


_results = LiveResults()


def get_live_results():
    return _results


def res2key(res):
    if res == '.':
        return 'OK'
    elif res == '-':
        return 'FAILED'
    raise NotImplementedError(res)


async def consume(queue, numworkers, verbose=0):
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
            results = get_live_results()
            try:
                if item in ['.', '-']:
                    results.incr(res2key(item))
                else:
                    if verbose > 0:
                        print(item)
            except ClosedError:
                break
        else:
            if verbose > 0:
                import traceback
                traceback.print_tb(item)


async def step(worker_id, step_id, session, quiet, verbose, stream,
               scenario=None):
    """ single scenario call.

    When it returns 1, it works. -1 the script failed,
    0 the test is stopping or needs to stop.
    """
    if scenario is None:
        scenario = pick_scenario(worker_id, step_id)
    try:
        await scenario['func'](session, *scenario['args'], **scenario['kw'])
        await stream.put('.')
        if scenario['delay'] > 0.:
            await asyncio.sleep(scenario['delay'])
        return 1
    except asyncio.CancelledError:
        return 0
    except Exception as exc:
        await stream.put('-')
        if verbose > 0:
            await stream.put(repr(exc))
            await stream.put(sys.exc_info()[2])

    return -1


def _reached_tolerance(results, minute_res, current_time, args):
    if not args.sizing:
        return False

    global _TOLERANCE, _REACHED_TOLERANCE

    if _REACHED_TOLERANCE:
        return True

    if current_time - _TOLERANCE > 60:
        # we need to reset the tolerance counters
        _TOLERANCE = current_time
        minute_res['OK'] = 0
        minute_res['FAILED'] = 0
        return False

    OK = minute_res['OK']
    FAILED = minute_res['FAILED']

    if OK + FAILED < 100:
        # we don't have enough samples
        return False

    current_ratio = float(FAILED) / float(OK) * 100.
    reached = current_ratio > args.sizing_tolerance
    if reached:
        _REACHED_TOLERANCE = True
        _SIZING_RES['ratio'] = current_ratio
        _SIZING_RES['OK'] = results['OK']
        _SIZING_RES['FAILED'] = results['FAILED']
        _SIZING_RES['MINUTE_OK'] = minute_res['OK']
        _SIZING_RES['MINUTE_FAILED'] = minute_res['FAILED']

    return reached


async def worker(num, loop, results, minute_res, args, stream, statsd, delay):
    global _STOP
    if delay > 0.:
        await asyncio.sleep(delay)
    if args.sizing:
        _SIZING_RES['workers'] += 1
    quiet = args.quiet
    duration = args.duration
    verbose = args.verbose
    exception = args.exception
    if args.single_mode:
        single = get_scenario(args.single_mode)
    else:
        single = None
    count = 1
    start = _now()
    howlong = 0
    setup = get_fixture('setup')
    if setup is not None:
        try:
            options = await setup(num, args)
        except Exception as e:
            log(e)
            await stream.put('WORKER_STOPPED')
            return
        if options is None:
            options = {}
        elif not isinstance(options, dict):
            log('The setup function needs to return a dict')
            await stream.put('WORKER_STOPPED')
            return
    else:
        options = {}

    ssetup = get_fixture('setup_session')
    steardown = get_fixture('teardown_session')

    async with Session(loop, stream, verbose, statsd, **options) as session:
        session.args = args
        session.worker_id = num

        if ssetup is not None:
            await ssetup(num, session)

        while howlong < duration and not _STOP and not _REACHED_TOLERANCE:
            if args.max_runs and count > args.max_runs:
                break
            current_time = _now()
            howlong = current_time - start
            session.step = count
            result = await step(num, count, session, quiet, verbose,
                                stream, single)
            if result == 1:
                results['OK'] += 1
                minute_res['OK'] += 1
            elif result == -1:
                results['FAILED'] += 1
                minute_res['FAILED'] += 1
                if exception:
                    await stream.put('WORKER_STOPPED')
                    _STOP = True
            elif result == 0:
                break

            if _reached_tolerance(results, minute_res, current_time, args):
                await stream.put('WORKER_STOPPED')
                _STOP = True
                os.kill(os.getpid(), signal.SIGINT)

            count += 1
            if args.delay > 0.:
                await asyncio.sleep(args.delay)
            else:
                # forces a context switch
                await asyncio.sleep(0)

        if steardown is not None:
            try:
                await steardown(num, session)
            except Exception as e:
                # we can't stop the teardown process
                log(e)

    if not _STOP:
        await stream.put('WORKER_STOPPED')


def _worker_done(num, future):
    teardown = get_fixture('teardown')
    if teardown is not None:
        try:
            teardown(num)
        except Exception as e:
            # we can't stop the teardown process
            log(e)


def _runner(loop, args, results, minute_res, stream, statsd):
    def _prepare():
        tasks = []
        delay = 0
        if args.ramp_up > 0.:
            step = args.ramp_up / args.workers
        else:
            step = 0.
        for i in range(args.workers):
            f = worker(i, loop, results, minute_res, args, stream, statsd,
                       delay)
            future = asyncio.ensure_future(f)
            future.add_done_callback(partial(_worker_done, i))
            tasks.append(future)
            delay += step

        return tasks
    if args.quiet:
        return _prepare()
    else:
        msg = 'Preparing {} worker{}'
        with stream_log(msg.format(args.workers,
                                   's' if args.workers > 1 else '')):
            return _prepare()


def _process(args):
    global _STOP, _STARTED_AT, _TOLERANCE
    _STARTED_AT = _TOLERANCE = _now()

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
    minute_res = {'OK': 0, 'FAILED': 0}
    stream = asyncio.Queue(loop=loop)

    co_tasks = []

    if args.statsd:
        statsd = get_statsd_client(args.statsd_address, loop=loop)
    else:
        statsd = None

    consumer = asyncio.ensure_future(consume(stream, args.workers,
                                             args.verbose))
    co_tasks.append(consumer)
    _TASKS.extend(co_tasks)

    co_tasks = asyncio.gather(*co_tasks, loop=loop, return_exceptions=True)

    workers = _runner(loop, args, results, minute_res, stream, statsd)
    run_task = asyncio.gather(*workers, loop=loop, return_exceptions=True)

    _TASKS.extend(workers)

    try:
        loop.run_until_complete(run_task)
    except asyncio.CancelledError:
        _STOP = True
        co_tasks.cancel()
        loop.run_until_complete(co_tasks)
        run_task.cancel()
        loop.run_until_complete(run_task)
    finally:
        if statsd is not None:
            statsd.close()
        for task in _TASKS:
            del task
        loop.close()

    return results


_PROCESSES = []
_TASKS = []


def _shutdown(signal, frame):
    global _STOP
    _STOP = True
    get_live_results().close()

    for task in _TASKS:
        task.cancel()

    # send sigterms
    for proc in _PROCESSES:
        proc.terminate()


def _launch_processes(args):
    results = {'FAILED': 0, 'OK': 0}
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if args.processes > 1:
        if not args.quiet:
            log('Forking %d processes' % args.processes, pid=False)
        result_queue = multiprocessing.Queue()
        loop = asyncio.get_event_loop()

        def _pprocess(result_queue):
            result_queue.put(_process(args))

        jobs = []
        for i in range(args.processes):
            p = multiprocessing.Process(target=_pprocess,
                                        args=(result_queue,))
            jobs.append(p)
            p.start()

        for job in jobs:
            _PROCESSES.append(job)

        async def run(loop, quiet):
            while len(_PROCESSES) > 0:
                if not quiet:
                    try:
                        print(get_live_results(), end='\r')
                    except ClosedError:
                        # finished
                        return
                for job in jobs:
                    if job.exitcode is not None and job in _PROCESSES:
                        _PROCESSES.remove(job)

                await asyncio.sleep(.2)

        loop.run_until_complete(asyncio.ensure_future(run(loop, args.quiet)))

        for job in jobs:
            proc_result = result_queue.get()
            results['FAILED'] += proc_result['FAILED']
            results['OK'] += proc_result['OK']
    else:
        loop = asyncio.get_event_loop()

        if not args.quiet and args.console and args.verbose > 0:
            def _display(loop):
                try:
                    print(get_live_results(), end='\r')
                except ClosedError:
                    return
                loop.call_later(_REFRESH, _display, loop)

            loop.call_soon(_display, loop)

        results = _process(args)

    return results


def runner(args):
    global_setup = get_fixture('global_setup')
    if global_setup is not None:
        try:
            global_setup(args)
        except Exception:
            log("The global_setup() fixture failed")
            raise

    try:
        return _launch_processes(args)
    finally:
        global_teardown = get_fixture('global_teardown')
        if global_teardown is not None:
            try:
                global_teardown()
            except Exception as e:
                # we can't stop the teardown process
                log(e)
