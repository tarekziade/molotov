from molotov import scenario


@scenario(5)
async def scenario_one(session):
    res = await session.get('http://localhost:5000/api')
    res = res.json()
    assert res['result'] == 'OK', res


@scenario(30)
async def scenario_two(session):
    somedata = {'OK': 1}
    res = await session.post('http://localhost:5000/api', json=somedata)
    assert res.status_code == 200
    await session.statsd_incr('200')
