Helpers
=======

Molotov provides a few helpers to make it easier to write tests.

Synchronous requests
--------------------

If you need to perform synchronous requests in your setup:

.. autofunction:: molotov.request

.. autofunction:: molotov.json_request


.. code-block:: python

    from molotov import global_setup, json_request


    _TOKEN = {}

    @global_setup(args)
    def _setup():
        _TOKEN['data'] = json_request('http://example.com')['content']

