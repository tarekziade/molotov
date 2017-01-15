=======
molotov
=======

Simple asyncio-based tool to write load tests.

**molotov** provides:

- a `scenario` decorator that can be used
  to turn a function into a load test.
- a **Requests** session wrapper to interact with the
  HTTP application that's been tested
- a simple command-line runner to run the load test


To create a load test you simply have to write
your functions and decorate them.

Here's a full working example ::

    import json
    from molotov import scenario, requests

    @scenario(5)
    def scenario_one():
        res = requests.get('https://myapp/api').json()
        assert res['result'] == 'OK'

    @scenario(30)
    def scenario_two():
        somedata = json.dumps({'OK': 1})
        res = requests.post('http://myapp/api', data=somedata)
        assert res.status_code == 200


the **scenario** decorator takes one paramater which is the
weight of the test.

When molotov runs, it creates some workers and each worker
runs a sequence of functions. To determine which function
should be run for each step, the worker randomly picks one
given their weights.

Runner
======

To run a test, use the **molotov** runner and point it to
the scenario module with the -s option::

    $ bin/molotov --help
    usage: molotov [-h] [--version] [-p] [-v] [-s SCENARII] [-u USERS]
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
