import signal
import asyncio
import os
import multiprocess

from molotov.api import get_fixture
from molotov.listeners import EventSender
from molotov.stats import get_statsd_client
from molotov.sharedcounter import SharedCounters
from molotov.util import (
    cancellable_sleep,
    stop,
    is_stopped,
    set_timer,
    event_loop,
    SharedTasks,
)
from molotov.worker import Worker


class Runner(object):
    """Manages processes & workers and grabs results."""

    def __init__(self, args, loop=None):
        self.args = args
        self.console = self.args.shared_console
        if loop is None:
            loop = event_loop()
        self.loop = loop
        # the stastd client gets initialized after we fork
        # processes in case -p was used
        self.statsd = None
        self._tasks = SharedTasks()
        self._procs = []
        self._results = SharedCounters(
            "WORKER",
            "REACHED",
            "RATIO",
            "OK",
            "FAILED",
            "MINUTE_OK",
            "MINUTE_FAILED",
            "MAX_WORKERS",
            "SETUP_FAILED",
            "SESSION_SETUP_FAILED",
            "PROCESS",
        )
        self.eventer = EventSender(self.console)

    def _set_statsd(self):
        if self.args.statsd:
            self.statsd = get_statsd_client(self.args.statsd_address)
        else:
            self.statsd = None

    def run_coro(self, coro):
        if not self.loop.is_running():
            raise Exception("Loop is not running")
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def gather(self, *futures):
        return asyncio.gather(*futures, return_exceptions=True)

    def ensure_future(self, coro):
        return asyncio.ensure_future(coro, loop=self.loop)

    def __call__(self):
        global_setup = get_fixture("global_setup")
        if global_setup is not None:
            try:
                global_setup(self.args)
            except Exception as e:
                self.console.print("The global_setup() fixture failed")
                self.console.print_error(e)
                raise

        if not self.args.quiet:
            fut = self._display_results(self.args.console_update)
            update = self.ensure_future(fut)
            self._tasks.append(update)

        self._tasks.append(self.ensure_future(self._send_workers_event(1)))
        try:
            return self._launch_processes()
        finally:
            global_teardown = get_fixture("global_teardown")
            if global_teardown is not None:
                try:
                    global_teardown()
                except Exception as e:
                    # we can't stop the teardown process and the ui is down
                    print(e)

            self._shutdown(None, None)

    def _launch_processes(self):
        args = self.args
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
        args.original_pid = os.getpid()

        if args.processes > 1:
            if not args.quiet:
                self.console.print("Forking %d processes" % args.processes)
            jobs = []
            for i in range(args.processes):
                p = multiprocess.Process(target=self._process)
                jobs.append(p)
                p.start()
                self._results["PROCESS"] += 1

            for job in jobs:
                self._procs.append(job)

            async def run(quiet, console):
                while len(self._procs) > 0:
                    for job in jobs:
                        if job.exitcode is not None and job in self._procs:
                            self._procs.remove(job)
                            self._results["PROCESS"] -= 1
                    await cancellable_sleep(args.console_update)
                await self.eventer.stop()

            self.loop.run_until_complete(run(args.quiet, self.console))
        else:
            self._process()

        return self._results

    def _shutdown(self, signal, frame):
        stop()
        self._tasks.cancel_all()
        # send sigterms
        for proc in self._procs:
            proc.terminate()

    def _runner(self):
        args = self.args

        def _prepare():
            tasks = []
            delay = 0
            if args.ramp_up > 0.0:
                step = args.ramp_up / args.workers
            else:
                step = 0.0
            for i in range(self.args.workers):
                worker = Worker(
                    i,
                    self._results,
                    self.console,
                    self.args,
                    self.statsd,
                    delay,
                    self.loop,
                )
                f = self.ensure_future(worker.run())
                tasks.append(f)
                delay += step
            return tasks

        if self.args.quiet:
            return _prepare()
        else:
            msg = "Preparing {} worker{}"
            msg = msg.format(args.workers, "s" if args.workers > 1 else "")
            return self.console.print_block(msg, _prepare)

    def _process(self):
        set_timer()

        # coroutine that will kill everything when duration is up
        if self.args.duration and self.args.force_shutdown:

            async def _duration_killer():
                cancelled = object()
                res = await cancellable_sleep(self.args.duration, result=cancelled)
                if res is cancelled or (res and not res.canceled()):
                    self._shutdown(None, None)
                    await asyncio.sleep(0)

            _duration_killer = self.ensure_future(_duration_killer())
        else:
            _duration_killer = None

        if self.args.processes > 1:
            signal.signal(signal.SIGINT, self._shutdown)
            signal.signal(signal.SIGTERM, self._shutdown)
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        if self.args.debug:
            self.console.print("**** RUNNING IN DEBUG MODE == SLOW ****")
            self.loop.set_debug(True)

        self._set_statsd()

        if self.args.original_pid == os.getpid():
            self._tasks.append(self.ensure_future(self._send_workers_event(1)))

        workers = self.gather(*self._runner())

        def _stop(cb):
            if _duration_killer is not None:
                if not _duration_killer.done():
                    _duration_killer.cancel()
            stop()

        workers.add_done_callback(_stop)
        self._tasks.append(workers)

        try:
            self.loop.run_until_complete(self.gather(*self._tasks))
        finally:
            if self.statsd is not None and not self.statsd.disconnected:
                self.loop.run_until_complete(self.ensure_future(self.statsd.close()))
            self._tasks.cancel_all()
            self.loop.close()

    async def _display_results(self, update_interval):
        if self.args.original_pid != os.getpid():
            raise IOError("Wrong process")

        await self.console.start()

        while not is_stopped():
            self.console.print_results(self._results.to_dict())
            await cancellable_sleep(update_interval)

        await self.console.stop()

    async def _send_workers_event(self, update_interval):
        while not self.eventer.stopped() and not is_stopped():
            workers = self._results["WORKER"].value
            await self.eventer.send_event("current_workers", workers=workers)
            await cancellable_sleep(update_interval)
