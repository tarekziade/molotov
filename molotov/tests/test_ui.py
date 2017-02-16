import unittest
from molotov.ui import init_screen, quit


class TestUI(unittest.TestCase):

    def test_init_screen(self):
        called = []
        pids = [1, 2, 3]

        def get_results(*args):
            called.append(True)
            quit()

        ui = init_screen(pids, get_results)
        ui.run()
        self.assertEqual(called, [True])
