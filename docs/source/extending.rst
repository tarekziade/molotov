Extending Molotov
=================

Molotov has a **--use-extension** option that can be used to load
one or several arbitrary Python module that contains some fixtures
and/or an event listener.

For example, you can have a module that is displaying the
request time at the end of the run:

.. literalinclude:: ../../molotov/tests/example6.py

When a Molotov test uses this extension, it will display the
average response time of the requests made on the server:

.. code-block:: bash

    $ molotov --use-extension molotov/tests/example6.py --max-runs 10 --worker 50 -s scenario_two loadtest.py
    **** Molotov v1.4. Happy breaking! ****
    Loading extension 'molotov/tests/example6.py'
    Preparing 50 workers...
    OK
    Average response time 0.00599 | WORKERS: 12
    SUCCESSES: 451 | FAILURES: 49
    *** Bye ***

