from molotov import scenario


@scenario(5)
def _scenario_one(session):
    """Calls Google.
    """
    return session.get('http://localhost:8000')


@scenario(30)
def _scenario_two(session):
    """Calls Yahoo.
    """
    return session.get('http://localhost:8000')
