Fixtures
========

Molotov provides 4 decorators to deal with test fixtures:

- **@global_setup()** called once when the test starts, before processes and workers
  are created. Receives the arguments used to start Molotov. The decorated
  function should not be a coroutine.

- **@setup()** called once per worker startup. Receives the worker number and the
  arguments used to start Molotov. The decorated function should be a coroutine.

- **@teardown()** called when a worker is done. Receives the worker id.
  The decorated function should not be a coroutine.

- **@global_teardown()** called when everything is done.
  The decorated function should not be a coroutine.


When a function is decorated with the :func:`setup` decorator, it will be
called with the worker id and the command-line arguments and needs to send
back a dict.

This dict will be passed to the :class:`ClientSession` class when it's
created. This is useful when you need to set up session-wide options
like Authorization headers, or do whatever you need on startup.

The :func:`global_setup` decorator is useful if you need to set up
some fixtures that are shared by all workers.

