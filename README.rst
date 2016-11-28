=======
ailoads
=======

Simple asyncio-based tool to write load tests.

**ailoads** provides:

- a `scenario` decorator that can be used
  to turn a function into a load test.
- a **Requests** session wrapper to interact with the
  HTTP application that's been tested
- a simple command-line runner to run the load test


To create a load test you simply have to write
your functions and decorate them.

Here's a full working example ::

    import json
    from ailoads.fmwk import scenario, requests

    @scenario(5)
    def _scenario_one():
        res = requests.get('https://myapp/api').json()
        assert res['result'] == 'OK'

    @scenario(30)
    def _scenario_two():
        somedata = json.dumps({'OK': 1})
        res = requests.post('http://myapp/api', data=somedata)
        assert res.status_code == 200

the **scenario** decorator takes one paramater which is the
weight of the test.

When ailoads runs, it creates some workers and each worker
runs a sequence of functions. To determine which function
should be run for each step, the worker randomly picks one
given their weights.

Runner
======

To run a test, use the **ailoads** runner and point it to
the scenario module with the -s option::

    $ bin/ailoads --help
    usage: ailoads [-h] [--version] [-p] [-v] [-s SCENARII] [-u USERS]
                [-d DURATION]

    Load test.

    optional arguments:
    -h, --help            show this help message and exit
    --version             Displays version and exits.
    -p, --processes       Uses processes instead of threads.
    -v, --verbose         Verbose
    -s SCENARII, --scenarii SCENARII
                            Module with scenarii
    -u USERS, --users USERS
                            Number of users
    -d DURATION, --duration DURATION
                            Duration in seconds
