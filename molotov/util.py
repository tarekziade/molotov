from io import StringIO
import traceback
import sys
import functools
import json
import socket
import os
import asyncio
import time
import threading
from urllib.parse import urlparse, urlunparse
from socket import gethostbyname
from aiohttp import ClientSession, __version__


_DNS_CACHE = {}
_STOP = False
_STOP_WHY = []
_TIMER = None
if __version__[0] == "2":
    raise ImportError("Molotov only supports aiohttp 3.x going forward")


def get_timer():
    return _TIMER


def set_timer(value=None):
    global _TIMER
    if value is None:
        value = int(time.time())
    _TIMER = value


def stop(why=None):
    global _STOP
    if why is not None:
        _STOP_WHY.append(why)
    _STOP = True


def stop_reason():
    return _STOP_WHY


def is_stopped():
    return _STOP


def resolve(url):
    parts = urlparse(url)

    if "@" in parts.netloc:
        username, password = parts.username, parts.password
        netloc = parts.netloc.split("@", 1)[1]
    else:
        username, password = None, None
        netloc = parts.netloc

    if ":" in netloc:
        host = netloc.split(":")[0]
    else:
        host = netloc

    port_provided = False
    if not parts.port and parts.scheme == "https":
        port = 443
    elif not parts.port and parts.scheme == "http":
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
    host = resolved if parts.scheme != "https" else host
    netloc = host
    if port_provided:
        netloc += ":%d" % port
    if username is not None:
        if password is not None:
            netloc = "%s:%s@%s" % (username, password, netloc)
        else:
            netloc = "%s@%s" % (username, netloc)

    if port not in (443, 80):
        host += ":%d" % port
        original += ":%d" % port

    new = urlunparse(
        (
            parts.scheme,
            netloc,
            parts.path or "",
            "",
            parts.query or "",
            parts.fragment or "",
        )
    )
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
        except Exception:
            raise OptionError("Can't parse %r" % config)
    else:
        if not os.path.exists(config):
            raise OptionError("Can't find %r" % config)

        with open(config) as f:
            try:
                config = json.loads(f.read())
            except ValueError:
                raise OptionError("Can't parse %r" % config)

    if "molotov" not in config:
        raise OptionError("Bad config -- no molotov key")

    if "tests" not in config["molotov"]:
        raise OptionError("Bad config -- no molotov/tests key")

    if scenario not in config["molotov"]["tests"]:
        raise OptionError("Can't find %r in the config" % scenario)

    _expand_args(args, config["molotov"]["tests"][scenario])


def _run_in_fresh_loop(coro, timeout=30):
    thres = []
    thexc = []

    def run():
        loop = asyncio.new_event_loop()
        try:
            task = loop.create_task(coro(loop=loop))
            thres.append(loop.run_until_complete(task))
        except Exception as e:
            thexc.append(e)
        finally:
            loop.close()

    th = threading.Thread(target=run)
    th.start()
    th.join(timeout=timeout)

    # re-raise a thread exception
    if len(thexc) > 0:
        raise thexc[0]

    return thres[0]


async def _request(
    endpoint, verb="GET", session_options=None, json=False, loop=None, **options
):
    if session_options is None:
        session_options = {}

    async with ClientSession(loop=loop, **session_options) as session:
        meth = getattr(session, verb.lower())
        result = {}
        async with meth(endpoint, **options) as resp:
            if json:
                result["content"] = await resp.json()
            else:
                result["content"] = await resp.text()
            result["status"] = resp.status
            result["headers"] = resp.headers

        return result


def request(endpoint, verb="GET", session_options=None, **options):
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
    req = functools.partial(_request, endpoint, verb, session_options, **options)
    return _run_in_fresh_loop(req)


def json_request(endpoint, verb="GET", session_options=None, **options):
    """Like :func:`molotov.request` but extracts json from the response.
    """
    req = functools.partial(
        _request, endpoint, verb, session_options, json=True, **options
    )
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


# taken from https://stackoverflow.com/a/37211337
def _make_sleep():
    async def sleep(delay, result=None, *, loop=None):
        coro = asyncio.sleep(delay, result=result, loop=loop)
        task = asyncio.ensure_future(coro, loop=loop)
        sleep.tasks.add(task)
        try:
            return await task
        except asyncio.CancelledError:
            return result
        finally:
            sleep.tasks.remove(task)

    sleep.tasks = set()
    sleep.cancel_all = lambda: sum(task.cancel() for task in sleep.tasks)
    return sleep


cancellable_sleep = _make_sleep()


def printable_error(error, tb=None):
    printable = [repr(error)]
    if tb is None:
        tb = sys.exc_info()[2]
    printed = StringIO()
    traceback.print_tb(tb, file=printed)
    printed.seek(0)
    for line in printed.readlines():
        printable.append(line.rstrip("\n"))
    return printable
