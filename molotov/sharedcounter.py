import multiprocessing


class SharedCounter(object):
    """A multi-process compatible counter.
    """

    def __init__(self, name):
        self._val = multiprocessing.Value("i", 0)
        self._name = name

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __ne__(self, other):
        return self.__cmp__(other) != 0

    def __gt__(self, other):
        return self.__cmp__(other) > 0

    def __ge__(self, other):
        return self.__cmp__(other) >= 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __le__(self, other):
        return self.__cmp__(other) <= 0

    def __cmp__(self, other):
        if isinstance(other, SharedCounter):
            other = other.value
        if not isinstance(other, int):
            raise TypeError(other)
        if self._val.value == other:
            return 0
        elif self._val.value > other:
            return 1
        return -1

    def __repr__(self):
        return "<SharedCounter %d>" % self._val.value

    def __iadd__(self, other):
        self.__add__(other)
        return self

    def __isub__(self, other):
        self.__sub__(other)
        return self

    def __add__(self, other):
        with self._val.get_lock():
            if isinstance(other, SharedCounter):
                other = other.value
            if not isinstance(other, int):
                raise NotImplementedError()
            self._val.value += other

    def __sub__(self, other):
        self.__add__(-other)

    @property
    def value(self):
        return self._val.value

    @value.setter
    def value(self, _value):
        with self._val.get_lock():
            if isinstance(_value, SharedCounter):
                _value = _value.value
            if not isinstance(_value, int):
                raise TypeError(_value)
            self._val.value = _value


class SharedCounters(object):
    """Mapping of SharedCounter items.
    """

    def __init__(self, *keys):
        self._counters = {}
        for key in keys:
            self._counters[key] = SharedCounter(key)

    def items(self):
        return self._counters.items()

    def values(self):
        return self._counters.values()

    def __iter__(self):
        return self._counters.__iter__()

    def keys(self):
        return self._counters.keys()

    def __contains__(self, key):
        return key in self._counters

    def __repr__(self):
        return repr(self._counters)

    def __setitem__(self, key, value):
        if key not in self._counters:
            raise KeyError(key)
        self._counters[key].value = value

    def __getitem__(self, key):
        return self._counters[key]
