import unittest
import multiprocessing
from molotov.sharedcounter import SharedCounters, SharedCounter


# pre-forked variable
_DATA = SharedCounters("test")


def run_worker(value):
    _DATA["test"] += value
    _DATA["test"] -= value
    _DATA["test"] += value


class TestSharedCounters(unittest.TestCase):
    def test_operators(self):
        c1 = SharedCounter("ok")
        c2 = SharedCounter("ok")
        c1.value = 4
        c2.value = 5
        self.assertTrue(c1 <= c2)
        self.assertTrue(c1 < c2)
        self.assertTrue(c1 >= 2)
        self.assertTrue(c1 > 2)
        self.assertTrue(c1 == 4)
        self.assertTrue(c1 != 5)
        c2.value = 4
        c2 += SharedCounter("ok")
        self.assertTrue(c1 == c2)
        repr(c1)
        str(c1)

        def _t():
            c = SharedCounter("ok")
            c += 6.2

        self.assertRaises(NotImplementedError, _t)

        def _c():
            SharedCounter("ok") != 6.3

        self.assertRaises(TypeError, _c)

    def test_interface(self):
        data = SharedCounters("one", "two")
        self.assertTrue("one" in data)
        self.assertEqual(len(data.keys()), 2)

        for key in data:
            data[key] = 0
            self.assertTrue(data[key], 0)

        for key, value in data.items():
            data[key] = value
            self.assertTrue(data[key], value)

        data.values()
        repr(data)
        str(data)
        self.assertRaises(KeyError, data.__setitem__, "meh", 1)
        self.assertRaises(TypeError, data.__setitem__, "one", "1")

    def test_mapping(self):
        # making sure it works like a defaultdict(int)
        data = SharedCounters("one", "two")
        self.assertTrue(data["one"].value == 0)
        data["one"] += 10
        data["one"] -= 1
        data["two"] = 4
        self.assertTrue(data["one"].value, 9)
        self.assertTrue(data["two"].value, 4)

    def test_multiprocess(self):
        # now let's try with several processes
        pool = multiprocessing.Pool(10)
        try:
            inputs = [1] * 3000
            pool.map(run_worker, inputs)
            self.assertEqual(_DATA["test"].value, 3000)
        finally:
            pool.close()
