from functools import partial
import signal
import multiprocessing
import asyncio
import time
import os

from molotov.session import LoggedClientSession as Session
from molotov.api import get_fixture, pick_scenario, get_scenario
from molotov.stats import get_statsd_client
from molotov.sharedcounter import SharedCounters


_STOP = False
_STARTED_AT = _TOLERANCE = None
_REFRESH = .3
_HOWLONG = 0
_RESULTS = SharedCounters('WORKER', 'REACHED', 'RATIO', 'OK', 'FAILED',
                          'MINUTE_OK', 'MINUTE_FAILED')


def display_results():
    ok, fail = _RESULTS['OK'].value, _RESULTS['FAILED'].value
    workers = _RESULTS['WORKER'].value
    return 'SUCCESSES: %s | FAILURES: %s | WORKERS: %s' % (ok, fail, workers)


def _now():
    return int(time.time())


async def step(worker_id, step_id, session, quiet, verbose, console,
               scenario=None):
    """ single scenario call.

    When it returns 1, it works. -1 the script failed,
    0 the test is stopping or needs to stop.
    """
    if scenario is None:
        scenario = pick_scenario(worker_id, step_id)
    try:
        await scenario['func'](session, *scenario['args'], **scenario['kw'])
        if scenario['delay'] > 0.:
            await asyncio.sleep(scenario['delay'])
        return 1
    except asyncio.CancelledError:
        return 0
    except Exception as exc:
        if verbose > 0:
            console.print_error(exc)

    return -1


def _reached_tolerance(current_time, args):
    if not args.sizing:
        return False

    global _TOLERANCE

    if _RESULTS['REACHED'] == 1:
        return True

    if current_time - _TOLERANCE > 60:
        # we need to reset the tolerance counters
        _TOLERANCE = current_time
        _RESULTS['MINUTE_OK'].value = 0
        _RESULTS['MINUTE_FAILED'].value = 0
        return False

    OK = _RESULTS['MINUTE_OK'].value
    FAILED = _RESULTS['MINUTE_FAILED'].value

    if OK + FAILED < 100:
        # we don't have enough samples
        return False

    current_ratio = float(FAILED) / float(OK) * 100.
    reached = current_ratio > args.sizing_tolerance
    if reached:
        _RESULTS['REACHED'] = 1
        _RESULTS['RATIO'] = int(current_ratio * 100)

    return reached


async def worker(num, loop, args, statsd, delay):
    if delay > 0.:
        await asyncio.sleep(delay)
    _RESULTS['WORKER'] += 1
    try:
        return await _worker(num, loop, args, statsd, delay)
    finally:
        _RESULTS['WORKER'] -= 1


async def _worker(num, loop, args, statsd, delay):
    global _STOP
    quiet = args.quiet
    duration = args.duration
    verbose = args.verbose
    exception = args.exception
    console = args.shared_console

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
            console.print_error(e)
            return
        if options is None:
            options = {}
        elif not isinstance(options, dict):
            console.print('The setup function needs to return a dict')
            return
    else:
        options = {}

    ssetup = get_fixture('setup_session')
    steardown = get_fixture('teardown_session')

    async with Session(loop, console, verbose, statsd, **options) as session:
        session.args = args
        session.worker_id = num

        if ssetup is not None:
            await ssetup(num, session)

        while (howlong < duration and not _STOP and
               not _RESULTS['REACHED'] == 1):
            if args.max_runs and count > args.max_runs:
                break
            current_time = _now()
            howlong = current_time - start
            session.step = count
            result = await step(num, count, session, quiet, verbose,
                                console, single)
            if result == 1:
                _RESULTS['OK'] += 1
                _RESULTS['MINUTE_OK'] += 1
            elif result == -1:
                _RESULTS['FAILED'] += 1
                _RESULTS['MINUTE_FAILED'] += 1
                if exception:
                    _STOP = True
            elif result == 0:
                break

            if _reached_tolerance(current_time, args):
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
                console.print_error(e)


def _worker_done(num, console, future):
    teardown = get_fixture('teardown')
    if teardown is not None:
        try:
            teardown(num)
        except Exception as e:
            # we can't stop the teardown process
            console.print_error(e)


def _runner(loop, args, statsd):
    def _prepare():
        tasks = []
        delay = 0
        if args.ramp_up > 0.:
            step = args.ramp_up / args.workers
        else:
            step = 0.
        for i in range(args.workers):
            f = worker(i, loop, args, statsd, delay)
            future = asyncio.ensure_future(f)
            future.add_done_callback(partial(_worker_done, i,
                                             args.shared_console))
            tasks.append(future)
            delay += step

        return tasks

    if args.quiet:
        return _prepare()
    else:
        msg = 'Preparing {} worker{}'
        msg = msg.format(args.workers, 's' if args.workers > 1 else '')
        return args.shared_console.print_block(msg, _prepare)


async def _results(console, update_interval):
    while not _STOP:
        console.print(display_results(), end='\r')
        await asyncio.sleep(update_interval)


def _process(args):
    global _STOP, _STARTED_AT, _TOLERANCE
    _STARTED_AT = _TOLERANCE = _now()
    console = args.shared_console

    if args.processes > 1:
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    if args.debug:
        console.print('**** RUNNING IN DEBUG MODE == SLOW ****')
        loop.set_debug(True)

    display = asyncio.ensure_future(console.display())
    co_tasks = [display]
    if args.original_pid == os.getpid():
        co_tasks.append(asyncio.ensure_future(_results(console,
                                              args.console_update)))

    if args.statsd:
        statsd = get_statsd_client(args.statsd_address, loop=loop)
    else:
        statsd = None

    _TASKS.extend(co_tasks)
    co_tasks = asyncio.gather(*co_tasks, loop=loop, return_exceptions=True)

    workers = _runner(loop, args, statsd)
    run_task = asyncio.gather(*workers, loop=loop, return_exceptions=True)
    _TASKS.extend(workers)

    try:
        loop.run_until_complete(run_task)
        _STOP = True
    except asyncio.CancelledError:
        _STOP = True
        co_tasks.cancel()
        loop.run_until_complete(co_tasks)
        run_task.cancel()
        loop.run_until_complete(run_task)
    finally:
        console.stop()
        loop.run_until_complete(co_tasks)
        if statsd is not None:
            statsd.close()
        for task in _TASKS:
            del task
        loop.close()


_PROCESSES = []
_TASKS = []


def _shutdown(signal, frame):
    global _STOP
    _STOP = True

    for task in _TASKS:
        try:
            task.cancel()
        except RuntimeError:
            pass

    # send sigterms
    for proc in _PROCESSES:
        proc.terminate()


def _launch_processes(args):
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    console = args.shared_console
    args.original_pid = os.getpid()

    if args.processes > 1:
        if not args.quiet:
            args.shared_console.print('Forking %d processes' % args.processes)
        loop = asyncio.get_event_loop()
        jobs = []
        for i in range(args.processes):
            p = multiprocessing.Process(target=_process, args=(args,))
            jobs.append(p)
            p.start()

        for job in jobs:
            _PROCESSES.append(job)

        async def run(quiet, console):
            while len(_PROCESSES) > 0:
                if not quiet:
                    console.print(display_results(), end='\r')
                for job in jobs:
                    if job.exitcode is not None and job in _PROCESSES:
                        _PROCESSES.remove(job)
                await asyncio.sleep(args.console_update)
            console.stop()

        tasks = [asyncio.ensure_future(console.display()),
                 asyncio.ensure_future(run(args.quiet, console))]
        loop.run_until_complete(asyncio.gather(*tasks))
    else:
        _process(args)

    return _RESULTS


def runner(args):
    global_setup = get_fixture('global_setup')
    if global_setup is not None:
        try:
            global_setup(args)
        except Exception as e:
            args.shared_console.print("The global_setup() fixture failed")
            args.shared_console.print_error(e)
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
                args.shared_console.print_error(e)
