Helpers
=======

Molotov provides a few helpers to make it easier to write tests.


Global variables
----------------

If you need to use an object in various test fixtures or tests,
you can use the :func:`set_var` and :func:`get_var` functions.

.. autofunction:: molotov.set_var

.. autofunction:: molotov.get_var


Synchronous requests
--------------------

If you need to perform synchronous requests in your setup:

.. autofunction:: molotov.request

.. autofunction:: molotov.json_request


.. code-block:: python

    from molotov import global_setup, json_request, set_var


    @global_setup(args)
    def _setup():
        set_var('token') = json_request('http://example.com')['content']

