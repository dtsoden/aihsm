import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

from secret_harness import store


def _config_dir():
    return Path.home() / ".claude" / "secret-harness"


def cmd_put(args):
    value = getpass.getpass("Value for '{0}' (input hidden): ".format(args.name))
    if not value:
        sys.stderr.write("Aborted: empty value.\n")
        return 1
    store.store_secret(args.name, value, _config_dir())
    sys.stdout.write("Stored '{0}' in the OS vault.\n".format(args.name))
    return 0


def cmd_run(args):
    env = os.environ.copy()
    for pair in args.set:
        var, sep, name = pair.partition("=")
        if not var or not sep or not name:
            sys.stderr.write("Bad --set '{0}', expected VAR=NAME.\n".format(pair))
            return 1
        secret = store.get_secret(name, _config_dir())
        if secret is None:
            sys.stderr.write("No vault entry named '{0}'.\n".format(name))
            return 1
        env[var] = secret
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        sys.stderr.write("No command given. Usage: vault run --set VAR=NAME -- <command>\n")
        return 1
    return subprocess.run(command, env=env).returncode


def cmd_list(args):
    for name in store.list_names(_config_dir()):
        sys.stdout.write(name + "\n")
    return 0


def cmd_rm(args):
    store.delete_secret(args.name, _config_dir())
    sys.stdout.write("Removed '{0}'.\n".format(args.name))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="vault",
        description="Store and use secrets in the OS credential vault.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_put = sub.add_parser("put", help="Store a secret via a hidden prompt.")
    p_put.add_argument("name")
    p_put.set_defaults(func=cmd_put)

    p_run = sub.add_parser("run", help="Inject secrets into a command's env and run it.")
    p_run.add_argument("--set", action="append", default=[], metavar="VAR=NAME")
    p_run.add_argument("command", nargs=argparse.REMAINDER)
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list", help="List stored names (never values).")
    p_list.set_defaults(func=cmd_list)

    p_rm = sub.add_parser("rm", help="Delete a stored secret.")
    p_rm.add_argument("name")
    p_rm.set_defaults(func=cmd_rm)

    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
