import unittest
import multiprocessing
from molotov.result import LiveResults
from molotov.tests.support import async_test


class LiveResultsTest(unittest.TestCase):

    @async_test
    async def test_live(self, loop):

        # we have results
        live = LiveResults(use_buffer=False)

        def _do_it():
            live.incr_success()
            live.incr_failure()

        # we fork 2 processes
        p1 = multiprocessing.Process(target=_do_it)
        p2 = multiprocessing.Process(target=_do_it)
        p1.start()
        p2.start()
        p1.join()
        p2.join()
        pids = [p1.pid, p2.pid]
        live.update()
        self.assertEqual(live.get_successes(), 2)
        self.assertEqual(live.get_failures(), 2)
        for pid in pids:
            self.assertTrue(live.get_successes(pid) > 0)
            self.assertTrue(live.get_failures(pid) > 0)
