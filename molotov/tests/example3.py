from molotov import scenario, global_setup


@global_setup()
def init_test(args):
    raise Exception("BAM")


@scenario(weight=100)
async def fail(session):
    raise Exception("I am failing")
