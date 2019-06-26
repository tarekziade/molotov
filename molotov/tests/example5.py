"""

This Molotov script demonstrates how to hook events.

"""

import molotov


@molotov.events()
async def print_request(event, **info):
    if event == "sending_request":
        print("=>")


@molotov.events()
async def print_response(event, **info):
    if event == "response_received":
        print("<=")


@molotov.scenario(100)
async def scenario_one(session):
    async with session.get("http://localhost:8080") as resp:
        res = await resp.json()
        assert res["result"] == "OK"
        assert resp.status == 200
