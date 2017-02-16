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



