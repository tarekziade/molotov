try:
    from molotov.api import (scenario, setup, global_setup, teardown,  # NOQA
                             global_teardown)                          # NOQA
except ImportError:
    pass   # first import

__version__ = '1.0'
