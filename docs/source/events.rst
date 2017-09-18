.. _events:

Events
======

You can register one or several functions to receive events
emited during the load test. You just need to decorate the function
with the :func:`molotov.events` fixture described below:

.. autofunction:: molotov.events

Current supported events and their keyword arguments:

- **sending_request**: session, request
- **response_received**: session, response, request
- **current_workers**: workers
- **scenario_start**: scenario, wid
- **scenario_success**: scenario, wid
- **scenario_failure**: scenario, exception, wid

The framework will gradually get more events triggered from
every step in the load test cycle.

In the example below, all events are printed out:

.. literalinclude:: ../../molotov/tests/example5.py

