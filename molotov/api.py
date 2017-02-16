import random
import functools
import asyncio


_SCENARIO = []


def get_scenarios():
    return _SCENARIO


def _check_coroutine(func):
    if not asyncio.iscoroutinefunction(func):
        raise TypeError('%s needs to be a coroutine' % str(func))


def scenario(weight):
    def _scenario(func, *args, **kw):
        _check_coroutine(func)
        if weight > 0:
            _SCENARIO.append((weight, func, args, kw))

        @functools.wraps(func)
        def __scenario():
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
            func, args, kw = item[1:]
            return func, args, kw
        upto += weight
    raise Exception('What')


_SETUP = {}


def get_global_setup():
    return _SETUP.get('global_setup')


def get_setup():
    return _SETUP.get('setup')


def _setup(name, coroutine=True):
    def __setup(func, *args, **kw):
        if coroutine:
            _check_coroutine(func)
        if name in _SETUP:
            raise ValueError("You can't have two setup functions")
        _SETUP[name] = func

        @functools.wraps(func)
        def ___setup():
            return func(*args, **kw)

        return ___setup
    return __setup


def setup():
    return _setup('setup')


def global_setup():
    return _setup('global_setup', coroutine=False)
