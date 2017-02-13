import json
import os
import sys
import argparse
import subprocess
import tempfile
import shutil
from collections import namedtuple

from molotov import __version__
from molotov.run import run


def clone_repo(github):
    # XXX security
    subprocess.check_call('git clone %s .' % github, shell=True)


def create_virtualenv(virtualenv, python):
    # XXX security
    subprocess.check_call('%s --python %s venv' % (virtualenv, python),
                          shell=True)


def install_reqs(reqfile):
    subprocess.check_call('./venv/bin/pip install -r %s' % reqfile,
                          shell=True)


_DEFAULTS = {'processes': False, 'verbose': False, 'scenario': 'loadtest.py',
             'workers': 1, 'duration': 10, 'quiet': False,
             'statsd': False, 'console': True, 'debug': False}


def run_test(**options):
    for option, value in _DEFAULTS.items():
        if option not in options:
            options[option] = value

    args = namedtuple('Arguments', options.keys())(**options)
    print('Running molotov with %s' % str(args))
    return run(args)


def main():
    parser = argparse.ArgumentParser(description='Github-based load test')

    parser.add_argument('--version', action='store_true', default=False,
                        help='Displays version and exits.')

    parser.add_argument('--virtualenv', type=str, default='virtualenv',
                        help='Virtualenv executable.')

    parser.add_argument('--python', type=str, default=sys.executable,
                        help='Python executable.')

    parser.add_argument('--config', type=str, default='molotov.json',
                        help='Path of the configuration file.')

    parser.add_argument('repo', help='Github repo', type=str)
    parser.add_argument('run', help='Test to run')

    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    tempdir = tempfile.mkdtemp()
    curdir = os.getcwd()
    os.chdir(tempdir)
    print('Working directory is %s' % tempdir)
    try:
        clone_repo(args.repo)
        config_file = os.path.join(tempdir, args.config)

        with open(config_file) as f:
            config = json.loads(f.read())

        # creating the virtualenv
        create_virtualenv(args.virtualenv, args.python)

        # install deps
        if 'requirements' in config['molotov']:
            install_reqs(config['molotov']['requirements'])

        # environment
        if 'env' in config['molotov']:
            for key, value in config['molotov']['env'].items():
                os.environ[key] = value

        run_test(**config['molotov']['tests'][args.run])
    except Exception:
        os.chdir(curdir)
        shutil.rmtree(tempdir, ignore_errors=True)
        raise


if __name__ == '__main__':
    main()
