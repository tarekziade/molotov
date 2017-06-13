from molotov import scenario


_API = 'http://localhost:8080'


@scenario(weight=40)
async def scenario_one(session):
    async with session.get(_API) as resp:
        res = await resp.json()
        assert res['result'] == 'OK'
        assert resp.status == 200


@scenario(weight=60)
async def scenario_two(session):
    async with session.get(_API) as resp:
        assert resp.status == 200
