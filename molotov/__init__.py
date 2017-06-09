try:
    from molotov.api import (scenario, setup, global_setup, teardown,  # NOQA
                             global_teardown, setup_session,           # NOQA
                             teardown_session)                         # NOQA
    from molotov.util import request, json_request                     # NOQA
    from molotov.util import set_var, get_var                          # NOQA
except ImportError:
    pass   # first import

__version__ = '1.2'
