import os
import sys
from contextlib import contextmanager


@contextmanager
def stream_log(msg, pid=True):
    if pid:
        msg = '[%d] %s...' % (os.getpid(), msg)
    sys.stdout.write(msg)
    sys.stdout.flush()

    yield

    sys.stdout.write('OK\n')
    sys.stdout.flush()


def log(msg, pid=True):
    if pid:
        print('[%d] %s' % (os.getpid(), msg))
    else:
        print(msg)
