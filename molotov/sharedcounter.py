import multiprocessing


class SharedCounter(object):
    def __init__(self, name):
        self._val = multiprocessing.Value('i', 0)
        self._name = name

    def __iadd__(self, other):
        self.__add__(other)
        return self

    def __isub__(self, other):
        self.__sub__(other)
        return self

    def __add__(self, other):
        if isinstance(other, int):
            self._incr(other)
        else:
            raise NotImplementedError()

    def __sub__(self, other):
        self.__add__(-other)

    def _incr(self, value=1):
        with self._val.get_lock():
            self._val.value += value

    @property
    def value(self):
        return self._val.value


class SharedCounters(dict):
    def __init__(self, *keys):
        for key in keys:
            self[key] = SharedCounter(key)
