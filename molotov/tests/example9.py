"""
Molotov scripts can import modules from the same dir
"""
from molotov import scenario
from mylib import get_url


@scenario(weight=1)
async def my_scenario(session):
    async with session.get(get_url()) as resp:
        assert resp.status == 200
