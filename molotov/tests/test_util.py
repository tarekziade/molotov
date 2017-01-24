import unittest
from molotov.util import resolve


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
