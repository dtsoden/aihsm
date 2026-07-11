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
