import sys
import traceback
from io import StringIO
import asyncio
import multiprocessing
import os
from queue import Empty

from molotov.util import cancellable_sleep


class SharedConsole(object):
    """Multi-process compatible stdout console.
    """
    def __init__(self, interval=.1, max_lines_displayed=20):
        self._stream = multiprocessing.Queue()
        self._interval = interval
        self._stop = True
        self._creator = os.getpid()
        self._stop = False
        self._max_lines_displayed = max_lines_displayed

    async def stop(self):
        self._stop = True
        while True:
            try:
                sys.stdout.write(self._stream.get_nowait())
            except Empty:
                break
        sys.stdout.flush()

    async def flush(self):
        sys.stdout.flush()
        await asyncio.sleep(0)

    async def display(self):
        if os.getpid() != self._creator:
            return

        while not self._stop:
            lines_displayed = 0
            while True:
                try:
                    line = self._stream.get_nowait()
                    sys.stdout.write(line)
                    lines_displayed += 1
                except Empty:
                    break
                if self._stop or lines_displayed > self._max_lines_displayed:
                    break
                else:
                    await asyncio.sleep(0)
            sys.stdout.flush()
            if not self._stop:
                await cancellable_sleep(self._interval)

    def print(self, line, end='\n'):
        if os.getpid() != self._creator:
            line = "[%d] %s" % (os.getpid(), line)
        line += end
        self._stream.put_nowait(line)

    def print_error(self, error, tb=None):
        self.print(repr(error))
        if tb is None:
            tb = sys.exc_info()[2]
        printed = StringIO()
        traceback.print_tb(tb, file=printed)
        printed.seek(0)
        for line in printed.readlines():
            self.print(line, end='')

    def print_block(self, start, callable, end='OK'):
        if os.getpid() != self._creator:
            prefix = "[%d] " % os.getpid()
        else:
            prefix = ''
        self._stream.put(prefix + start + '...\n')
        res = callable()
        self._stream.put(prefix + 'OK\n')
        return res
