import multiprocess
import multiprocessing
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
        # in Python 3.19 this will fail using `multiprocess` so we use `multiprocessing`
        if sys.version_info.minor >= 10:
            self.manager = multiprocessing.Manager()
        else:
            self.manager = multiprocess.Manager()
        self.data = self.manager.list()

    def write(self, data):
        self.data.append(data)
        if len(self.data) > self.max_lines:
            self.data[:] = self.data[-self.max_lines :]

    def create_content(self, width, height):
        items = ["\n"]

        for line in self.data:
            items.append(line)

        lines = "".join(items).split("\n")
        items = [to_formatted_text(HTML(line)) for line in lines]

        def get_line(i: int):
            return items[i]

        return UIContent(get_line=get_line, line_count=len(items), show_cursor=False)


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
    def __init__(self, refresh_interval=0.3, max_lines=25):
        self.title = TITLE
        self.terminal = TerminalController(max_lines)
        self.status = RunStatus()
        self.errors = TerminalController(max_lines)
        self.key_bindings = create_key_bindings()
        self.refresh_interval = refresh_interval
        self.max_lines = max_lines

    async def start(self):
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

        self.task = asyncio.ensure_future(self.app.run_async())

    async def stop(self):
        try:
            self.app.exit()
        except Exception:
            pass


class SharedConsole(object):
    def __init__(self, interval=0.3, max_lines_displayed=25, stream=None):
        self._interval = interval
        self._stop = True
        self._creator = os.getpid()
        self._stop = False
        self._max_lines_displayed = max_lines_displayed
        self.ui = MolotovApp(refresh_interval=interval, max_lines=max_lines_displayed)
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
            line = f'<style fg="#cecece">[P:{os.getpid()}]</style> {line}'
        self.terminal.write(line)

    def print_error(self, error, tb=None):
        for line in printable_error(error, tb):
            line = f'<style fg="gray">{line}</style>' + "\n"
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
