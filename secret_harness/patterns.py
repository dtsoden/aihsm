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


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def find_secrets(text, entropy_threshold=3.5, min_entropy_len=20):
    findings = []
    seen = set()
    for rule, pattern in _KNOWN:
        for match in pattern.finditer(text):
            value = match.group(0)
            if value not in seen:
                seen.add(value)
                findings.append(Finding(value, rule))
    for match in _TOKEN_RE.finditer(text):
        value = match.group(0)
        if value in seen:
            continue
        if len(value) >= min_entropy_len and shannon_entropy(value) >= entropy_threshold:
            seen.add(value)
            findings.append(Finding(value, "high-entropy"))
    return findings
