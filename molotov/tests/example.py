import json
from molotov import scenario


@scenario(5)
async def scenario_one(session):
    async with session.get('http://127.0.0.1:5000/api') as res:
        data = await res.json()
        assert data['result'] == 'OK', data


@scenario(30)
async def scenario_two(session):
    somedata = json.dumps({'OK': 1})
    async with session.post('http://127.0.0.1:5000/api', data=somedata) as res:
        assert res.status == 200
