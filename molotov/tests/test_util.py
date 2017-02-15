import unittest
import os
from molotov.util import resolve, expand_options

_HERE = os.path.dirname(__file__)
config = os.path.join(_HERE, '..', '..', 'molotov.json')


class TestUtil(unittest.TestCase):
    def test_resolve(self):

        urls = [('http://localhost:80/blah', 'http://127.0.0.1:80/blah'),
                ('https://localhost', 'https://localhost'),
                ('http://cantfind', 'http://cantfind'),
                ('https://google.com', 'https://google.com'),
                ('http://user:pass@localhost/blah?yeah=1#ok',
                 'http://user:pass@127.0.0.1/blah?yeah=1#ok'),
                ('http://tarek@localhost/blah',
                 'http://tarek@127.0.0.1/blah')]

        for url, wanted in urls:
            changed, original, resolved = resolve(url)
            self.assertEqual(changed, wanted,
                             '%s vs %s' % (original, resolved))

    def test_config(self):
        class Args:
            pass

        args = Args()
        expand_options(config, "test", args)
        self.assertEqual(args.duration, 1)
