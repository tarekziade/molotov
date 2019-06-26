""" Molotov-based test.
"""
import json
from molotov import scenario, setup, global_setup, teardown, global_teardown


# This is the service you want to load test
_API = "http://localhost:8080"


@global_setup()
def test_starts(args):
    """ This functions is called before anything starts.

    Notice that it's not a coroutine.
    """
    pass


@setup()
async def worker_starts(worker_id, args):
    """ This function is called once per worker.

    If it returns a mapping, it will be used with all requests.

    You can add things like Authorization headers for instance,
    by setting a "headers" key.
    """
    headers = {"SomeHeader": "1"}
    return {"headers": headers}


@teardown()
def worker_ends(worker_id):
    """ This functions is called when the worker is done.

    Notice that it's not a coroutine.
    """
    pass


@global_teardown()
def test_ends():
    """ This functions is called when everything is done.

    Notice that it's not a coroutine.
    """
    pass


# each scenario has a weight. Molotov uses it to determine
# how often the scenario is picked.
@scenario(weight=40)
async def scenario_one(session):
    async with session.get(_API) as resp:
        # if Molotov is called with --statsd
        # you will have a statsd client set into the session
        # you can use to add metrics
        if session.statsd:
            session.statsd.incr("BLEH")
        # when you read the body, don't forget to use await
        res = await resp.json()
        assert res["result"] == "OK"
        assert resp.status == 200


# all scenarii are coroutines
@scenario(weight=30)
async def scenario_two(session):
    # a call to one of the session method should be awaited
    # see aiohttp.Client docs for more info on this
    async with session.get(_API) as resp:
        assert resp.status == 200


@scenario(weight=30)
async def scenario_three(session):
    somedata = json.dumps({"OK": 1})
    async with session.post(_API, data=somedata) as resp:
        assert resp.status == 200
