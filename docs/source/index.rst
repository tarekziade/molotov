molotov
=======

Simple Python 3.5+ tool to write load tests.

Based on `asyncio <https://docs.python.org/3/library/asyncio.html>`_,
`aiohttp.client <http://aiohttp.readthedocs.io/en/stable/client.html>`_ and
`Urwid <http://urwid.org/>`_ for its curses console.



Installation
============

Make sure you are using Python 3.5+ with Pip installed, then:

.. code-block:: bash

   $ pip install molotov


If you want to use statsd, you need to install `aiostatsd <https://github.com/scivey/aiostatsd>`_
which requires a g++ complier and installing cystatsd.

Under MacOS X Sierra:

.. code-block:: bash

    $ export MACOSX_DEPLOYMENT_TARGET=10.12
    $ pip install cython
    $ pip install git+https://github.com/tarekziade/cystatsd.git#egg=cystatsd
    $ pip install aiostatsd

On Linux, make sure you have g++ 4.9, then:

.. code-block:: bash

    $ export CXXFLAGS=--std=c++0x
    $ export CXX=g++-4.9
    $ export CC=g++-4.9
    $ pip install cython
    $ pip install git+https://github.com/tarekziade/cystatsd.git#egg=cystatsd
    $ pip install aiostatsd



Quickstart
==========

To create a load test, you need to create a Python module with some functions
decorated with the **scenario** decorator -- those functions needs to be
coroutines.

When executed, the function receives a **session** object inherited
from **aiohttp.ClientSession**.

Molotov also provides 4 decorators to deal with test fixtures:

- **@global_setup()** called once when the test starts, before processes and workers
  are created. Receives the arguments used to start Molotov. The decorated
  function should not be a coroutine.

- **@setup()** called once per worker startup. Receives the worker number and the
  arguments used to start Molotov. The decorated function should be a coroutine.

- **@teardown()** called when a worker is done. Receives the worker id.
  The decorated function should not be a coroutine.

- **@global_teardown()** called when everything is done.
  The decorated function should not be a coroutine.


Here's a full example :

.. literalinclude:: ../../molotov/tests/example.py

When a function is decorated with the :func:`setup` decorator, it will be
called with the command-line arguments and needs to send back a dict.
This dict will be passed to the :class:`ClientSession` class when it's
created. This is useful when you need to set up session-wide options
like Authorization headers, or do whatever you need on startup.

When molotov runs, it creates some workers (coroutines) that will
run scenarii indefinitely until the test is done. A test is done
when the time in seconds provided by **-d** is reached.

Each worker randomly picks one scenario to execute, given their weights.
Once it's finished, it picks the next one, and so on. In our example,
**scenario_two** is picked ~40% of the time.


.. note::

   Check out aiohttp's documentation to understand how to work with
   a session object.

   Link: https://aiohttp.readthedocs.io/en/stable/client.html


To run the load script, you can provide its module name or its path.
In the example below, the script is executed in quiet mode with
10 processes and 200 workers for 60 seconds. It stops on the first failure:


.. code-block:: bash

    $ molotov molotov/tests/example.py -p 10 -w 200 -d 60 -qx


Next steps
==========

Check out the detailed documentation:

.. toctree::
   :maxdepth: 2

   cli
   slave
   design
   tutorial
