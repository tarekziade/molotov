import random
import functools
import asyncio


_SCENARIO = {}


def get_scenarios():
    scenarios = list(_SCENARIO.items())
    scenarios.sort()
    return [scenario for (name, scenario) in scenarios]


def get_scenario(name):
    return _SCENARIO.get(name)


def _check_coroutine(func):
    if not asyncio.iscoroutinefunction(func):
        raise TypeError("%s needs to be a coroutine" % str(func))


def scenario(weight=1, delay=0.0, name=None):
    """Decorator to register a function as a Molotov test.

    Options:

    - **weight** used by Molotov when the scenarii are randomly picked.
      The functions with the highest values are more likely to be picked.
      Integer, defaults to 1. This value is ignored when the
      *scenario_picker* decorator is used.
    - **delay** once the scenario is done, the worker will sleep
      *delay* seconds. Float, defaults to 0.
      The general --delay argument you can pass to Molotov
      will be summed with this delay.
    - **name** name of the scenario. If not provided, will use the
      function __name___ attribute.

    The decorated function receives an :class:`aiohttp.ClientSession` instance.
    """

    def _scenario(func, *args, **kw):
        _check_coroutine(func)
        if weight > 0:
            sname = name or func.__name__
            data = {
                "name": sname,
                "weight": weight,
                "delay": delay,
                "func": func,
                "args": args,
                "kw": kw,
            }
            _SCENARIO[sname] = data

        @functools.wraps(func)
        def __scenario(*args, **kw):
            return func(*args, **kw)

        return __scenario

    return _scenario


def pick_scenario(worker_id=0, step_id=0):
    custom_picker = get_fixture("scenario_picker")
    if custom_picker is not None:
        name = custom_picker(worker_id, step_id)
        return get_scenario(name)

    scenarios = get_scenarios()
    total = sum(item["weight"] for item in scenarios)
    selection = random.uniform(0, total)
    upto = 0
    for item in scenarios:
        weight = item["weight"]
        if upto + weight > selection:
            return item
        upto += weight


def next_scenario():
    for scenario in get_scenarios():
        yield scenario


def scenario_picker():
    """Called to chose a scenario.

    Arguments received by the decorated function:

    - **worker_id** the worker number
    - **step_id** the loop counter

    The decorated function should return the name
    of the scenario the worker should execute next.

    When used, the weights are ignored.

    *The decorated function should not be a coroutine.*
    """
    return _fixture("scenario_picker", coroutine=False)


_FIXTURES = {}


def get_fixture(name):
    return _FIXTURES.get(name)


def _fixture(name, coroutine=True, multiple=False):
    def __fixture(func, *args, **kw):
        if coroutine:
            _check_coroutine(func)
        if name in _FIXTURES and not multiple:
            raise ValueError("You can't have two %r functions" % name)
        if multiple:
            if name in _FIXTURES:
                _FIXTURES[name].append(func)
            else:
                _FIXTURES[name] = [func]
        else:
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
    This dict will be passed to the :class:`aiohttp.ClientSession` class
    as keywords when it's created.

    This is useful when you need to set up session-wide options
    like Authorization headers, or do whatever you need on startup.

    *The decorated function should be a coroutine.*
    """
    return _fixture("setup")


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
    return _fixture("global_setup", coroutine=False)


def teardown():
    """Called when a worker is done.

    Arguments received by the decorated function:

    - **worker_id** the worker number

    *The decorated function should not be a coroutine.*
    """
    return _fixture("teardown", coroutine=False)


def global_teardown():
    """Called when everything is done.

    *The decorated function should not be a coroutine.*
    """
    return _fixture("global_teardown", coroutine=False)


def setup_session():
    """Called once per worker startup.

    Arguments received by the decorated function:

    - **worker_id** the worker number
    - **session** the :class:`aiohttp.ClientSession` instance created

    The function can attach extra attributes to the session and use
    **session.loop** if needed.

    It's a good place to attache an object that interacts with the event loop,
    so you are sure to use the same one that the session's.


    *The decorated function should be a coroutine.*
    """
    return _fixture("setup_session")


def teardown_session():
    """Called once per worker when the session is closing.

    Arguments received by the decorated function:

    - **worker_id** the worker number
    - **session** the :class:`aiohttp.ClientSession` instance

    *The decorated function should be a coroutine.*
    """
    return _fixture("teardown_session")


def events():
    """Called everytime Molotov sends an event

    Arguments received by the decorated function:

    - **event** Name of the event
    - extra argument(s) specific to the event

    *The decorated function should be a coroutine.*

    *IMPORTANT This function will directly impact the load test performances*
    """
    return _fixture("events", multiple=True)
