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

# A run of characters with no delimiter breaking it up.
_ALNUM_RUN_RE = re.compile(r"[A-Za-z0-9]+")


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def densest_run(value: str) -> str:
    """Return the longest unbroken alphanumeric run inside a candidate.

    Entropy must be judged on this, never on the whole candidate. _TOKEN_RE
    includes "/" and "-", so a URL or file path arrives here glued into one
    string ("com/docs/en/plugin-marketplaces"). Shannon entropy measures
    character diversity, not randomness, and a long path mixing words, digits,
    slashes and dashes scores as high as a real key. Judging the densest run
    instead separates the two: a secret is one dense random run, while paths,
    slugs and UUIDs are short words joined by delimiters.
    """
    runs = _ALNUM_RUN_RE.findall(value)
    return max(runs, key=len) if runs else ""


def find_secrets(text, entropy_threshold=3.5, min_entropy_len=16) -> List[Finding]:
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
        # Known-pattern findings are authoritative. Skip any high-entropy
        # candidate that contains an already-found known secret, so a secret
        # glued to surrounding context (e.g. KEY=secret) is not double-counted.
        if any(known in value for known in seen):
            continue
        candidate = densest_run(value)
        if len(candidate) >= min_entropy_len and shannon_entropy(candidate) >= entropy_threshold:
            seen.add(value)
            findings.append(Finding(value, "high-entropy"))
    return findings
