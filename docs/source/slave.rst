Run from github
===============

To run **molotov** directly from a github repo, add a **molotov.json**
at the top of that repo alongside your molotov tests.

**molotov.json** is a configuration file that contains a list of tests to run.
Each test is defined by a name and the options that will be passed in
the command line to **molotov**.

In the following example, two tests are defined, **test** and **test-heavy**::

  {
    "molotov": {
      "tests": {
        "test": {"duration": 30,
                 "verbose": true
        },
        "test-heavy": {"duration": 300,
                       "users": 30
        }
      }
    }
  }


Once you have that file on the top of you repository you can directly run
it using **molotov**, with the **moloslave** command.

Example:

.. code-block:: bash

    $ moloslave https://github.com/tarekziade/shavar-loadtests test

This will simply run **molotov** with the options from the json file.

There are also two global options you can use to run the test:

- **requirements**: points a Pip requirements file that will be installed prior
  to the test
- **env**: mapping containing environment variables that will be
  set prior to the test

Example:

.. code-block:: json

    {"molotov": {
       "requirements": "requirements.txt",
       "env": {"SERVER_URL": "http://aserver.net"},
       "tests": {
         "test": {"duration": 30},
         "test-heavy": {"duration": 300, "workers": 10}
       }
     }
    }


