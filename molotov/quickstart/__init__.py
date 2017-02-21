import sys
import shutil
import os
import argparse
from molotov import __version__


_DEFAULTS = {'target_dir': '.'}
_PREFIX = '> '
_HERE = os.path.dirname(__file__)


class ValidationError(Exception):
    pass


def _input(msg):
    return input(msg)


def _prompt(text, validator=None, default=None):
    while True:
        try:
            if default:
                res = _input(_PREFIX + '%s [%s]: ' % (text, default))
            else:
                res(_PREFIX + '%s: ' % text)

            if not res and default:
                res = default

            if validator:
                res = validator(res)

            return res
        except ValidationError as e:
            print(e)


def _yes(x):
    if x.upper() not in ('Y', 'YES', 'N', 'NO'):
        raise ValidationError("Please enter either 'y' or 'n'.")
    return x.upper() in ('Y', 'YES')


def _parser():
    parser = argparse.ArgumentParser(description='Quickstart')
    parser.add_argument('--version', action='store_true', default=False,
                        help='Displays version and exits.')

    return parser


def _copy_file(name, target_dir):
    print("…copying %r in %r" % (name, target_dir))
    target = os.path.join(target_dir, name)
    if os.path.exists(target):
        print("%r already exists. Cowardly stopping here" % target)
        sys.exit(1)
    shutil.copyfile(os.path.join(_HERE, name), target)


def main():
    parser = _parser()
    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    # XXX
    print('**** Molotov Quickstart ****')
    print('')
    print('Answer to a few questions to get started...')
    target_dir = _prompt("Target directory", default='.')
    create_makefile = _prompt("Create Makefile", default='y', validator=_yes)

    print('Generating Molotov test...')
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    if create_makefile:
        _copy_file('Makefile', target_dir)

    _copy_file('loadtest.py', target_dir)
    _copy_file('molotov.json', target_dir)

    print("")
    print("All done. Happy Breaking!")
    print("Go in %r" % target_dir)
    if create_makefile:
        print("Run 'make build' to get started...")
