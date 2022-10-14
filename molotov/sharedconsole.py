import multiprocess
import queue
import asyncio
import os
import signal
import sys

from prompt_toolkit import HTML
from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import UIContent, UIControl

from molotov import __version__
from molotov.util import printable_error


TITLE = HTML(
    f"<b>Molotov v{__version__}</b> ~ Happy Breaking 🥛🔨 ~ <i>Ctrl+C to abort</i>"
)


def create_key_bindings():
    kb = KeyBindings()

    @kb.add("c-l")
    def _clear(event):
        event.app.renderer.clear()

    @kb.add("c-c")
    def _interrupt(event):
        event.app.exit()
        os.kill(os.getpid(), signal.SIGTERM)

    return kb


class BaseController(UIControl):
    def __init__(self, max_lines=25, add_style=True):
        super().__init__()
        self._creator = os.getpid()
        self.max_lines = max_lines
        self._add_style = add_style
        self._key_bindings = create_key_bindings()

    def create_content(self, width, height):
        raise NotImplementedError

    def is_focusable(self):
        return True

    def get_key_bindings(self):
        return self._key_bindings

    def write(self, data):
        raise NotImplementedError

    def write_line(self, data, fg=None):
        if self._add_style and fg is not None:
            data = f'<style fg="{fg}">{data}</style>'

        # pid header
        if os.getpid() != self._creator:
            if not self._add_style:
                data = f"[P:{os.getpid()} {data}"
            else:
                data = f'<style fg="#cecece">[P:{os.getpid()}]</style> {data}'

        self.write(f"{data}\n")


class TerminalController(BaseController):
    def __init__(self, max_lines=25, single_process=True):
        super().__init__(max_lines, add_style=True)
        self.single_process = single_process
        if not single_process:
            self.manager = multiprocess.Manager()
            self.data = self.manager.list()
        else:
            self.data = list()
        self._closed = False

    def close(self):
        self._closed = True
        if not self.single_process:
            self.manager.shutdown()

    def write(self, data):
        if self._closed:
            return
        self.data.append(data)
        if len(self.data) > self.max_lines:
            self.data[:] = self.data[-self.max_lines :]

    def create_content(self, width, height):
        items = ["\n"]

        def format_items():
            lines = "".join(items).split("\n")
            items[:] = [to_formatted_text(HTML(line)) for line in lines]

        def get_line(i: int):
            return items[i]

        if self._closed:
            items.append("data stream closed!")
            format_items()
            return UIContent(
                get_line=get_line, line_count=len(items), show_cursor=False
            )

        for line in self.data:
            items.append(line)

        format_items()
        return UIContent(get_line=get_line, line_count=len(items), show_cursor=False)


class SimpleController(BaseController):
    def __init__(self, max_lines, single_process=True):
        super().__init__(max_lines, add_style=False)
        if single_process:
            self.data = queue.Queue()
        else:
            self.data = multiprocess.Queue()

    def close(self):
        pass

    def write(self, data):
        self.data.put(data)

    def dump(self):
        while not self.data.empty():
            yield self.data.get()


class RunStatus(BaseController):
    def __init__(self, max_lines=25):
        super().__init__(max_lines)
        self._status = {}

    def update(self, results):
        self._status.update(results)

    def formatted(self):
        return to_formatted_text(
            HTML(
                f'<style fg="green" bg="#cecece">SUCCESS: {self._status.get("OK", 0)} </style>'
                f'<style fg="red" bg="#cecece"> FAILED: {self._status.get("FAILED", 0)} </style>'
                f' WORKERS: {self._status.get("WORKER", 0)}'
                f' PROCESSES: {self._status.get("PROCESS", 0)}'
            )
        )

    def create_content(self, width: int, height: int) -> UIContent:
        def get_line(i):
            return self.formatted()

        return UIContent(get_line=get_line, line_count=1, show_cursor=False)


class MolotovApp:
    def __init__(
        self,
        refresh_interval=0.3,
        max_lines=25,
        simple_console=False,
        single_process=True,
    ):
        self.title = TITLE
        self.single_process = single_process
        self.simple_console = simple_console
        if simple_console:
            controller_klass = SimpleController
        else:
            controller_klass = TerminalController
        self.terminal = controller_klass(max_lines, single_process)
        self.errors = controller_klass(max_lines, single_process)
        self.status = RunStatus()
        self.key_bindings = create_key_bindings()
        self.refresh_interval = refresh_interval
        self.max_lines = max_lines
        self._running = False

    async def refresh_console(self):
        while self._running:
            for line in self.terminal.dump():
                sys.stdout.write(line)
                sys.stdout.flush()
            for line in self.errors.dump():
                sys.stdout.write(line)
                sys.stdout.flush()
            await asyncio.sleep(self.refresh_interval)

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

        terminal = Window(content=self.terminal, height=self.max_lines + 2)
        errors = Window(content=self.errors, height=self.max_lines + 2)

        self.app = Application(
            min_redraw_interval=0.05,
            layout=Layout(
                HSplit(
                    [
                        title_toolbar,
                        VSplit([terminal, Window(width=4, char=" || "), errors]),
                        bottom_toolbar,
                    ]
                )
            ),
            style=None,
            key_bindings=self.key_bindings,
            refresh_interval=self.refresh_interval,
            color_depth=None,
            output=None,
            input=None,
            erase_when_done=True,
        )

        def _handle_exception(*args, **kw):
            pass

        self.app._handle_exception = _handle_exception
        self.task = asyncio.ensure_future(self.app.run_async())

    async def stop(self):
        self._running = False
        await asyncio.sleep(0)

        if not self.simple_console:
            try:
                self.app.exit()
            except Exception:
                pass
        self.terminal.close()
        self.errors.close()
        await self.task


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
        for line in data.split("\n"):
            line = line.strip()
            self.terminal.write_line(line)

    def print_error(self, error, tb=None):
        if isinstance(error, str):
            for line in error.split("\n"):
                line = line.strip()
                self.errors.write_line(line, fg="gray")
            return

        for line in printable_error(error, tb):
            self.errors.write_line(line, fg="gray")

        self.errors.write_line("", fg="gray")

    def print_block(self, start, callable, end="OK"):
        self.terminal.write_line(f"{start}...")
        try:
            return callable()
        finally:
            self.terminal.write_line("OK")
