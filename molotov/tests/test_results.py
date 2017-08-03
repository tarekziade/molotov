import unittest
import multiprocessing
from molotov.result import LiveResults
from molotov.tests.support import async_test


class LiveResultsTest(unittest.TestCase):

    @async_test
    async def test_live(self, loop):

        # we have results
        live = LiveResults()

        def _do_it():
            live.incr('OK')
            live.incr('FAILED')

        # we fork 2 processes
        p1 = multiprocessing.Process(target=_do_it)
        p2 = multiprocessing.Process(target=_do_it)
        p1.start()
        p2.start()
        p1.join()
        p2.join()
        self.assertEqual(live.get_successes(), 2)
        self.assertEqual(live.get_failures(), 2)
