import os
from io import StringIO
import time
import asyncio
from queue import Empty
from multiprocessing import Queue


def _now():
    return int(time.time())


class LiveResults:
    def __init__(self, loop=None):
        self._data = {os.getpid(): {'OK': 0, 'FAILED': 0}}
        self.last_tb = StringIO()
        self.stream = StringIO()
        self.start = _now()
        if loop is None:
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        self.queue = Queue()
        self.loop.call_soon(self._update)

    def _update(self):
        if not self.queue.empty():
            while True:
                try:
                    data = self.queue.get_nowait()
                except Empty:
                    break
                if data is not None:
                    pid, res, count = data
                    if pid not in self._data:
                        self._data[pid] = {'OK': 0, 'FAILED': 0}
                    if res == 'OK':
                        self._data[pid]['OK'] += count
                    if res == 'FAILED':
                        self._data[pid]['FAILED'] += count

        self.loop.call_later(.2, self._update)

    def get_successes(self):
        return self._count('OK')

    def get_failures(self):
        return self._count('FAILED')

    def _count(self, value):
        count = 0
        for pid, values in self._data.items():
            count += values[value]
        return count

    def incr_success(self, count=1):
        self.queue.put((os.getpid(), 'OK', count))

    def incr_failure(self, count=1):
        self.queue.put((os.getpid(), 'FAILED', count))

    def howlong(self):
        return _now() - self.start

    def display(self, loop):
        print(self.__str__(), end='\r')
        loop.call_later(.3, self.display, loop)

    def __str__(self):
        # XXX display TB or Stream
        stream = self.stream.read()
        if stream != '':
            return stream

        last_tb = self.last_tb.read()
        if last_tb != '':
            return last_tb

        return 'SUCCESSES: %s | FAILURES: %s' % (self.get_successes(),
                                                 self.get_failures())
