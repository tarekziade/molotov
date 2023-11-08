"""
Molotov scripts can import modules from the same dir
"""
from mylib import get_url

from molotov import scenario


@scenario(weight=1)
async def my_scenario(session):
    async with session.get(get_url()) as resp:
        assert resp.status == 200
