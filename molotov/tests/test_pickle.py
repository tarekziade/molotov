import pickle
import io

from molotov.runner import Runner
from molotov.tests.support import TestLoop


class MyPickler (pickle._Pickler):
    def save(self, obj):
        try:
            return pickle._Pickler.save(self, obj)
        except Exception:
            print('pickling object {0} of type {1}'.format(obj, type(obj)))
            raise


class TestPickler(TestLoop):
    def test_pickling_runner(self):
        pickled = io.BytesIO()

        args = self.get_args()
        run = Runner(args=args)

        MyPickler(pickled).dump(run)


