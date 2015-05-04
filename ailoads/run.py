from ailoads.fmwk import scenario, runner, requests


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


if __name__ == '__main__':
    res = runner(1, 10)
    tok, tfailed = 0, 0

    for ok, failed in res:
        tok += ok
        tfailed += failed

    print('')
    print('%d OK, %d failed' % (tok, tfailed))
