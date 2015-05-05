import os
import sys

from ailoads.fmwk import runner


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
    if os.path.exists('loadtest.py'):
        scenarii_file = 'loadtest'
    else:
        scenarii_file = 'ailoads.example'

    print('Scenarii file is %r' % scenarii_file)
    resolve_name(scenarii_file)

    res = runner(10, 60)
    tok, tfailed = 0, 0

    for ok, failed in res:
        tok += ok
        tfailed += failed

    print('')
    print('%d OK, %d Failed' % (tok, tfailed))


if __name__ == '__main__':
    main()
