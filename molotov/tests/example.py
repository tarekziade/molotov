from molotov import scenario


@scenario(5)
def scenario_one(session, statsd=None):
    res = session.get('http://localhost:5000/api').json()
    assert res['result'] == 'OK', res


@scenario(30)
def scenario_two(session, statsd=None):
    somedata = {'OK': 1}
    res = session.post('http://localhost:5000/api', json=somedata)
    assert res.status_code == 200
    if statsd is not None:
        statsd.incr('200')
