=======
molotov
=======

Simple asyncio-based tool to write load tests.

**molotov** provides:

- a `scenario` decorator that can be used
  to turn a function into a load test.
- a **Requests** session wrapper to interact with the
  HTTP application that's been tested. The session
  is passed to your functions.
- a simple command-line runner to run the load test.


To create a load test you simply have to write
your functions and decorate them.

Here's a full working example ::

    from molotov import scenario

    @scenario(5)
    def scenario_one(session):
        res = session.get('https://myapp/api').json()
        assert res['result'] == 'OK'

    @scenario(30)
    def scenario_two(session):
        somedata = {'OK': 1}
        res = session.post('http://myapp/api', json=somedata)
        assert res.status_code == 200


the **scenario** decorator takes one agument which is the
weight of the test.

When molotov runs, it creates some workers and each worker
runs a sequence of functions. To determine which function
should be run for each step, the worker randomly picks one
given their weights.

The function receives a **session** object which is
a custom Requests Session instance that's tooled for
sending statsd metrics and display info.



Runner
======

To run a test, use the **molotov** runner and point it to
the scenario module or path::

    $ molotov --help
    usage: molotov [-h] [--statsd] [--statsd-host STATSD_HOST]
                [--statsd-port STATSD_PORT] [--version] [-p] [-v] [-u USERS]
                [-d DURATION] [-q] [-x]
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
    -p, --processes       Uses processes instead of threads.
    -v, --verbose         Verbose
    -u USERS, --users USERS
                            Number of users
    -d DURATION, --duration DURATION
                            Duration in seconds
    -q, --quiet           Quiet
    -x, --exception       Stop on first failure.


When the runner is launched with **--statsd**, some requests metrics are sent
through statsd:

- a timer: molotov.{method}.{url}
- a increment: motolov.request

The statsd client in this case is also passed to the scenario as a keyword
so you can add custom statsd calls.

Example::

    @scenario(30)
    def scenario_two(session, statsd=None):
        somedata = {'OK': 1}
        res = session.post('http://myapp/api', json=somedata)
        if statsd is not None:
            stats.incr(res.status_code)


Running from a git repo
=======================

To run **molotov** directly from a github repo, add a **loads.json**
at the top of that repo alongside your molotov tests.

**loads.json** is a configuration file that contains a list of tests to run.
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
it using **molotov**, with the **aislave** command.

Example::

    $ aislave https://github.com/tarekziade/shavar-loadtests test

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
         "test-heavy": {"duration": 300, "users": 10}
       }
     }
    }
