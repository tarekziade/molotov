import asyncio
import unittest
import sys
from molotov.slave import main


class TestSlave(unittest.TestCase):
    def test_main(self):
        oldloop = asyncio.get_event_loop()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        saved = list(sys.argv)
        repo = 'https://github.com/loads/molotov'
        run = 'test'
        sys.argv[:] = ['moloslave', repo, run]
        try:
            main()
        finally:
            sys.argv[:] = saved
            asyncio.set_event_loop(oldloop)
