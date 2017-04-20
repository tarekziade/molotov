from molotov import *


@global_setup()
def init_test(args):
    set_var('SomeHeader') = '1'
    set_var('endpoint') = 'http://localhost:8080'


@setup()
async def init_worker(worker_num, args):
    headers = {'AnotherHeader': '1', 'SomeHeader': get_var('SomeHeader')}
    return {'headers': headers}


@setup_session()
async def init_session(worker_num, session):
    session.ob = SomeObject(loop=session.loop)


@scenario(100)
async def scenario_one(session):
    async with session.get(get_var('endpoint')) as resp:
        res = await resp.json()
        assert res['result'] == 'OK'
        assert resp.status == 200


@teardown_session()
async def end_session(worker_num, session):
    session.ob.cleanup()


@teardown()
def end_worker(worker_num):
    print("This is the end for %d" % worker_num)


@global_teardown()
def end_test():
    print("This is the end of the test.")
