import os
import time
from queue import Empty
from multiprocessing import Queue


def _now():
    return int(time.time())


class ClosedError(Exception):
    pass


class LiveResults:
    def __init__(self, use_buffer=True, buffer_max_age=1.):
        self._data = {os.getpid(): {'OK': 0, 'FAILED': 0}}
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
                            self._data[pid] = {'OK': 0, 'FAILED': 0}
                        if res == 'OK':
                            self._data[pid]['OK'] += count
                        if res == 'FAILED':
                            self._data[pid]['FAILED'] += count
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
        ok_count = self._buffer['OK']
        self._buffer['OK'] = 0
        failed_count = self._buffer['FAILED']
        self._buffer['FAILED'] = 0
        self._buffer_age = time.time()
        try:
            self.queue.put((pid, 'OK', ok_count))
            self.queue.put((pid, 'FAILED', failed_count))
        except BrokenPipeError:
            pass

    def _incr(self, counter, count=1):
        if self.closed:
            raise ClosedError()
        if self._use_buffer:
            self._buffer[counter] += count
            self._unbuffer()
        else:
            self.queue.put((os.getpid(), counter, count))

    def incr_success(self, count=1):
        self._incr('OK', count)

    def incr_failure(self, count=1):
        self._incr('FAILED', count)

    def howlong(self):
        return _now() - self.start

    def __str__(self):
        self.update()
        return 'SUCCESSES: %s | FAILURES: %s' % (self.get_successes(),
                                                 self.get_failures())
