import os
import sys
from contextlib import contextmanager
from urllib.parse import urlparse, urlunparse
from socket import gethostbyname


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


_DNS_CACHE = {}


def resolve(url):
    parts = urlparse(url)

    if ':' in parts.netloc:
        host = parts.netloc.split(':')[0]
    else:
        host = parts.netloc

    if not parts.port and parts.scheme == 'https':
        port = 443
    elif not parts.port and parts.scheme == 'http':
        port = 80
    else:
        port = parts.port

    original = host
    if host in _DNS_CACHE:
        resolved = _DNS_CACHE[host]
    else:
        resolved = gethostbyname(host)
        _DNS_CACHE[host] = resolved

    # Don't use a resolved hostname for SSL requests otherwise the
    # certificate will not match the IP address (resolved)
    host = resolved if parts.scheme != 'https' else host
    netloc = '%s:%d' % (host, port) if port else host

    if port not in (443, 80):
        host += ':%d' % port
        original += ':%d' % port

    new = urlunparse(parts.scheme, netloc, parts.path or '', '',
                     parts.query or '', parts.fragment or '')
    return new, original, host
