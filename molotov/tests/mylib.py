import os

PORT = os.environ.get("TEST_PORT", "8888")


def get_url():
    return "http://localhost:%s" % PORT
