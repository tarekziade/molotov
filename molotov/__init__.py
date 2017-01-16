try:
    from molotov import patch                       # NOQA
    from molotov.fmwk import scenario, requests     # NOQA
except ImportError:
    pass   # first import

__version__ = '0.1'
