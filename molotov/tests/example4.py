import molotov


class SomeObject(object):
    """Does something smart in real lif with the async loop.
    """
    def __init__(self, loop):
        self.loop = loop

    def cleanup(self):
        pass


@molotov.global_setup()
def init_test(args):
    molotov.set_var('SomeHeader', '1')
    molotov.set_var('endpoint', 'http://localhost:8080')


@molotov.setup()
async def init_worker(worker_num, args):
    headers = {'AnotherHeader': '1',
               'SomeHeader': molotov.get_var('SomeHeader')}
    return {'headers': headers}


@molotov.setup_session()
async def init_session(worker_num, session):
    session.ob = SomeObject(loop=session.loop)


@molotov.scenario(100)
async def scenario_one(session):
    endpoint = molotov.get_var('endpoint')
    async with session.get(endpoint) as resp:
        res = await resp.json()
        assert res['result'] == 'OK'
        assert resp.status == 200


@molotov.teardown_session()
async def end_session(worker_num, session):
    session.ob.cleanup()


@molotov.teardown()
def end_worker(worker_num):
    print("This is the end for %d" % worker_num)


@molotov.global_teardown()
def end_test():
    print("This is the end of the test.")
