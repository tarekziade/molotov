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



Quickstart
==========

To create a load test, you need to create a Python module with some functions
decorated with the **scenario** decorator.

When executed, the function receives a **session** object inherited
from **aiohttp.ClientSession**.

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
