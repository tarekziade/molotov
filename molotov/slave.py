import json
import os
import sys
import argparse
import subprocess
import tempfile
import shutil
import site
import pkg_resources

from molotov import __version__
from molotov.run import run, _parser


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


def run_test(**options):
    parser = _parser()
    fields = {}
    cli = []

    for action in parser._actions:
        if action.dest in ('help', 'scenario'):
            continue
        op_str = action.option_strings[0]
        fields[action.dest] = op_str, action.const

    for key, value in options.items():
        if key in fields:
            opt, const = fields[key]
            if const:
                cli.append(opt)
            else:
                cli.append(opt)
                cli.append(str(value))

    cli.append(options.pop('scenario', 'loadtest.py'))
    args = parser.parse_args(args=cli)
    print('Running: molotov %s' % ' '.join(cli))
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

    parser.add_argument('repo', help='Github repo', type=str, nargs="?")
    parser.add_argument('run', help='Test to run', nargs="?")

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

        # load deps into sys.path
        pyver = '%d.%d' % (sys.version_info.major, sys.version_info.minor)
        site_pkg = os.path.join(tempdir, 'venv', 'lib', 'python' + pyver,
                                'site-packages')
        site.addsitedir(site_pkg)
        pkg_resources.working_set.add_entry(site_pkg)

        # environment
        if 'env' in config['molotov']:
            for key, value in config['molotov']['env'].items():
                os.environ[key] = value

        run_test(**config['molotov']['tests'][args.run])
    except Exception:
        os.chdir(curdir)
        shutil.rmtree(tempdir, ignore_errors=True)
        raise
