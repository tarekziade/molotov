import asyncio
import io
import shutil
import sys
import termios

from prompt_toolkit import HTML
from prompt_toolkit.application import Application
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)

from molotov import __version__
from molotov.ui.controllers import (
    RunStatus,
    SimpleController,
    TerminalController,
    create_key_bindings,
)
from molotov.util import cancellable_sleep

TITLE = HTML(
    f"<b>Molotov v{__version__}</b> ~ Happy Breaking 🥛🔨 ~ <i>Ctrl+C to abort</i>"
)


class MolotovApp:
    def __init__(
        self,
        refresh_interval=0.3,
        max_lines=25,
        simple_console=False,
        single_process=True,
    ):
        term_size = shutil.get_terminal_size((80, 25))
        if max_lines > (term_size.lines - 10):
            max_lines = term_size.lines - 10

        self.max_lines = max_lines
        self.title = TITLE
        self.single_process = single_process
        if not simple_console:
            try:
                sys.stdin.fileno()
            except io.UnsupportedOperation:
                # This is not a terminal
                simple_console = True

        self.simple_console = simple_console
        if simple_console:
            controller_klass = SimpleController
        else:
            controller_klass = TerminalController
        if max_lines >= 0:
            self.terminal = controller_klass(max_lines, single_process)
            self.errors = controller_klass(max_lines, single_process)
        else:
            self.terminal = self.errors = None
        self.status = RunStatus()
        self.key_bindings = create_key_bindings()
        self.refresh_interval = refresh_interval
        self._running = False
        self._term_settings = None

    def _dump_term(self, max_lines=25):
        for line in self.terminal.dump(max_lines):
            sys.stdout.write(line)
            sys.stdout.flush()

    def _dump_errors(self, max_lines=25):
        for line in self.errors.dump(max_lines):
            sys.stdout.write(line)
            sys.stdout.flush()

    async def refresh_console(self):
        while self._running:
            self._dump_term()
            await asyncio.sleep(0)
            self._dump_errors()
            await cancellable_sleep(self.refresh_interval)

    async def start(self):
        self._running = True

        if self.simple_console:
            self.task = asyncio.ensure_future(self.refresh_console())
            return

        title_toolbar = Window(
            FormattedTextControl(lambda: self.title),
            height=1,
            style="class:title",
        )

        bottom_toolbar = Window(
            content=self.status,
            style="class:bottom-toolbar",
            height=1,
        )

        if self.terminal is not None:
            terminal = Window(content=self.terminal, height=self.max_lines + 2)
            errors = Window(content=self.errors, height=self.max_lines + 2)
            splits = [
                title_toolbar,
                VSplit([terminal, Window(width=4, char=" || "), errors]),
                bottom_toolbar,
            ]

        else:
            splits = [title_toolbar, bottom_toolbar]

        self.app = Application(
            min_redraw_interval=0.05,
            layout=Layout(HSplit(splits)),
            style=None,
            key_bindings=self.key_bindings,
            refresh_interval=self.refresh_interval,
            color_depth=None,
            output=None,
            input=None,
            erase_when_done=True,
        )

        try:
            self._term_settings = termios.tcgetattr(sys.stdin)
        except Exception:
            pass  # could be under pytest

        def _handle_exception(*args, **kw):
            pass

        self.app._handle_exception = _handle_exception
        self.task = asyncio.ensure_future(self.app.run_async())

    async def stop(self):
        self._running = False
        cancellable_sleep.cancel_all()

        # dump any remaining data
        self._dump_term()
        self._dump_errors()

        if not self.simple_console:
            try:
                self.app.exit()
            except Exception:
                pass
            if self._term_settings is not None:
                termios.tcsetattr(sys.stdin, termios.TCSANOW, self._term_settings)
            # shows back the cursor
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
        else:
            await self.task
        self.terminal.close()
        self.errors.close()
