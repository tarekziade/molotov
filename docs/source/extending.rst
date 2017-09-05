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

    $ molotov --use-extension molotov/tests/example6.py --max-runs 10 --worker 50 -s scenario_two loadtest.py
    **** Molotov v1.4. Happy breaking! ****
    Loading extension 'molotov/tests/example6.py'
    Preparing 50 workers...
    OK
    Average response time 0.00599 | WORKERS: 12
    SUCCESSES: 451 | FAILURES: 49
    *** Bye ***

