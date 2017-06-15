import random
import functools
import asyncio


_SCENARIO = []


def get_scenarios():
    return _SCENARIO


def get_scenario(name):
    for scenario in _SCENARIO:
        if scenario[2].__name__ == name:
            return scenario
    return None


def _check_coroutine(func):
    if not asyncio.iscoroutinefunction(func):
        raise TypeError('%s needs to be a coroutine' % str(func))


def scenario(weight=1, delay=0.0):
    """Decorator to register a function as a Molotov test.

    Options:

    - **weight** used by Molotov when the scenarii are randomly picked.
      The functions with the highest values are more likely to be picked.
      Integer, defaults to 1.
    - **delay** once the scenario is done, the worker will sleep
      *delay* seconds. Float, defaults to 0.
      The general --delay argument you can pass to Molotov
      will be summed with this delay.

    The decorated function receives an :class:`aoihttp.ClienSession` instance.
    """
    def _scenario(func, *args, **kw):
        _check_coroutine(func)
        if weight > 0:
            _SCENARIO.append((weight, delay, func, args, kw))

        @functools.wraps(func)
        def __scenario(*args, **kw):
            return func(*args, **kw)
        return __scenario

    return _scenario


def pick_scenario():
    scenarios = get_scenarios()
    total = sum(item[0] for item in scenarios)
    selection = random.uniform(0, total)
    upto = 0
    for item in scenarios:
        weight = item[0]
        if upto + item[0] > selection:
            delay, func, args, kw = item[1:]
            return delay, func, args, kw
        upto += weight


_FIXTURES = {}


def get_fixture(name):
    return _FIXTURES.get(name)


def _fixture(name, coroutine=True):
    def __fixture(func, *args, **kw):
        if coroutine:
            _check_coroutine(func)
        if name in _FIXTURES:
            raise ValueError("You can't have two %r functions" % name)
        _FIXTURES[name] = func

        @functools.wraps(func)
        def ___fixture(*args, **kw):
            return func(*args, **kw)

        return ___fixture
    return __fixture


def setup():
    """Called once per worker startup.

    Arguments received by the decorated function:

    - **worker_id** the worker number
    - **args** arguments used to start Molotov.

    The decorated function can send back a dict.
    This dict will be passed to the :class:`aoihttp.ClientSession` class
    as keywords when it's created.

    This is useful when you need to set up session-wide options
    like Authorization headers, or do whatever you need on startup.

    *The decorated function should be a coroutine.*
    """
    return _fixture('setup')


def global_setup():
    """Called once when the test starts.

    The decorated function is called before processes and workers
    are created.

    Arguments received by the decorated function:

    - **args** arguments used to start Molotov.

    This decorator is useful if you need to set up some fixtures that
    are shared by all workers.

    *The decorated function should not be a coroutine.*
    """
    return _fixture('global_setup', coroutine=False)


def teardown():
    """Called when a worker is done.

    Arguments received by the decorated function:

    - **worker_id** the worker number

    *The decorated function should not be a coroutine.*
    """
    return _fixture('teardown', coroutine=False)


def global_teardown():
    """Called when everythin is done.

    *The decorated function should not be a coroutine.*
    """
    return _fixture('global_teardown', coroutine=False)


def setup_session():
    """Called once per worker startup.

    Arguments received by the decorated function:

    - **worker_id** the worker number
    - **session** the :class:`aoihttp.ClienSession` instance created

    The function can attach extra attributes to the session and use
    **session.loop** if needed.

    It's a good place to attache an object that interacts with the event loop,
    so you are sure to use the same one that the session's.


    *The decorated function should be a coroutine.*
    """
    return _fixture('setup_session')


def teardown_session():
    """Called once per worker when the session is closing.

    Arguments received by the decorated function:

    - **worker_id** the worker number
    - **session** the :class:`aoihttp.ClienSession` instance

    *The decorated function should be a coroutine.*
    """
    return _fixture('teardown_session')
