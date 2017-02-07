import json
from molotov import scenario, setup


_API = 'http://localhost:8080'


@setup()
async def init_test(args):
    headers = {'SomeHeader': '1'}
    return {'headers': headers}


@scenario(40)
async def scenario_one(session):
    async with session.get(_API) as resp:
        if session.statsd:
            session.statsd.incr('BLEH')
        res = await resp.json()
        assert res['result'] == 'OK'
        assert resp.status == 200


@scenario(30)
async def scenario_two(session):
    async with session.get(_API) as resp:
        assert resp.status == 200


@scenario(30)
async def scenario_three(session):
    somedata = json.dumps({'OK': 1})
    async with session.post(_API, data=somedata) as resp:
        assert resp.status == 200
