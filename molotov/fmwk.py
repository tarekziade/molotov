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
from molotov.ui import quit as quit_screen


_STOP = False
_REFRESH = .3


def _now():
    return int(time.time())


_results = LiveResults()


def get_live_results():
    return _results


async def consume(queue, numworkers, console=False, verbose=0):
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
                if item == '.':
                    results.incr_success()
                elif item == '-':
                    results.incr_failure()
                else:
                    if console and verbose > 0:
                        print(item)
            except ClosedError:
                break
        else:
            if console and verbose > 0:
                import traceback
                traceback.print_tb(item)


async def step(session, quiet, verbose, stream, scenario=None):
    """ single scenario call.

    When it returns 1, it works. -1 the script failed,
    0 the test is stopping or needs to stop.
    """
    if scenario:
        __, delay, func, args_, kw = scenario
    else:
        delay, func, args_, kw = pick_scenario()
    try:
        await func(session, *args_, **kw)
        await stream.put('.')
        if delay > 0.0:
            await asyncio.sleep(delay)
        return 1
    except asyncio.CancelledError:
        return 0
    except Exception as exc:
        await stream.put('-')
        if verbose > 0:
            await stream.put(repr(exc))
            await stream.put(sys.exc_info()[2])

    return -1


_HOWLONG = 0


async def worker(num, loop, results, args, stream, statsd, delay):
    global _STOP
    if delay > 0.:
        await asyncio.sleep(delay)
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

        while howlong < duration and not _STOP:
            if args.max_runs and count > args.max_runs:
                break
            howlong = _now() - start
            session.step = count
            result = await step(session, quiet, verbose, stream, single)
            if result == 1:
                results['OK'] += 1
            elif result == -1:
                results['FAILED'] += 1
                if exception:
                    await stream.put('WORKER_STOPPED')
                    _STOP = True
            elif result == 0:
                break
            count += 1
            if args.delay > 0.:
                await asyncio.sleep(args.delay)

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


def _runner(loop, args, results, stream, statsd):
    def _prepare():
        tasks = []
        delay = 0
        if args.ramp_up > 0.:
            step = args.ramp_up / args.workers
        else:
            step = 0.

        for i in range(args.workers):
            future = asyncio.ensure_future(worker(i, loop, results, args,
                                                  stream, statsd, delay))
            future.add_done_callback(partial(_worker_done, i))
            tasks.append(future)
            delay += step

        return tasks
    if args.quiet:
        return _prepare()
    else:
        with stream_log('Preparing %d workers' % args.workers):
            return _prepare()


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
    stream = asyncio.Queue(loop=loop)

    co_tasks = []

    if args.statsd:
        statsd = get_statsd_client(args.statsd_server, args.statsd_port)
        stastd_task = asyncio.ensure_future(statsd.run())
    else:
        statsd = stastd_task = None

    consumer = asyncio.ensure_future(consume(stream, args.workers,
                                     args.console, args.verbose))
    co_tasks.append(consumer)
    _TASKS.extend(co_tasks)

    co_tasks = asyncio.gather(*co_tasks, loop=loop, return_exceptions=True)

    workers = _runner(loop, args, results, stream, statsd)
    run_task = asyncio.gather(*workers, loop=loop, return_exceptions=True)

    _TASKS.extend(workers)
    _STATSD.append((statsd, stastd_task))

    try:
        loop.run_until_complete(run_task)
    except asyncio.CancelledError:
        _STOP = True
        co_tasks.cancel()
        loop.run_until_complete(co_tasks)
        run_task.cancel()
        loop.run_until_complete(run_task)
    finally:
        _stop_statsd()
        for task in _TASKS:
            del task
        loop.close()

    return results


_STATSD = []
_PROCESSES = []
_TASKS = []


def _stop_statsd():

    if _STATSD != []:
        loop = asyncio.get_event_loop()

        async def stop():
            statsd, stastd_task = _STATSD[0]
            try:
                await statsd.stop()
                await stastd_task
            except Exception:
                pass

        stop = asyncio.ensure_future(stop())
        loop.run_until_complete(stop)
        _STATSD[:] = []


def _shutdown(signal, frame):
    global _STOP
    _STOP = True
    get_live_results().close()

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
        if not args.quiet:
            log('Forking %d processes' % args.processes, pid=False)
        result_queue = multiprocessing.Queue()
        ui = None
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

        if screen is not None and not args.console:
            pids = [job.pid for job in jobs]
            ui = screen(pids, get_live_results)

            def check_procs(*args):
                dead = [not p.is_alive() for p in _PROCESSES]
                if all(dead):
                    quit_screen()

            ui.set_alarm_in(1, check_procs)
            ui.run()

        async def run(loop, quiet, console):
            while len(_PROCESSES) > 0:
                if not quiet and console:
                    try:
                        print(get_live_results(), end='\r')
                    except ClosedError:
                        # finished
                        return
                for job in jobs:
                    if job.exitcode is not None and job in _PROCESSES:
                        _PROCESSES.remove(job)

                await asyncio.sleep(.2)

        loop.run_until_complete(asyncio.ensure_future(run(loop, args.quiet,
                                                          args.console)))

        for job in jobs:
            proc_result = result_queue.get()
            results['FAILED'] += proc_result['FAILED']
            results['OK'] += proc_result['OK']
    else:
        loop = asyncio.get_event_loop()
        if screen is not None and not args.console:
            ui = screen([os.getpid()], get_live_results, loop)
            ui.start()
        else:
            ui = None

        if not args.quiet and args.console and args.verbose > 0:
            def _display(loop):
                try:
                    print(get_live_results(), end='\r')
                except ClosedError:
                    return
                loop.call_later(_REFRESH, _display, loop)

            loop.call_soon(_display, loop)

        results = _process(args)

        if ui is not None:
            ui.stop()

    return results


def runner(args, screen=None):
    global_setup = get_fixture('global_setup')
    if global_setup is not None:
        try:
            global_setup(args)
        except Exception:
            log("The global_setup() fixture failed")
            raise

    try:
        return _launch_processes(args, screen)
    finally:
        global_teardown = get_fixture('global_teardown')
        if global_teardown is not None:
            try:
                global_teardown()
            except Exception as e:
                # we can't stop the teardown process
                log(e)
