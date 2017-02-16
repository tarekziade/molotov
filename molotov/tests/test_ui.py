import unittest
import time
import os

from molotov.ui import init_screen, quit
from molotov.result import LiveResults


class TestUI(unittest.TestCase):

    def test_init_screen(self):
        results = LiveResults()

        called = []
        pids = [1, 2, 3, os.getpid()]
        running = time.time()

        def get_results(*args):
            called.append(True)
            # give the updater a chance to kick in
            if time.time() - running > 2:
                quit()
            else:
                results.incr_success()
                results.incr_failure()

            return results

        ui = init_screen(pids, get_results)
        ui.run()
        self.assertTrue(len(called) > 1)
