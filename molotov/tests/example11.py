import molotov


@molotov.scenario()
async def test_print(session):
    session.print("Hello")
