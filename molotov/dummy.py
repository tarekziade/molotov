""" Molotov-based test.
"""
import molotov
import random
from time import sleep


@molotov.global_setup()
def starting(args):
    print("This is a dummy load test that runs against example.com")
    print("Some random failures were added on purpose (1%)")
    print("The test will start the Molotov console in 5 secs")
    sleep(5)


@molotov.scenario()
async def scenario_one(session):
    async with session.get("http://example.com") as resp:
        if random.randint(1, 100) == 5:
            raise AssertionError("Failed")
        from base64 import b64encode
        from os import urandom

        for i in range(1000):
            random_bytes = urandom(64)
            token = b64encode(random_bytes).decode("utf-8")

        assert resp.status == 200
