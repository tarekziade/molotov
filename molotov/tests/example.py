from molotov import scenario


@scenario(5)
def scenario_one(session):
    res = session.get('http://localhost:5000/api').json()
    assert res['result'] == 'OK'


@scenario(30)
def scenario_two(session):
    somedata = {'OK': 1}
    res = session.post_json('https://localhost:5000/api', data=somedata)
    assert res.status_code == 200
