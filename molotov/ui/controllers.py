import multiprocess
import queue
import os
import signal
from datetime import datetime

import humanize
from prompt_toolkit import HTML
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.controls import UIContent, UIControl


def create_key_bindings():
    kb = KeyBindings()

    @kb.add("c-l")
    def _clear(event):
        event.app.renderer.clear()

    @kb.add("c-c")
    def _interrupt(event):
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
        try:
            self.data.append(data)
            if len(self.data) > self.max_lines:
                self.data[:] = self.data[-self.max_lines :]
        except BrokenPipeError:
            pass

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
        self._started = datetime.now()

    def update(self, results):
        self._status.update(results)

    def formatted(self):
        delta = datetime.now() - self._started
        return to_formatted_text(
            HTML(
                f'<style fg="green" bg="#cecece">SUCCESS: {self._status.get("OK", 0)} </style>'
                f'<style fg="red" bg="#cecece"> FAILED: {self._status.get("FAILED", 0)} </style>'
                f' WORKERS: {self._status.get("WORKER", 0)}'
                f' PROCESSES: {self._status.get("PROCESS", 0)} '
                f'<style fg="blue" bg="#cecece"> ELAPSED: {humanize.precisedelta(delta)}</style>'
            )
        )

    def create_content(self, width: int, height: int) -> UIContent:
        def get_line(i):
            return self.formatted()

        return UIContent(get_line=get_line, line_count=1, show_cursor=False)
