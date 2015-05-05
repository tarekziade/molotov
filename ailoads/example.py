from ailoads.fmwk import scenario, requests


@scenario(5)
def _scenario_one():
    """Calls Google.
    """
    return requests.get('http://localhost:8000')


@scenario(30)
def _scenario_two():
    """Calls Yahoo.
    """
    return requests.get('http://localhost:8000')
