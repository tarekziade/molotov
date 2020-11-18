import asyncio
import time
from inspect import isgenerator

from molotov.listeners import EventSender
from molotov.session import LoggedClientSession as Session
from molotov.api import get_fixture, pick_scenario, get_scenario, next_scenario
from molotov.util import cancellable_sleep, is_stopped, set_timer, get_timer, stop


class FixtureError(Exception):
    pass


def _now():
    return int(time.time())


class Worker(object):
    """"The Worker class creates a Session and runs scenario.
    """

    def __init__(self, wid, results, console, args, statsd=None, delay=0, loop=None):
        self.wid = wid
        self.results = results
        self.console = console
        self.loop = loop or asyncio.get_event_loop()
        self.args = args
        self.statsd = statsd
        self.delay = delay
        self.count = 0
        self.worker_start = 0
        self.eventer = EventSender(console)
        self._exhausted = False
        self.resolve_dns = not args.disable_dns_resolve
        # fixtures
        self._session_setup = get_fixture("setup_session")
        self._session_teardown = get_fixture("teardown_session")
        self._setup = get_fixture("setup")
        self._teardown = get_fixture("teardown")

    async def send_event(self, event, **options):
        await self.eventer.send_event(event, wid=self.wid, **options)

    async def run(self):
        if self.delay > 0.0:
            await cancellable_sleep(self.delay)
        if is_stopped():
            return
        self.results["WORKER"] += 1
        self.results["MAX_WORKERS"] += 1
        try:
            res = await self._run()
        finally:
            self.teardown()
            self.results["WORKER"] -= 1
        return res

    def _may_run(self):
        if is_stopped():
            return False
        if _now() - self.worker_start > self.args.duration:
            return False
        if self._exhausted:
            return False
        if self.results["REACHED"] == 1:
            return False
        if self.args.max_runs and self.count > self.args.max_runs:
            return False
        return True

    async def setup(self):
        if self._setup is None:
            return {}
        try:
            options = await self._setup(self.wid, self.args)
        except Exception as e:
            self.console.print_error(e)
            raise FixtureError(str(e))

        if options is None:
            options = {}
        elif not isinstance(options, dict):
            msg = "The setup function needs to return a dict"
            self.console.print(msg)
            raise FixtureError(msg)

        return options

    async def session_setup(self, session):
        if self._session_setup is None:
            return
        try:
            await self._session_setup(self.wid, session)
        except Exception as e:
            self.console.print_error(e)
            raise FixtureError(str(e))

    async def session_teardown(self, session):
        if self._session_teardown is None:
            return
        try:
            await self._session_teardown(self.wid, session)
        except Exception as e:
            # we can't stop the teardown process
            self.console.print_error(e)

    async def _run(self):
        verbose = self.args.verbose
        exception = self.args.exception

        if self.args.single_mode:
            single = get_scenario(self.args.single_mode)
        elif self.args.single_run:
            single = next_scenario()
        else:
            single = None

        self.count = 1
        self.worker_start = _now()

        try:
            options = await self.setup()
        except FixtureError as e:
            self.results["SETUP_FAILED"] += 1
            stop(why=e)
            return

        async with Session(
            self.loop, self.console, verbose, self.statsd, self.resolve_dns, **options
        ) as session:
            session.args = self.args
            session.worker_id = self.wid

            try:
                await self.session_setup(session)
            except FixtureError as e:
                self.results["SESSION_SETUP_FAILED"] += 1
                stop(why=e)
                return

            while self._may_run():
                step_start = _now()
                session.step = self.count
                result = await self.step(self.count, session, scenario=single)
                if result == 1:
                    self.results["OK"] += 1
                    self.results["MINUTE_OK"] += 1
                elif result != 0:
                    self.results["FAILED"] += 1
                    self.results["MINUTE_FAILED"] += 1
                    if exception:
                        stop(why=result)

                if not is_stopped() and self._reached_tolerance(step_start):
                    stop()
                    cancellable_sleep.cancel_all()
                    break

                self.count += 1
                if self.args.delay > 0.0:
                    await cancellable_sleep(self.args.delay)
                else:
                    # forces a context switch
                    await asyncio.sleep(0)

            await self.session_teardown(session)

    def teardown(self):
        if self._teardown is None:
            return
        try:
            self._teardown(self.wid)
        except Exception as e:
            # we can't stop the teardown process
            self.console.print_error(e)

    def _reached_tolerance(self, current_time):
        if not self.args.sizing:
            return False

        if current_time - get_timer() > 60:
            # we need to reset the tolerance counters
            set_timer(current_time)
            self.results["MINUTE_OK"].value = 0
            self.results["MINUTE_FAILED"].value = 0
            return False

        OK = self.results["MINUTE_OK"].value
        FAILED = self.results["MINUTE_FAILED"].value

        if OK + FAILED < 100:
            # we don't have enough samples
            return False

        current_ratio = float(FAILED) / float(OK) * 100.0
        reached = current_ratio > self.args.sizing_tolerance
        if reached:
            self.results["REACHED"].value = 1
            self.results["RATIO"].value = int(current_ratio * 100)

        return reached

    async def step(self, step_id, session, scenario=None):
        """ single scenario call.

        When it returns 1, it works. -1 the script failed,
        0 the test is stopping or needs to stop.
        """
        if scenario is None:
            scenario = pick_scenario(self.wid, step_id)
        elif isgenerator(scenario):
            try:
                scenario = next(scenario)
            except StopIteration:
                self._exhausted = True
                return 0
        try:
            await self.send_event("scenario_start", scenario=scenario)

            await scenario["func"](session, *scenario["args"], **scenario["kw"])

            await self.send_event("scenario_success", scenario=scenario)

            if scenario["delay"] > 0.0:
                await cancellable_sleep(scenario["delay"])
            return 1
        except Exception as exc:
            await self.send_event("scenario_failure", scenario=scenario, exception=exc)
            if self.args.verbose > 0:
                self.console.print_error(exc)
                await self.console.flush()
            return exc

        return -1
