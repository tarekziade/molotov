import asyncio
import time
from molotov.session import LoggedClientSession as Session
from molotov.api import get_fixture, pick_scenario, get_scenario
from molotov.util import (cancellable_sleep, is_stopped, set_timer, get_timer,
                          stop)


def _now():
    return int(time.time())


class Worker(object):
    """"The Worker class creates a Session and runs scenario.
    """
    def __init__(self, wid, results, console, args, statsd=None,
                 delay=0, loop=None):
        self.wid = wid
        self.results = results
        self.console = console
        self.loop = loop or asyncio.get_event_loop()
        self.args = args
        self.statsd = statsd
        self.delay = delay

    async def run(self):
        if self.delay > 0.:
            await cancellable_sleep(self.delay)
        if is_stopped():
            return
        self.results['WORKER'] += 1
        try:
            res = await self._run()
        finally:
            await self.done()
            self.results['WORKER'] -= 1
        return res

    async def _run(self):
        duration = self.args.duration
        verbose = self.args.verbose
        exception = self.args.exception

        if self.args.single_mode:
            single = get_scenario(self.args.single_mode)
        else:
            single = None
        count = 1
        start = _now()
        howlong = 0
        setup = get_fixture('setup')
        if setup is not None:
            try:
                options = await setup(self.wid, self.args)
            except Exception as e:
                self.console.print_error(e)
                stop()
                return
            if options is None:
                options = {}
            elif not isinstance(options, dict):
                self.console.print('The setup function needs to return a dict')
                stop()
                return
        else:
            options = {}

        ssetup = get_fixture('setup_session')
        steardown = get_fixture('teardown_session')

        async with Session(self.loop, self.console, verbose, self.statsd,
                           **options) as session:
            session.args = self.args
            session.worker_id = self.wid

            if ssetup is not None:
                await ssetup(self.wid, session)

            while (howlong < duration and not is_stopped() and
                   not self.results['REACHED'] == 1):
                if self.args.max_runs and count > self.args.max_runs:
                    break
                current_time = _now()
                howlong = current_time - start
                session.step = count
                result = await self.step(count, session, scenario=single)
                if result == 1:
                    self.results['OK'] += 1
                    self.results['MINUTE_OK'] += 1
                elif result == -1:
                    self.results['FAILED'] += 1
                    self.results['MINUTE_FAILED'] += 1
                    if exception:
                        stop()

                if not is_stopped() and self._reached_tolerance(current_time):
                    stop()
                    cancellable_sleep.cancel_all()
                    break

                count += 1
                if self.args.delay > 0.:
                    await cancellable_sleep(self.args.delay)
                else:
                    # forces a context switch
                    await asyncio.sleep(0)

            if steardown is not None:
                try:
                    await steardown(self.wid, session)
                except Exception as e:
                    # we can't stop the teardown process
                    self.console.print_error(e)

    async def done(self):
        teardown = get_fixture('teardown')
        if teardown is not None:
            try:
                teardown(self.wid)
            except Exception as e:
                # we can't stop the teardown process
                self.console.print_error(e)

    def _reached_tolerance(self, current_time):
        if not self.args.sizing:
            return False

        if self.results['REACHED'] == 1 or is_stopped():
            return True

        if current_time - get_timer() > 60:
            # we need to reset the tolerance counters
            set_timer(current_time)
            self.results['MINUTE_OK'].value = 0
            self.results['MINUTE_FAILED'].value = 0
            return False

        OK = self.results['MINUTE_OK'].value
        FAILED = self.results['MINUTE_FAILED'].value

        if OK + FAILED < 100:
            # we don't have enough samples
            return False

        current_ratio = float(FAILED) / float(OK) * 100.
        reached = current_ratio > self.args.sizing_tolerance
        if reached:
            self.results['REACHED'] = 1
            self.results['RATIO'] = int(current_ratio * 100)

        return reached

    async def step(self, step_id, session, scenario=None):
        """ single scenario call.

        When it returns 1, it works. -1 the script failed,
        0 the test is stopping or needs to stop.
        """
        if scenario is None:
            scenario = pick_scenario(self.wid, step_id)
        try:
            await scenario['func'](session, *scenario['args'],
                                   **scenario['kw'])
            if scenario['delay'] > 0.:
                await cancellable_sleep(scenario['delay'])
            return 1
        except Exception as exc:
            if self.args.verbose > 0:
                self.console.print_error(exc)
                await self.console.flush()
        return -1
