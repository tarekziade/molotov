import molotov


@molotov.events()
async def event(event, **info):
    print(event, info)


@molotov.scenario(100)
async def scenario_one(session):
    async with session.get('http://localhost:8080') as resp:
        res = await resp.json()
        assert res['result'] == 'OK'
        assert resp.status == 200
