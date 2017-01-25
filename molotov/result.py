import os
from io import StringIO
import time
try:
    import redis
except ImportError:
    redis = None


def _now():
    return int(time.time())


class LiveResults:
    def __init__(self, pid=os.getpid()):
        self.pid = pid
        self.OK = 0
        self.FAILED = 0
        self.last_tb = StringIO()
        self.stream = StringIO()
        self.start = _now()
        if redis is not None:
            self.r = redis.StrictRedis(host='localhost', port=6379, db=0)
        else:
            self.r = None

    def get_successes(self):
        if self.pid == os.getpid() or self.r is None:
            return self.OK
        res = self.r.get('motolov:%d:OK' % self.pid)
        if res is None:
            return 0
        return int(res)

    def get_failures(self):
        if self.pid == os.getpid() or self.r is None:
            return self.FAILED
        res = self.r.get('motolov:%d:FAILED' % self.pid)
        if res is None:
            return 0
        return int(res)

    def incr_success(self):
        self.OK += 1
        self.r.incr('motolov:%d:OK' % os.getpid())

    def incr_failure(self):
        self.FAILED += 1
        self.r.incr('motolov:%d:FAILED' % os.getpid())

    def howlong(self):
        return _now() - self.start

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
