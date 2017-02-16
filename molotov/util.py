import json
import socket
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

    if '@' in parts.netloc:
        username, password = parts.username, parts.password
        netloc = parts.netloc.split('@', 1)[1]
    else:
        username, password = None, None
        netloc = parts.netloc

    if ':' in netloc:
        host = netloc.split(':')[0]
    else:
        host = netloc

    port_provided = False
    if not parts.port and parts.scheme == 'https':
        port = 443
    elif not parts.port and parts.scheme == 'http':
        port = 80
    else:
        port = parts.port
        port_provided = True

    original = host
    resolved = None
    if host in _DNS_CACHE:
        resolved = _DNS_CACHE[host]
    else:
        try:
            resolved = gethostbyname(host)
            _DNS_CACHE[host] = resolved
        except socket.gaierror:
            return url, original, host

    # Don't use a resolved hostname for SSL requests otherwise the
    # certificate will not match the IP address (resolved)
    host = resolved if parts.scheme != 'https' else host
    netloc = host
    if port_provided:
        netloc += ':%d' % port
    if username is not None:
        if password is not None:
            netloc = '%s:%s@%s' % (username, password, netloc)
        else:
            netloc = '%s@%s' % (username, netloc)

    if port not in (443, 80):
        host += ':%d' % port
        original += ':%d' % port

    new = urlunparse((parts.scheme, netloc, parts.path or '', '',
                      parts.query or '', parts.fragment or ''))
    return new, original, host


class OptionError(Exception):
    pass


def _expand_args(args, options):
    for key, val in options.items():
        setattr(args, key, val)


def expand_options(config, scenario, args):
    if not isinstance(config, str):
        try:
            config = json.loads(config.read())
        except ValueError:
            raise OptionError("Can't parse %r" % config)
    else:
        if not os.path.exists(config):
            raise OptionError("Can't find %r" % config)

        with open(config) as f:
            try:
                config = json.loads(f.read())
            except ValueError:
                raise OptionError("Can't parse %r" % config)

    if 'molotov' not in config:
        raise OptionError("Bad config -- no molotov key")

    if 'tests' not in config['molotov']:
        raise OptionError("Bad config -- no molotov/tests key")

    if scenario not in config['molotov']['tests']:
        raise OptionError("Can't find %r in the config" % scenario)

    _expand_args(args, config['molotov']['tests'][scenario])
