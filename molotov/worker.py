import asyncio
from inspect import isgenerator, signature

from molotov.api import get_fixture, get_scenario, next_scenario, pick_scenario
from molotov.listeners import EventSender
from molotov.session import get_context, get_session
from molotov.util import cancellable_sleep, get_timer, is_stopped, now, set_timer, stop


class FixtureError(Exception):
    pass


class Worker:
    """ "The Worker class creates a Session and runs scenario."""

    def __init__(
        self,
        wid,
        results,
        console,
        args,
        statsd=None,
        delay=0,
        loop=None,
    ):
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
        # fixtures
        self._session_setup = get_fixture("setup_session")
        self._session_teardown = get_fixture("teardown_session")
        self._setup = get_fixture("setup")
        self._teardown = get_fixture("teardown")
        self._active_sessions = {}

    def print(self, line):
        self.console.print(f"[W:{self.wid}] {line}")

    async def send_event(self, event, **options):
        await self.eventer.send_event(event, wid=self.wid, **options)

    async def run(self):
        self.print("Starting")
        await asyncio.sleep(0)
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
        if now() - self.worker_start > self.args.duration:
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
            raise FixtureError(str(e)) from e

        if options is None:
            options = {}
        elif not isinstance(options, dict):
            msg = "The setup function needs to return a dict"
            self.print(msg)
            raise FixtureError(msg)

        return options

    async def session_setup(self, session):
        if self._session_setup is None:
            return
        try:
            await self._session_setup(self.wid, session)
        except Exception as e:
            self.console.print_error(e)
            raise FixtureError(str(e)) from e

    async def session_teardown(self):
        for _, session in self._active_sessions.items():
            if self._session_teardown is not None:
                try:
                    await self._session_teardown(self.wid, session)
                except Exception as e:
                    # we can't stop the teardown process
                    self.console.print_error(e)
            try:
                await session.close()
            except Exception:
                pass

    async def _get_session(self, kind, **options):
        if kind in self._active_sessions:
            session = self._active_sessions[kind]
        else:
            self.print(f"Setting up session of kind {kind}")
            # needs creation
            session = get_session(
                self.loop,
                self.console,
                self.args.verbose,
                self.statsd,
                kind=kind,
                **options,
            )

            context = get_context(session)
            if context is not None:
                context.args = self.args  # type: ignore
                context.worker_id = self.wid  # type: ignore

            try:
                await self.session_setup(session)
            except FixtureError as e:
                self.results["SESSION_SETUP_FAILED"] += 1
                stop(why=e)
                return
            self._active_sessions[kind] = session

        context = get_context(session)
        if context is not None:
            context.step = self.count  # type: ignore
        return session

    async def _run(self):
        if self.statsd and not self.statsd.connected:
            try:
                await self.statsd.connect()
                await asyncio.sleep(0)
            except Exception as e:
                print(e)

        exception = self.args.exception

        if self.args.single_mode:
            single = get_scenario(self.args.single_mode)
        elif self.args.single_run:
            single = next_scenario()
        else:
            single = None

        self.count = 1
        self.worker_start = now()

        try:
            options = await self.setup()
        except FixtureError as e:
            self.results["SETUP_FAILED"] += 1
            stop(why=e)
            return

        self.print("Running scenarios")

        while self._may_run():
            if self.count % 10 == 0:
                self.print(f"Ran {self.count} scenarios")
            step_start = now()
            result = await self.step(self.count, scenario=single, options=options)

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

        self.print("Done!")
        await self.session_teardown()

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

    async def step(self, step_id, scenario=None, options=None):
        """single scenario call.

        When it returns 1, it works. -1 the script failed,
        0 the test is stopping or needs to stop.
        """
        if options is None:
            options = {}

        if scenario is None:
            scenario = pick_scenario(self.wid, step_id)
        elif isgenerator(scenario):
            try:
                scenario = next(scenario)
            except StopIteration:
                self._exhausted = True
                return 0

        if scenario is None:
            msg = "Could not pick a scenario"
            exc = ValueError(msg)
            self.print(msg)
            self.console.print_error(exc)
            return exc

        func = scenario["func"]
        sig = signature(func)
        session_kind = sig.parameters.get("session_factory")

        if session_kind is not None and session_kind.default is not None:
            session_kind = session_kind.default
            for name, param in sig.parameters.items():
                if name == "session_factory":
                    continue
                options[name] = param.default
        else:
            session_kind = "http"

        try:
            session = await self._get_session(session_kind, **options)
        except Exception as exc:
            await self.send_event("scenario_failure", scenario=scenario, exception=exc)
            self.print("Session creation failure!")
            self.console.print_error(exc)
            return exc

        try:
            await self.send_event("scenario_start", scenario=scenario)
            await func(session, *scenario["args"], **scenario["kw"])
            await self.send_event("scenario_success", scenario=scenario)

            if scenario["delay"] > 0.0:
                await cancellable_sleep(scenario["delay"])
            return 1
        except Exception as exc:
            await self.send_event("scenario_failure", scenario=scenario, exception=exc)
            self.print("Failure!")
            self.console.print_error(exc)

            return exc
