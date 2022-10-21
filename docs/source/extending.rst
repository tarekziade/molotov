Extending Molotov
=================

Molotov has a **--use-extension** option that can be used to load
one or several arbitrary Python modules that contains some fixtures
or event listeners.

Using extensions is useful when you want to implement a behavior
that can be reused with arbitrary load tests.

In the example below :func:`record_time` is used to calculate the
average response time of the load test:

.. literalinclude:: ../../molotov/tests/example6.py

When a Molotov test uses this extension, the function will collect
execution times and print out the average response time of
all requests made by Molotov:

.. code-block:: bash

    $ molotov --use-extension molotov/tests/example6.py --max-runs 10 loadtest.py -c
    Loading extension '../molotov/tests/example6.py'
    Preparing 1 worker...
    OK
    [W:0] Starting
    [W:0] Setting up session
    [W:0] Running scenarios

    Average response time 16ms
    **** Molotov v2.6. Happy breaking! ****
    SUCCESSES: 10 | FAILURES: 0
    *** Bye ***
