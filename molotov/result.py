import time
from molotov.sharedcounter import SharedCounters


def _now():
    return int(time.time())


class ClosedError(Exception):
    pass


class LiveResults:
    def __init__(self):
        self._counters = SharedCounters('OK', 'FAILED')
        self.closed = False
        self.start = _now()

    def close(self):
        self.closed = True

    def get_successes(self):
        return self._count('OK')

    def get_failures(self):
        return self._count('FAILED')

    def _count(self, value):
        return self._counters[value].value

    def incr(self, counter, count=1):
        if self.closed:
            raise ClosedError()
        self._counters[counter] += count

    def howlong(self):
        return _now() - self.start

    def __str__(self):
        return 'SUCCESSES: %s | FAILURES: %s' % (self.get_successes(),
                                                 self.get_failures())
