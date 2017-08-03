import unittest
import multiprocessing
from molotov.sharedcounter import SharedCounters


# pre-forked variable
_DATA = SharedCounters(*['test'])


def run_worker(value):
    _DATA['test'] += value
    _DATA['test'] -= value
    _DATA['test'] += value


class TestSharedCounters(unittest.TestCase):
    def test_mapping(self):
        # making sure it works like a defaultdict(int)
        data = SharedCounters('one')
        self.assertTrue(data['one'], 0)
        data['one'] += 10
        data['one'] -= 1
        self.assertTrue(data['one'], 9)

    def test_multiprocess(self):
        # now let's try with several processes
        pool = multiprocessing.Pool(10)
        inputs = [1] * 3000
        workers = pool.map_async(run_worker, inputs)
        workers.wait()
        self.assertEqual(_DATA['test'].value, 3000)
