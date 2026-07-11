from secret_harness.redact import StreamRedactor


def _run(redactor, chunks):
    out = b""
    for chunk in chunks:
        out += redactor.feed(chunk)
    out += redactor.flush()
    return out


def test_feeds_single_chunk_with_needle_inside():
    r = StreamRedactor([b"SECRET"])
    out = _run(r, [b"abcSECRETdef"])
    assert b"****" in out
    assert b"SECRET" not in out


def test_needle_split_across_two_feed_calls():
    r = StreamRedactor([b"SECRET"])
    out = _run(r, [b"abcSEC", b"RETdef"])
    assert b"****" in out
    assert b"SECRET" not in out


def test_multiple_needles_both_redacted():
    r = StreamRedactor([b"FIRSTSECRET", b"SECONDSECRET"])
    out = _run(r, [b"start FIRSTSECRET middle SECONDSECRET end"])
    assert b"FIRSTSECRET" not in out
    assert b"SECONDSECRET" not in out
    assert out.count(b"****") == 2


def test_empty_needle_is_ignored_and_does_not_blow_up():
    r = StreamRedactor([b"", b"SECRET"])
    out = _run(r, [b"abcSECRETdef"])
    assert b"****" in out
    assert b"SECRET" not in out
    # An empty needle must not turn into a mask-everywhere disaster.
    assert out == b"abc****def"


def test_no_needle_present_passes_through_unchanged():
    r = StreamRedactor([b"SECRET"])
    out = _run(r, [b"nothing to see here"])
    assert out == b"nothing to see here"


def test_needle_split_across_many_small_chunks():
    r = StreamRedactor([b"SUPERSECRETVALUE"])
    needle = b"SUPERSECRETVALUE"
    chunks = [needle[i:i + 1] for i in range(len(needle))]
    chunks = [b"pre-"] + chunks + [b"-post"]
    out = _run(r, chunks)
    assert b"****" in out
    assert needle not in out
