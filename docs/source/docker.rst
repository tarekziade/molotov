Run in Docker
=============

If your test can :ref:`from-github`, we provide a generic Docker image
in the Docker Hub called **molotov**, that can be used to run your load
test inside Docker.

The Docker image will use Moloslave against a provided repository.
It's configured with two environment variables:

- **TEST_REPO** -- the Git repository (has to be public)
- **TEST_NAME** -- the name of the test to run

Example:

.. code-block:: bash

    docker run -i --rm -e TEST_REPO=https://github.com/loads/molotov -e TEST_NAME=test tarekziade/molotov:latest
