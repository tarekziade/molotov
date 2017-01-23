import json
from molotov import scenario


@scenario(5)
async def scenario_one(session):
    async with session.get('http://localhost:8080/') as res:
        assert res.status == 200


@scenario(30)
async def scenario_two(session):
    somedata = json.dumps({'OK': 1})
    async with session.post('http://localhost:8080', data=somedata) as res:
        assert res.status == 200
