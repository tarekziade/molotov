import json
from molotov import scenario, setup, global_setup, global_teardown, teardown


_API = 'http://localhost:8080'
_HEADERS = {}


# notice that the global setup, global teardown and teardown
# are not a coroutine.
@global_setup()
def init_test(args):
    _HEADERS['SomeHeader'] = '1'


@global_teardown()
def end_test():
    print("This is the end")


@setup()
async def init_worker(worker_num, args):
    headers = {'AnotherHeader': '1'}
    headers.update(_HEADERS)
    return {'headers': headers}


@teardown()
def end_worker(worker_num):
    print("This is the end for %d" % worker_num)


@scenario(weight=40)
async def scenario_one(session):
    async with session.get(_API) as resp:
        if session.statsd:
            session.statsd.incr('BLEH')
        res = await resp.json()
        assert res['result'] == 'OK'
        assert resp.status == 200


@scenario(weight=30)
async def scenario_two(session):
    async with session.get(_API) as resp:
        assert resp.status == 200


@scenario(weight=30)
async def scenario_three(session):
    somedata = json.dumps({'OK': 1})
    async with session.post(_API, data=somedata) as resp:
        assert resp.status == 200
