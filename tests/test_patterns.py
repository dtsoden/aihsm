from aihsm.patterns import Finding, find_secrets, shannon_entropy


def test_entropy_of_repeated_char_is_zero():
    assert shannon_entropy("aaaa") == 0.0


def test_detects_github_token():
    text = "here is my token ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    rules = [f.rule for f in find_secrets(text)]
    assert "github-token" in rules


def test_detects_anthropic_key_over_openai():
    text = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA"
    found = find_secrets(text)
    assert any(f.rule == "anthropic-key" for f in found)


def test_detects_aws_access_key():
    assert any(f.rule == "aws-access-key" for f in find_secrets("AKIAIOSFODNN7EXAMPLE"))


def test_detects_pem_block():
    assert any(f.rule == "pem-private-key" for f in find_secrets("-----BEGIN RSA PRIVATE KEY-----"))


def test_high_entropy_catchall():
    # random-looking blob with no known prefix
    blob = "Zx9Qw3Vt7Lp2Rk8Nb4Hs6Md1Gf5Jc0Yy"
    assert any(f.rule == "high-entropy" for f in find_secrets(blob))


def test_plain_english_is_clean():
    assert find_secrets("please add error handling to the auth module") == []


def test_no_duplicate_findings():
    text = "ghp_abcdefghijklmnopqrstuvwxyz0123456789 ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    values = [f.value for f in find_secrets(text)]
    assert len(values) == len(set(values))


def test_known_secret_glued_to_context_not_double_counted():
    found = find_secrets("GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    assert len(found) == 1
    assert found[0].rule == "github-token"


# --- Regression: URL and path pastes must not trip the high-entropy catch-all ---
# Root cause: the token regex includes "/" and "-", so whole URL paths were glued
# into one candidate whose character diversity (not randomness) cleared the bar.

BENIGN = [
    "https://code.claude.com/docs/en/plugin-marketplaces",
    "https://github.com/dtsoden/aihsm/blob/main/aihsm/patterns.py",
    "https://example.com/some/long/path/to/a/resource/page",
    "https://myblog.example.com/2026/07/how-to-debug-entropy-false-positives",
    "C:/Users/DavidSoden/Claude-Secret-Harness/aihsm/patterns.py",
    "https://example.com/api/v1/orders/f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "https://portal.azure.com/#/resource/subscriptions/550e8400-e29b-41d4-a716-446655440000/overview",
    "https://example.com/x/3F2504E0-4F89-11D3-9A0C-0305E82C3301",
    "https://app.example.com/thing?id=123e4567-e89b-12d3-a456-426614174000",
    "550e8400-e29b-41d4-a716-446655440000",
    "https://github.com/dtsoden/aihsm2/releases/tag/v0.1.0",
    "https://s3.console.aws.amazon.com/s3/buckets/MyBucket2/files",
]


def test_benign_urls_and_paths_do_not_trigger():
    for text in BENIGN:
        assert find_secrets(text) == [], "false positive on: %s" % text


SECRETS = [
    # Webhook-shaped URL where the URL itself is the credential. Uses a neutral
    # host on purpose: a literal hooks.slack.com URL trips GitHub push
    # protection even with invented values. The host is irrelevant to the rule,
    # which fires on the dense trailing run.
    ("webhook url, url is the secret", "https://hooks.example.com/services/T7K4blPqR/B9xJ2mNvW/kD8fH3jQ7pL5xZ2vB6nM4tYr"),
    ("presigned s3 signature", "https://b.s3.amazonaws.com/k?X-Amz-Signature=a9f8e7d6c5b4a3928170f6e5d4c3b2a1908172635445362718293a4b5c6d7e8f"),
    ("aws secret key with slashes", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
    ("api key in query param", "https://api.example.com/v1/t?api_key=9f8Kd2Lm4Xq7Rv1Zt6Yw3Bn5Hj8Pc0Ss"),
    ("bare random token", "kD8fH3jQ7pL5xZ2vB6nM4tYrW9gC1sA0"),
    ("bare 64-char hex secret", "a9f8e7d6c5b4a3928170f6e5d4c3b2a1908172635445362718293a4b5c6d7e8f"),
]


def test_real_secrets_still_blocked():
    for label, text in SECRETS:
        assert find_secrets(text) != [], "missed secret (%s): %s" % (label, text)


def test_uuid_consistent_bare_and_in_url():
    # A UUID is an identifier. It must behave the same either way.
    bare = find_secrets("550e8400-e29b-41d4-a716-446655440000")
    in_url = find_secrets("https://x.example.com/a/550e8400-e29b-41d4-a716-446655440000")
    assert bare == [] and in_url == []
