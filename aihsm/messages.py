REPO_URL = "https://github.com/dtsoden/aihsm"


def secret_detected_message(rule, suggested_name):
    return (
        "Secret detected (matched: {rule}).\n"
        "It is now in this transcript, so treat it as compromised.\n\n"
        "Do this:\n"
        "  1. Revoke or rotate it at the provider now.\n"
        "  2. Store the new one:  aihsm put {name}\n"
        "  3. Re-send your message, referring to it by name.\n\n"
        "False alarm? Re-send your message starting with !secret-ok and this\n"
        "exact string will stop being flagged."
    ).format(rule=rule, name=suggested_name)


def guard_failure_message(error_summary, remediation, uninstall_cmd):
    return (
        "aihsm guard could not run, so your message was blocked to\n"
        "protect any credentials it might contain.\n\n"
        "What broke: {err}\n\n"
        "Fix it:\n"
        "  {fix}\n\n"
        "Can't fix it right now? Remove the guard:\n"
        "  {uninstall}\n"
        "  Full uninstall guide: {url}#uninstall"
    ).format(err=error_summary, fix=remediation, uninstall=uninstall_cmd, url=REPO_URL)
