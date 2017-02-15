Step-by-step tutorial
=====================

Load testing a service with Molotov is done by creating a Python
script that contains **scenarii**. A scenario is a somewhat
realistic interaction with the service a client can have.

Before you can do anything, make sure you have Python 3.5+ and
virtualenv.

Let's use **molostart** to get started::

.. code-block:: bash

    $ bin/molostart
    **** Molotov Quickstart ****

    Answer to a few questions to get started...
    > Target directory [.]: /tmp/mytest
    > Create Makefile [y]:
    Generating Molotov test...
    …copying 'Makefile' in '/tmp/mytest'
    …copying 'loadtest.py' in '/tmp/mytest'
    …copying 'molotov.json' in '/tmp/mytest'

    All done. Happy Breaking!
    Go in '/tmp/mytest'
    Run 'make build' to get started...

**molostart** creates a default molotov layout for you.
You can build the test with **make build** it will create
a virtualenv inside the directory with Molotov installed.


.. code-block:: bash

    $ cd /tmp/mytest
    $ make build
    $ source venv/bin/activate
    (venv)

If that worked, you should now have a **molotov** command-line.

    (venv) $ molotov --version
    0.4


Running one scenario
--------------------


Let's open loadtests.py, remove all the examples,
and create our first real load test::

    from molotov import scenario

    @scenario(100)
    async def _test(session):
        async with session.get('https://example.com') as resp:
            assert resp.status == 200, resp.status


Molotov is used by marking some functions with the @scenario decorator.
A scenario needs to be a coroutine and gets a **session** instance that
can be used to query a server.

In our example we query https://example.com and make sure it returns
a 200. Let's run it in console mode for 2 seconds:

.. code-block:: bash

    (loadtest) $ molotov -d 2 -cx loadtests.py
    **** Molotov v0.4. Happy breaking! ****
    [44492] Preparing 1 workers...OK
    SUCCESSES: 1 | FAILURES: 0
    4 OK, 0 Failed

Notice that you can stop the test anytime with Ctrl+C.

The next step is to add more workers with -w. A worker is a coroutine that
will run the scenario concurrently. Let's run the same test with 10 workers:

.. code-block:: bash

    (loadtest) $ molotov -w 10 -d 2 -cx loadtests.py
    **** Molotov v0.4. Happy breaking! ****
    [44543] Preparing 10 workers...OK
    SUCCESSES: 19 | FAILURES: 0
    20 OK, 0 Failed

Molotov can also run several processes in parallel, each one running its
own set of workers. Let's try with 4 processes and 10 workers. Virtually it
means the level of concurrency will be 40:

.. code-block:: bash

    (loadtest) $ molotov -w 10 -p 4 -d 2 -cx loadtests.py
    **** Molotov v0.4. Happy breaking! ****
    Forking 4 processes
    [44553] Preparing 10 workers...OK
    [44554] Preparing 10 workers...OK
    [44555] Preparing 10 workers...OK
    [44556] Preparing 10 workers...OK
    SUCCESSES: 78 | FAILURES: 0
    80 OK, 0 Failed

You can usually raise the number of workers to a few hundreds, and the
number of processes to a few dozens. Depending how fast the server
responds, Molotov can reach several thousands requests per second.


Adding more scenarii
--------------------


You can add more scenarii and adapt their weights::

    from molotov import scenario

    @scenario(20)
    async def _test(session):
        async with session.get('https://example.com') as resp:
            assert resp.status == 200, resp.status

    @scenario(20)
    async def _test2(session):
        # do something

    @scenario(60)
    async def _test3(session):
        # do something different


The weights (20/20/60) define how often a scenario is executed by a worker.
These weights does not have to be a sum of 100. Molotov will simply use
this formula to determine how often a scenario is used::

    scenario_weigth / sum(scenario weights)

Run from github
---------------

XXX


Next steps
----------

Load testing a service from your laptop is often not enough. The next
step is to run a distributed load test using your script.

The simplest way to do it is to create a Docker image that automatically
runs molotov and orchestrate a distributed load with Loads.

XXX

