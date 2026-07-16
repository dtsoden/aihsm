import math
import re
from collections import Counter
from typing import List, NamedTuple


class Finding(NamedTuple):
    value: str
    rule: str


# Order matters: more specific rules first so their match wins.
_KNOWN = [
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("github-pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("github-token", re.compile(r"gh[posru]_[A-Za-z0-9]{20,}")),
    ("aws-access-key", re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("google-api-key", re.compile(r"AIza[A-Za-z0-9_\-]{35}")),
    ("stripe-key", re.compile(r"(?:sk|rk)_live_[A-Za-z0-9]{20,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")),
    ("pem-private-key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("connection-string", re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s:@/]+:[^\s:@/]+@[^\s/]+")),
]

_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_\-]+")

# Names that mean "the thing after me is a credential". Deliberately specific.
# A bare "auth" was tried and is too broad: it matches authorId, googleSheets-
# OAuth2Api, and every other identifier with "auth" buried in it.
_CREDENTIAL_NAME = (
    r"[A-Za-z0-9_\-]*"
    r"(?:secret|token|passwd|password|pwd|api[_\-]?key|apikey|access[_\-]?key"
    r"|private[_\-]?key|client[_\-]?secret|credential|bearer|session[_\-]?key"
    r"|signature)"
    r"[A-Za-z0-9_\-]*"
)

# Context gate: flag a value because of what it is ASSIGNED TO, not how random
# it looks.
#
# Entropy alone cannot do this job. A camelCase identifier scores 3.5-3.9, a
# hex digest maxes out at 4.0 (hex has only 16 symbols), and a random 16-char
# id lands at 3.6-3.9. They occupy one band, so every threshold either floods
# on ordinary JSON keys or goes blind to real keys. Naming solves what entropy
# cannot: "AWS_SECRET_ACCESS_KEY=" is a credential regardless of its entropy,
# and "convertFieldsToString" is not, regardless of its entropy.
_CONTEXT_RE = re.compile(
    r"(?i)(" + _CREDENTIAL_NAME + r")"
    r"[\"']?\s*[:=]\s*"
    r"[\"']?([A-Za-z0-9+/=_\-]{12,})"
)


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def find_secrets(text) -> List[Finding]:
    """Find secrets by known shape, then by assignment context.

    There is deliberately no general high-entropy catch-all. It was tried and
    removed in 0.2.0: it cannot separate a secret from an identifier, because
    camelCase names, hex digests and random ids all score 3.5-4.0. Every
    setting either blocked ordinary JSON and URLs or missed real keys.

    The trade is explicit. A bare unlabelled secret from a provider with no
    named rule is now missed. In exchange, pasting config, a workflow export,
    or a URL does not block. See "What this does not do" in the README.
    """
    findings = []
    seen = set()
    for rule, pattern in _KNOWN:
        for match in pattern.finditer(text):
            value = match.group(0)
            if value not in seen:
                seen.add(value)
                findings.append(Finding(value, rule))
    for match in _CONTEXT_RE.finditer(text):
        value = match.group(2)
        if value in seen:
            continue
        # Known-pattern findings are authoritative. Skip any candidate holding
        # an already-found secret so KEY=ghp_... is not counted twice.
        if any(known in value for known in seen):
            continue
        seen.add(value)
        findings.append(Finding(value, "credential"))
    return findings
