.. _from-github:

Run from GitHub
===============

To run **molotov** directly from a GitHub repo, add a **molotov.json**
at the top of that repo alongside your molotov tests.

**molotov.json** is a configuration file that contains a list of tests to run.
Each test is defined by a name and the options that will be passed in
the command line to **molotov**.

In the following example, three tests are defined: **test** and **big** and **scenario_two_once**:

.. literalinclude:: ../../molotov.json

Once you have that file on the top of you repository, you can directly run
it using **molotov**, with the **moloslave** command.

Example:

.. code-block:: bash

    $ moloslave https://github.com/tarekziade/molotov test

This will simply run **molotov** with the options from the json file.

As demonstrated in example, there are also two global options you can
use when running the tests:

- **requirements**: points to a Pip requirements file that will be installed prior
  to the test
- **env**: mapping containing environment variables that will be
  set prior to the test
