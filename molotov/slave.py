import json
import os
import sys
import argparse
from subprocess import check_call
import tempfile
import shutil
import site
import pkg_resources

from molotov import __version__
from molotov.run import main as run, _parser


def clone_repo(github):
    # XXX security
    check_call("git clone %s ." % github, shell=True)


def create_virtualenv(virtualenv, python):
    # XXX security
    if sys.version_info.minor > 7:
        cmd = "%s -m venv venv" % python
    else:
        cmd = "%s --python %s venv" % (virtualenv, python)

    check_call(cmd, shell=True)


def install_reqs(reqfile):
    check_call("./venv/bin/pip install -r %s" % reqfile, shell=True)


def run_test(**options):
    """Runs a molotov test.
    """
    parser = _parser()
    fields = {}
    cli = []
    for action in parser._actions:
        if action.dest in ("help", "scenario"):
            continue
        op_str = action.option_strings[0]
        fields[action.dest] = op_str, action.const, type(action)

    for key, value in options.items():
        if key in fields:
            opt, const, type_ = fields[key]
            is_count = type_ is argparse._CountAction
            if const or is_count:
                if is_count:
                    cli += [opt] * value
                else:
                    cli.append(opt)
            else:
                cli.append(opt)
                cli.append(str(value))

    cli.append(options.pop("scenario", "loadtest.py"))
    args = parser.parse_args(args=cli)
    print("Running: molotov %s" % " ".join(cli))
    return run(args)


def main():
    """Moloslave clones a git repo and runs a molotov test
    """
    parser = argparse.ArgumentParser(description="Github-based load test")

    parser.add_argument(
        "--version",
        action="store_true",
        default=False,
        help="Displays version and exits.",
    )

    parser.add_argument(
        "--virtualenv", type=str, default="virtualenv", help="Virtualenv executable."
    )

    parser.add_argument(
        "--python", type=str, default=sys.executable, help="Python executable."
    )

    parser.add_argument(
        "--directory", type=str, default=None, help="Directory to run into."
    )

    parser.add_argument(
        "--config",
        type=str,
        default="molotov.json",
        help="Path of the configuration file.",
    )

    parser.add_argument("repo", help="Github repo", type=str, nargs="?")
    parser.add_argument("run", help="Test to run", nargs="?")

    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    if args.directory is None:
        args.directory = tempfile.mkdtemp()
        remove_dir = True
    else:
        remove_dir = False

    curdir = os.getcwd()
    os.chdir(args.directory)
    print("Working directory is %s" % args.directory)
    try:
        clone_repo(args.repo)
        config_file = os.path.join(args.directory, args.config)

        with open(config_file) as f:
            config = json.loads(f.read())

        # creating the virtualenv
        create_virtualenv(args.virtualenv, args.python)

        # install deps
        if "requirements" in config["molotov"]:
            install_reqs(config["molotov"]["requirements"])

        # load deps into sys.path
        pyver = "%d.%d" % (sys.version_info.major, sys.version_info.minor)
        site_pkg = os.path.join(
            args.directory, "venv", "lib", "python" + pyver, "site-packages"
        )
        site.addsitedir(site_pkg)
        pkg_resources.working_set.add_entry(site_pkg)

        # environment
        if "env" in config["molotov"]:
            for key, value in config["molotov"]["env"].items():
                os.environ[key] = value

        run_test(**config["molotov"]["tests"][args.run])
    except Exception:
        os.chdir(curdir)
        if remove_dir:
            shutil.rmtree(args.directory, ignore_errors=True)
        raise
