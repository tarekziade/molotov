import os

from molotov.util import printable_error
from molotov.ui.app import MolotovApp


class SharedConsole(object):
    def __init__(
        self,
        interval=0.3,
        max_lines_displayed=25,
        simple_console=False,
        single_process=True,
    ):
        self._interval = interval
        self._stop = True
        self._creator = os.getpid()
        self._stop = False
        self._max_lines_displayed = max_lines_displayed
        self._simple_console = simple_console
        self.ui = MolotovApp(
            refresh_interval=interval,
            max_lines=max_lines_displayed,
            simple_console=simple_console,
            single_process=single_process,
        )
        self.terminal = self.ui.terminal
        self.errors = self.ui.errors
        self.status = self.ui.status
        self.started = False

    async def start(self):
        await self.ui.start()
        self.started = True

    async def stop(self):
        await self.ui.stop()
        self.started = False

    def print_results(self, results):
        self.status.update(results)

    def print(self, data):
        if self.terminal is None:
            return
        for line in data.split("\n"):
            line = line.strip()
            self.terminal.write_line(line)

    def print_error(self, error, tb=None):
        if self.errors is None:
            return
        if isinstance(error, str):
            for line in error.split("\n"):
                line = line.strip()
                self.errors.write_line(line, fg="gray")
            return

        for line in printable_error(error, tb):
            self.errors.write_line(line, fg="gray")

        self.errors.write_line("", fg="gray")

    def print_block(self, start, callable, end="OK"):
        if self.terminal is None:
            return callable()

        self.terminal.write_line(f"{start}...")
        try:
            return callable()
        finally:
            self.terminal.write_line("OK")
