import functools
import json
import socket
import os
import sys
import asyncio
from contextlib import contextmanager
from urllib.parse import urlparse, urlunparse
from socket import gethostbyname
from aiohttp import ClientSession


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


def _run_in_fresh_loop(coro):
    loop = asyncio.new_event_loop()
    res = None
    try:
        task = loop.create_task(coro(loop=loop))
        res = loop.run_until_complete(task)
    finally:
        loop.close()
    return res


async def _request(endpoint, verb='GET', session_options=None,
                   json=False, loop=None, **options):
    if session_options is None:
        session_options = {}

    async with ClientSession(loop=loop, **session_options) as session:
        meth = getattr(session, verb.lower())
        result = {}
        async with meth(endpoint, **options) as resp:
            if json:
                result['content'] = await resp.json()
            else:
                result['content'] = await resp.text()
            result['status'] = resp.status
            result['headers'] = resp.headers

        return result


def request(endpoint, verb='GET', session_options=None, **options):
    """Performs a synchronous request.

    Uses a dedicated event loop and aiohttp.ClientSession object.

    Options:

    - endpoint: the endpoint to call
    - verb: the HTTP verb to use (defaults: GET)
    - session_options: a dict containing options to initialize the session
      (defaults: None)
    - options: extra options for the request (defaults: None)

    Returns a dict object with the following keys:

    - content: the content of the response
    - status: the status
    - headers: a dict with all the response headers
    """
    req = functools.partial(_request, endpoint, verb, session_options,
                            **options)
    return _run_in_fresh_loop(req)


def json_request(endpoint, verb='GET', session_options=None, **options):
    """Like :func:`molotov.request` but extracts json from the response.
    """
    req = functools.partial(_request, endpoint, verb, session_options,
                            json=True, **options)
    return _run_in_fresh_loop(req)


_VARS = {}


def set_var(name, value):
    """Sets a global variable.

    Options:

    - name: name of the variable
    - value: object to set
    """
    _VARS[name] = value


def get_var(name, factory=None):
    """Gets a global variable given its name.

    If factory is not None and the variable is not set, factory
    is a callable that will set the variable.

    If not set, returns None.
    """
    if name not in _VARS and factory is not None:
        _VARS[name] = factory()
    return _VARS.get(name)
