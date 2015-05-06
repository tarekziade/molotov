import os
import sys
import argparse

from ailoads.fmwk import runner
from ailoads import __version__


def resolve_name(name):
    if len(sys.path) < 1 or sys.path[0] not in ('', os.getcwd()):
        sys.path.insert(0, '')

    if '.' not in name:
        # shortcut
        __import__(name)
        return sys.modules[name]

    parts = name.split('.')
    cursor = len(parts)
    module_name = parts[:cursor]
    ret = ''

    while cursor > 0:
        try:
            ret = __import__('.'.join(module_name))
            break
        except ImportError:
            cursor -= 1
            module_name = parts[:cursor]

    if ret == '':
        raise ImportError(parts[0])

    for part in parts[1:]:
        try:
            ret = getattr(ret, part)
        except AttributeError as exc:
            raise ImportError(exc)

    return ret



def main():
    parser = argparse.ArgumentParser(description='Load test.')

    parser.add_argument('--version', action='store_true', default=False,
                        help='Displays version and exits.')

    parser.add_argument('-p', '--processes', action='store_true',
                        default=False,
                        help='Uses processes instead of threads.')

    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help='Verbose')

    parser.add_argument('-s', '--scenarii', help='Module with scenarii',
                        type=str, default='loadtest')

    parser.add_argument('-u', '--users', help='Number of users',
                        type=int, default=1)

    parser.add_argument('-d', '--duration', help='Duration in seconds',
                        type=int, default=10)

    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    try:
        resolve_name(args.scenarii)
    except ImportError:
        print('Cannot import %r' % args.scenarii)
        sys.exit(1)

    res = runner(args)
    tok, tfailed = 0, 0

    for ok, failed in res:
        tok += ok
        tfailed += failed

    print('')
    print('%d OK, %d Failed' % (tok, tfailed))


if __name__ == '__main__':
    main()
