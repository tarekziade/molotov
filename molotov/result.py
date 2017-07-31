import os
import time
from collections import defaultdict

from queue import Empty
from multiprocessing import Queue


def _now():
    return int(time.time())


class ClosedError(Exception):
    pass


class LiveResults:
    def __init__(self, use_buffer=True, buffer_max_age=1.):
        self._data = {os.getpid(): defaultdict(int)}
        self.start = _now()
        self.queue = Queue()
        self.closed = False
        self._buffer = {'OK': 0, 'FAILED': 0}
        self._buffer_age = time.time()
        self._bma = buffer_max_age
        self._use_buffer = use_buffer

    def close(self):
        self.closed = True

    def update(self):
        if self.closed:
            raise ClosedError()
        try:
            if not self.queue.empty():
                while True:
                    try:
                        data = self.queue.get_nowait()
                    except Empty:
                        break
                    if data is not None:
                        pid, res, count = data
                        if pid not in self._data:
                            self._data[pid] = defaultdict(int)
                        self._data[pid][res] += count
        except BrokenPipeError:
            pass

    def get_successes(self, pid=None):
        return self._count('OK', pid)

    def get_failures(self, pid=None):
        return self._count('FAILED', pid)

    def _count(self, value, pid=None):
        if pid is not None:
            res = self._data.get(pid)
            if res is not None:
                return res[value]
            return 0
        count = 0
        for pid, values in self._data.items():
            count += values[value]
        return count

    # thread-safeness?
    def _unbuffer(self):
        if time.time() - self._buffer_age < self._bma:
            return
        pid = os.getpid()
        for key, value in list(self._buffer.items()):
            try:
                self.queue.put((pid, key, value))
                self._buffer[key] = 0
            except BrokenPipeError:
                pass
        self._buffer_age = time.time()

    def _incr(self, counter, count=1):
        if self.closed:
            raise ClosedError()
        if self._use_buffer:
            self._buffer[counter] += count
            self._unbuffer()
        else:
            self.queue.put((os.getpid(), counter, count))

    def incr(self, key, count=1):
        self._incr(key, count)

    def howlong(self):
        return _now() - self.start

    def __str__(self):
        self.update()
        return 'SUCCESSES: %s | FAILURES: %s' % (self.get_successes(),
                                                 self.get_failures())
