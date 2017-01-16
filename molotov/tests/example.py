from molotov import scenario


@scenario(5)
async def scenario_one(session, statsd=None):
    res = await session.get('http://localhost:5000/api')
    res = res.json()
    assert res['result'] == 'OK', res


@scenario(30)
async def scenario_two(session, statsd=None):
    somedata = {'OK': 1}
    res = await session.post('http://localhost:5000/api', json=somedata)
    assert res.status_code == 200
    if statsd is not None:
        statsd.incr('200')
