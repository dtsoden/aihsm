import argparse
import getpass
import os
import subprocess
import sys
import threading
from pathlib import Path

from aihsm import log, store
from aihsm.redact import StreamRedactor

_CHUNK_SIZE = 4096


def _config_dir():
    return Path.home() / ".claude" / "aihsm"


def cmd_put(args):
    if args.extra:
        sys.stderr.write(
            "Do not pass the secret value on the command line: it would be saved in your\n"
            "shell history and visible to other programs.\n"
            "Run:  aihsm put {0}\n"
            "and you will be prompted to enter the value privately.\n".format(args.name)
        )
        return 1
    value = getpass.getpass(
        "Value for '{0}' (hidden, nothing will show as you type or paste): ".format(args.name)
    )
    if not value:
        sys.stderr.write("Aborted: empty value, nothing was stored.\n")
        return 1
    confirm = getpass.getpass("Enter or paste it once more to confirm: ")
    if value != confirm:
        sys.stderr.write(
            "The two entries did not match. Nothing was stored. Run the command again.\n"
        )
        return 1
    store.store_secret(args.name, value, _config_dir())
    log.info("aihsm put: " + args.name)
    sys.stdout.write(
        "Stored '{0}' in the OS vault ({1} characters).\n".format(args.name, len(value))
    )
    return 0


def _pump(src, redactor, dest):
    """Read fixed-size chunks from src, redact secrets, and write to dest.

    dest is expected to be a binary stream (e.g. sys.stdout.buffer). Flushes
    after every write so output stays live, and flushes the redactor's held
    tail once the source hits EOF.
    """
    try:
        while True:
            chunk = src.read(_CHUNK_SIZE)
            if not chunk:
                break
            dest.write(redactor.feed(chunk))
            dest.flush()
        dest.write(redactor.flush())
        dest.flush()
    finally:
        src.close()


def cmd_run(args):
    env = os.environ.copy()
    secrets = []
    names_used = []
    for pair in args.set:
        var, sep, name = pair.partition("=")
        if not var or not sep or not name:
            log.error("aihsm run error: bad --set format")
            sys.stderr.write("Bad --set '{0}', expected VAR=NAME.\n".format(pair))
            return 1
        secret = store.get_secret(name, _config_dir())
        if secret is None:
            log.error("aihsm run error: unknown name " + name)
            sys.stderr.write("No vault entry named '{0}'.\n".format(name))
            return 1
        env[var] = secret
        secrets.append(secret)
        names_used.append(name)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        log.error("aihsm run error: no command given")
        sys.stderr.write("No command given. Usage: aihsm run --set VAR=NAME -- <command>\n")
        return 1

    log.info("aihsm run: injected " + ", ".join(sorted(set(names_used))))

    needles = [s.encode("utf-8", "surrogateescape") for s in secrets]

    try:
        proc = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as err:
        log.error("aihsm run error: cannot run command")
        sys.stderr.write("Cannot run command: {0}\n".format(err))
        return 1

    stdout_thread = threading.Thread(
        target=_pump,
        args=(proc.stdout, StreamRedactor(needles), sys.stdout.buffer),
    )
    stderr_thread = threading.Thread(
        target=_pump,
        args=(proc.stderr, StreamRedactor(needles), sys.stderr.buffer),
    )
    stdout_thread.start()
    stderr_thread.start()
    stdout_thread.join()
    stderr_thread.join()

    rc = proc.wait()
    log.info("aihsm run exit: " + str(rc))
    return rc


def cmd_list(args):
    for name in store.list_names(_config_dir()):
        sys.stdout.write(name + "\n")
    return 0


def cmd_rm(args):
    store.delete_secret(args.name, _config_dir())
    log.info("aihsm rm: " + args.name)
    sys.stdout.write("Removed '{0}'.\n".format(args.name))
    return 0


_EPILOG = """\
Examples:
  aihsm put github-token                 store a secret (you are prompted, input hidden)
  aihsm run --set GH=github-token -- gh api /user
                                         run a command with the secret in its environment
  aihsm list                             list stored names (never values)
  aihsm rm github-token                  delete a stored secret

Stored values are never printed. To view a value, open your OS credential
manager (Windows Credential Manager, macOS Keychain, or Linux Secret Service).
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="aihsm",
        description="Store and use secrets in the operating system's credential vault.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # -v as well as -V: there is no verbose flag to collide with, and -v is
    # what people reach for first.
    import aihsm

    parser.add_argument(
        "-v",
        "-V",
        "--version",
        action="version",
        version="aihsm " + aihsm.__version__,
        help="Show the installed version and exit.",
    )
    sub = parser.add_subparsers(dest="cmd", metavar="{put,run,list,rm}")

    p_put = sub.add_parser("put", help="Store a secret via a hidden prompt.")
    p_put.add_argument("name")
    p_put.add_argument("extra", nargs="*", help=argparse.SUPPRESS)
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
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0
    if not hasattr(args, "func"):
        # No subcommand given: show the full help instead of a terse error.
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
