API & Fixtures
==============


To write tests, the only function you need to use is the :func:`scenario` decorator.


.. autofunction:: molotov.scenario


Molotov also provides optional decorators to deal with test fixtures.

The lifecycle of a test is shown in the diagram below, and
test fixtures can be used to run functions at various stages.

.. image:: _static/lifecycle.jpg


.. autofunction:: molotov.global_setup

.. autofunction:: molotov.setup

.. autofunction:: molotov.setup_session

.. autofunction:: molotov.teardown_session

.. autofunction:: molotov.teardown

.. autofunction:: molotov.global_teardown


Here's a full example, in order of calls:

.. literalinclude:: ../../molotov/tests/example4.py

