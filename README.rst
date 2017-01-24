=======
molotov
=======

**PROTOTYPE, DO NOT USE**

Simple Python 3.5+ based tool to write load tests.

Uses `asyncio <https://docs.python.org/3/library/asyncio.html>`_
and `aiohttp.client <http://aiohttp.readthedocs.io/en/stable/client.html>`_

**molotov** provides:

- a **scenario** decorator that can be used to turn a function into a load test.
- a **aiohttp.client** session to interact with the HTTP application.
- a command line to run the load test.
- an optional curses interface

**motolov** runs each scenario inside a coroutine (==a worker). You can
spawn as many routines as you want to increase concurrency. If your scenarios
just contains network calls, you can spin up a few hundreds workers to
generate some pretty good load.

If you reach a peak and you want more load, **motolov** can also run several
processes, each one running its coroutines separately. For instance if you
run 10 processes and 100 coroutines, that will generate a load of 1000
coroutines spread across 10 separate processes.

Of course, unlike coroutines running in the same process, each forked process
will have its own memory space. If your scenario share some state, you need
to take this into account in your design.


Quickstart
==========

To create a load test, you need to create a Python module with some functions
decorated with the **scenario** decorator.

The function receives a **session** object inherited from **aiohttp.ClientSession**.

Here's a full example ::

    import json
    from molotov import scenario

    @scenario(40)
    async def scenario_one(session):
        with await session.get('https://myapp/api') as resp:
            res = await resp.json()
            assert res['result'] == 'OK'

    @scenario(60)
    async def scenario_two(session):
        somedata = json.dumps({'OK': 1})
        with await session.post('http://myapp/api', data=somedata) as resp:
            assert resp.status_code == 200


When molotov runs, it creates some workers and each worker runs a sequence
of functions. To determine which function should be run for each step, the
worker randomly picks one given their weights.

In our example, **scenario_two** is picked 60% of the time.

To run the script you can use the module name or its path.

In the example below, the script is executed in quiet mode with 50
concurrent users for 60 seconds, and stops on the first failure::

    $ molotov molotov/tests/example.py --statsd -w 50 -d 60 -qx



Runner
======

To run a test, use the **molotov** runner and point it to
the scenario module or path::


    $ bin/molotov --help
    usage: molotov [-h] [--statsd] [--statsd-host STATSD_HOST]
                [--statsd-port STATSD_PORT] [--version] [--debug] [-v]
                [-w WORKERS] [-p PROCESSES] [-d DURATION] [-q] [-x] [-c]
                scenario

    Load test.

    positional arguments:
    scenario              path or module name that contains scenarii

    optional arguments:
    -h, --help            show this help message and exit
    --statsd              Sends metrics to Statsd.
    --statsd-host STATSD_HOST
                            Statsd host.
    --statsd-port STATSD_PORT
                            Statsd port.
    --version             Displays version and exits.
    --debug               Run the event loop in debug mode.
    -v, --verbose         Verbose
    -w WORKERS, --workers WORKERS
                            Number of workers
    -p PROCESSES, --processes PROCESSES
                            Number of processes
    -d DURATION, --duration DURATION
                            Duration in seconds
    -q, --quiet           Quiet
    -x, --exception       Stop on first failure.
    -c, --console         Use simple console for feedback


Running from a git repo
=======================

To run **molotov** directly from a github repo, add a **molotov.json**
at the top of that repo alongside your molotov tests.

**molotov.json** is a configuration file that contains a list of tests to run.
Each test is defined by a name and the options that will be passed in
the command line to **molotov**.

In the following example, two tests are defined, **test** and **test-heavy**::

  {
    "molotov": {
      "tests": {
        "test": {"duration": 30,
                 "verbose": true
        },
        "test-heavy": {"duration": 300,
                       "users": 30
        }
      }
    }
  }


Once you have that file on the top of you repository you can directly run
it using **molotov**, with the **moloslave** command.

Example::

    $ moloslave https://github.com/tarekziade/shavar-loadtests test

This will simply run **molotov** with the options from the json file.

There are also two global options you can use to run the test:

- **requirements**: points a Pip requirements file that will be installed prior
  to the test
- **env**: mapping containing environment variables that will be
  set prior to the test

Example::

    {"molotov": {
       "requirements": "requirements.txt",
       "env": {"SERVER_URL": "http://aserver.net"},
       "tests": {
         "test": {"duration": 30},
         "test-heavy": {"duration": 300, "workers": 10}
       }
     }
    }
