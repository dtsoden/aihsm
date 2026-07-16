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


def test_high_entropy_blob_is_caught_when_it_has_credential_context():
    # Replaces the old bare high-entropy catch-all, removed in 0.2.0. The same
    # blob is caught when something names it as a credential.
    blob = "Zx9Qw3Vt7Lp2Rk8Nb4Hs6Md1Gf5Jc0Yy"
    assert any(f.rule == "credential" for f in find_secrets("API_TOKEN=" + blob))


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
    ("api key in query param", "https://api.example.com/v1/t?api_key=9f8Kd2Lm4Xq7Rv1Zt6Yw3Bn5Hj8Pc0Ss"),
    ("aws secret key with slashes", "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
    ("presigned s3 signature", "https://b.s3.amazonaws.com/k?X-Amz-Signature=a9f8e7d6c5b4a3928170f6e5d4c3b2a1908172635445362718293a4b5c6d7e8f"),
]


def test_real_secrets_still_blocked():
    for label, text in SECRETS:
        assert find_secrets(text) != [], "missed secret (%s): %s" % (label, text)


# Documents what 0.2.0 knowingly gives up, so the trade stays visible instead of
# being rediscovered as a surprise. A bare secret with no naming context and no
# known provider prefix is indistinguishable from an opaque id or a hash, so it
# passes. This was chosen over flooding every config and URL paste.
KNOWN_MISSES = [
    ("bare random token, no context", "kD8fH3jQ7pL5xZ2vB6nM4tYrW9gC1sA0"),
    ("bare hex digest, no context", "a9f8e7d6c5b4a3928170f6e5d4c3b2a1908172635445362718293a4b5c6d7e8f"),
    ("bare webhook url, no context", "https://hooks.example.com/services/T7K4blPqR/B9xJ2mNvW/kD8fH3jQ7pL5xZ2vB6nM4tYr"),
]


def test_known_misses_are_still_missed():
    # If one of these starts passing, the trade-off changed. That is fine, but
    # it must be a decision, not an accident.
    for label, text in KNOWN_MISSES:
        assert find_secrets(text) == [], "now caught (%s) - update the docs" % label


def test_uuid_consistent_bare_and_in_url():
    # A UUID is an identifier. It must behave the same either way.
    bare = find_secrets("550e8400-e29b-41d4-a716-446655440000")
    in_url = find_secrets("https://x.example.com/a/550e8400-e29b-41d4-a716-446655440000")
    assert bare == [] and in_url == []


# --- Regression: pasting a config/JSON export must not trip the detector ---
# A real n8n workflow paste produced 13 false positives: camelCase JSON KEYS
# ("googleSheetsOAuth2Api", "convertFieldsToString"), 16-char credential
# reference ids, and 64-char hex version ids. Shannon entropy cannot tell any
# of those from a real key: camelCase words score 3.5-3.9 and hex maxes at 4.0,
# so they share a band. Detection is now context-gated instead.

import os

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "n8n_workflow_shapes.json")


def test_pasting_a_workflow_export_is_not_flagged():
    text = open(FIXTURE, encoding="utf-8").read()
    found = find_secrets(text)
    assert found == [], "false positives on a config paste: %r" % [f.value for f in found]


def test_camelcase_identifiers_are_not_secrets():
    for ident in (
        "googleSheetsOAuth2Api",
        "convertFieldsToString",
        "workflowsFromSameOwner",
        "saveDataSuccessExecution",
        "shareMediaCategory",
        "canBeUsedToMatch",
        "linkedInOAuth2Api",
    ):
        assert find_secrets(ident) == [], "camelCase identifier flagged: %s" % ident


def test_opaque_ids_and_hashes_are_not_secrets():
    for ident in (
        "Fm9v3091Tzckxizi",                                                   # n8n credential ref
        "17363b6a32cc40ea26ed3dd0f00854b82043edc0d4039cb353e240d941515610",   # version id / sha256
        "a1b2c3d4-e5f6-4789-a012-3456789abcde",                              # uuid
    ):
        assert find_secrets(ident) == [], "opaque id flagged: %s" % ident


def test_credentials_are_caught_by_context():
    for text in (
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        '"apiKey": "9f8Kd2Lm4Xq7Rv1Zt6Yw3Bn5Hj8Pc0Ss"',
        "DATABASE_PASSWORD=hunter2CorrectHorseBattery",
        'client_secret: "8xKq2Lm9Rv4Zt7Yw1Bn6Hj3Pc5Ss0Dd"',
        "AUTH_TOKEN=abc123def456ghi789jkl",
    ):
        assert find_secrets(text) != [], "missed credential in context: %s" % text


def test_named_provider_rules_still_catch_bare_pastes():
    for text in (
        "ghp_0000000000111111111122222222223333",
        "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA",
        "AKIAIOSFODNN7EXAMPLE",
        "-----BEGIN RSA PRIVATE KEY-----",
    ):
        assert find_secrets(text) != [], "missed known provider secret: %s" % text
