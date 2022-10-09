import multiprocess
import asyncio
import os
import signal

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


TITLE = HTML(f"<b>Molotov v{__version__}</b> Ctrl+C to  abort.")


class UIControlWithKeys(UIControl):
    def __init__(self, size=25):
        super().__init__()
        self.size = size
        self._key_bindings = create_key_bindings()

    def is_focusable(self) -> bool:
        return True  # Make sure that the key bindings work.

    def get_key_bindings(self):
        return self._key_bindings


class TerminalController(UIControlWithKeys):
    def __init__(self, size=25):
        super().__init__(size)
        self.manager = multiprocess.Manager()
        self.data = self.manager.list()

    def write(self, data):
        self.data.append(data)
        if len(self.data) > self.size:
            self.data = self.data[-self.size :]

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
    def __init__(self, size=25):
        super().__init__(size)
        self.update({})

    def update(self, results):
        self.ok = results.get("OK", 0)
        self.failed = results.get("FAILED", 0)
        self.worker = results.get("WORKER", 0)

    def formatted(self):
        return to_formatted_text(
            HTML(f"SUCCESS: {self.ok}, FAILED: {self.failed}, WORKERS: {self.worker}")
        )

    def create_content(self, width: int, height: int) -> UIContent:
        def get_line(i: int) -> StyleAndTextTuples:
            return self.formatted()

        return UIContent(get_line=get_line, line_count=1, show_cursor=False)


class MolotovApp:
    def __init__(self):
        self.title = TITLE
        self.terminal = TerminalController()
        self.status = RunStatus()
        self.errors = TerminalController()
        self.key_bindings = create_key_bindings()

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

        terminal = Window(content=self.terminal, height=self.terminal.size + 2)
        errors = Window(content=self.errors, height=self.errors.size + 2)

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
            refresh_interval=0.3,
            color_depth=None,
            output=None,
            input=None,
            erase_when_done=True,
        )

        self.task = asyncio.ensure_future(self.app.run_async())

    async def stop(self):
        self.app.exit()


class SharedConsole(object):
    def __init__(self, interval=0.1, max_lines_displayed=20, stream=None):
        self._interval = interval
        self._stop = True
        self._creator = os.getpid()
        self._stop = False
        self._max_lines_displayed = max_lines_displayed
        self.ui = MolotovApp()
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
            line = "[%d] %s" % (os.getpid(), line)
        self.terminal.write(line)

    def print_error(self, error, tb=None):
        for line in printable_error(error, tb):
            line += "\n"
            self.errors.write(line)

    def print_block(self, start, callable, end="OK"):
        if os.getpid() != self._creator:
            prefix = "[%d] " % os.getpid()
        else:
            prefix = ""
        self.terminal.write(prefix + start + "...\n")
        res = callable()
        self.terminal.write(prefix + "OK\n")
        return res
