import unittest
from unittest.mock import patch


class TestStats(unittest.TestCase):

    def test_import_error(self):
        patched = {'aiostatsd.client': None,
                   'aiostatsd': None}

        with patch.dict('sys.modules', patched):
            from molotov.stats import get_statsd_client
            self.assertRaises(ImportError, get_statsd_client)
