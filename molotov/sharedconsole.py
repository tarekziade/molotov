import multiprocess
import asyncio
import os
import signal
import sys

from prompt_toolkit import HTML
from prompt_toolkit.formatted_text import StyleAndTextTuples
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


class UIControlWithKeys(UIControl):
    def __init__(self, max_lines=25):
        super().__init__()
        self.max_lines = max_lines
        self._key_bindings = create_key_bindings()

    def is_focusable(self) -> bool:
        return True  # Make sure that the key bindings work.

    def get_key_bindings(self):
        return self._key_bindings


class TerminalController(UIControlWithKeys):
    def __init__(self, max_lines=25):
        super().__init__(max_lines)
        self.manager = multiprocess.Manager()
        self.data = self.manager.list()
        self._closed = False

    def close(self):
        self._closed = True
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


class SimpleController:
    def __init__(self):
        self.data = multiprocess.Queue()

    def close(self):
        pass

    def write(self, data):
        self.data.put(data)

    def dump(self):
        while not self.data.empty():
            yield self.data.get()


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


class RunStatus(UIControlWithKeys):
    def __init__(self, max_lines=25):
        super().__init__(max_lines)
        self.ok = multiprocess.Value("i", 0)
        self.failed = multiprocess.Value("i", 0)
        self.worker = multiprocess.Value("i", 0)
        self.process = multiprocess.Value("i", 0)

    def update(self, results):
        if "OK" in results:
            self.ok.value = results["OK"].value
        if "FAILED" in results:
            self.failed.value = results["FAILED"].value
        if "WORKER" in results:
            self.worker.value = results["WORKER"].value
        if "PROCESS" in results:
            self.process.value = results["PROCESS"].value

    def formatted(self):
        return to_formatted_text(
            HTML(
                f'<style fg="green" bg="#cecece">SUCCESS: {self.ok.value} </style>'
                f'<style fg="red" bg="#cecece"> FAILED: {self.failed.value} </style>'
                f" WORKERS: {self.worker.value}"
                f" PROCESSES: {self.process.value}"
            )
        )

    def create_content(self, width: int, height: int) -> UIContent:
        def get_line(i: int) -> StyleAndTextTuples:
            return self.formatted()

        return UIContent(get_line=get_line, line_count=1, show_cursor=False)


class MolotovApp:
    def __init__(self, refresh_interval=0.3, max_lines=25, simple_console=False):
        self.title = TITLE
        self.simple_console = simple_console
        if simple_console:
            self.terminal = SimpleController()
            self.errors = SimpleController()
        else:
            self.terminal = TerminalController(max_lines)
            self.errors = TerminalController(max_lines)
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
    def __init__(self, interval=0.3, max_lines_displayed=25, simple_console=False):
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

    def print(self, line):
        line += "\n"
        if os.getpid() != self._creator:
            if self._simple_console:
                line = f"[P:{os.getpid()}]</style> {line}"
            else:
                line = f'<style fg="#cecece">[P:{os.getpid()}]</style> {line}'
        self.terminal.write(line)

    def print_error(self, error, tb=None):
        for line in printable_error(error, tb):
            if self._simple_console:
                line += "\n"
            else:
                line = f'<style fg="gray">{line}</style>\n'
            self.errors.write(line)
        self.errors.write("\n")

    def print_block(self, start, callable, end="OK"):
        if os.getpid() != self._creator:
            prefix = f'<style fg="#cecece">[P:{os.getpid()}]</style>'
        else:
            prefix = ""
        self.terminal.write(prefix + start + "...\n")
        res = callable()
        self.terminal.write(prefix + "OK\n")
        return res
