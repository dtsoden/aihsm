import argparse
import getpass
import os
import subprocess
import sys
import threading
from pathlib import Path

from secret_harness import log, store
from secret_harness.redact import StreamRedactor

_CHUNK_SIZE = 4096


def _config_dir():
    return Path.home() / ".claude" / "secret-harness"


def cmd_put(args):
    value = getpass.getpass("Value for '{0}' (input hidden): ".format(args.name))
    if not value:
        sys.stderr.write("Aborted: empty value.\n")
        return 1
    store.store_secret(args.name, value, _config_dir())
    log.info("vault put: " + args.name)
    sys.stdout.write("Stored '{0}' in the OS vault.\n".format(args.name))
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
            log.error("vault run error: bad --set format")
            sys.stderr.write("Bad --set '{0}', expected VAR=NAME.\n".format(pair))
            return 1
        secret = store.get_secret(name, _config_dir())
        if secret is None:
            log.error("vault run error: unknown name " + name)
            sys.stderr.write("No vault entry named '{0}'.\n".format(name))
            return 1
        env[var] = secret
        secrets.append(secret)
        names_used.append(name)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        log.error("vault run error: no command given")
        sys.stderr.write("No command given. Usage: vault run --set VAR=NAME -- <command>\n")
        return 1

    log.info("vault run: injected " + ", ".join(sorted(set(names_used))))

    needles = [s.encode("utf-8", "surrogateescape") for s in secrets]

    try:
        proc = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as err:
        log.error("vault run error: cannot run command")
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
    log.info("vault run exit: " + str(rc))
    return rc


def cmd_list(args):
    for name in store.list_names(_config_dir()):
        sys.stdout.write(name + "\n")
    return 0


def cmd_rm(args):
    store.delete_secret(args.name, _config_dir())
    log.info("vault rm: " + args.name)
    sys.stdout.write("Removed '{0}'.\n".format(args.name))
    return 0


_EPILOG = """\
Examples:
  vault put github-token                 store a secret (you are prompted, input hidden)
  vault run --set GH=github-token -- gh api /user
                                         run a command with the secret in its environment
  vault list                             list stored names (never values)
  vault rm github-token                  delete a stored secret

Stored values are never printed. To view a value, open your OS credential
manager (Windows Credential Manager, macOS Keychain, or Linux Secret Service).
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="vault",
        description="Store and use secrets in the operating system's credential vault.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", metavar="{put,run,list,rm}")

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
