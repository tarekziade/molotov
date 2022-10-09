""" Molotov-based test.
"""
import molotov
import random


@molotov.scenario()
async def scenario_one(session):
    async with session.get("http://example.com") as resp:
        if random.randint(1, 100) == 5:
            raise AssertionError("Failed")
        assert resp.status == 200
