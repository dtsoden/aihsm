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


def test_needle_that_is_prefix_of_another():
    # "abc123" is a prefix of "abc123xyz". Whichever order the needles come
    # in, the full longer secret and its trailing fragment must both vanish.
    for needles in ([b"abc123", b"abc123xyz"], [b"abc123xyz", b"abc123"]):
        r = StreamRedactor(needles)
        out = _run(r, [b"abc123xyz"])
        assert b"abc123xyz" not in out
        assert b"xyz" not in out
        assert b"abc123" not in out
        assert out == b"****"


def test_needle_that_is_substring_in_middle():
    # "xyz" sits in the middle of "abcxyzdef". The longer secret must win so
    # its surrounding bytes never leak, regardless of needle order.
    for needles in ([b"xyz", b"abcxyzdef"], [b"abcxyzdef", b"xyz"]):
        r = StreamRedactor(needles)
        out = _run(r, [b"abcxyzdef"])
        assert b"abcxyzdef" not in out
        assert b"abc" not in out
        assert b"def" not in out
        assert out == b"****"


def test_overlapping_needles_equal_length():
    # "AAAmid" and "midBBB" overlap on "mid" without either containing the
    # other. The union of their spans covers the whole buffer.
    for needles in ([b"AAAmid", b"midBBB"], [b"midBBB", b"AAAmid"]):
        r = StreamRedactor(needles)
        out = _run(r, [b"AAAmidBBB"])
        assert out == b"****"
        for frag in (b"AAA", b"BBB", b"mid", b"AAAmid", b"midBBB"):
            assert frag not in out


def test_overlapping_needles_unequal_length():
    for needles in ([b"AAAmi", b"midBBB"], [b"midBBB", b"AAAmi"]):
        r = StreamRedactor(needles)
        out = _run(r, [b"AAAmidBBB"])
        assert out == b"****"
        assert b"AAA" not in out
        assert b"BBB" not in out


def test_overlap_split_across_feeds():
    # The overlap region straddles the read boundary; it must still collapse
    # to a single mask with no leftover fragment.
    r = StreamRedactor([b"AAAmid", b"midBBB"])
    out = _run(r, [b"AAAmid", b"BBB"])
    assert out == b"****"
    for frag in (b"AAA", b"BBB", b"mid"):
        assert frag not in out


def test_disjoint_occurrences_each_masked():
    r = StreamRedactor([b"PREFIXaaa", b"PREFIXbbb"])
    out = _run(r, [b"PREFIXaaa PREFIXbbb"])
    assert out == b"**** ****"
    for frag in (b"PREFIX", b"aaa", b"bbb"):
        assert frag not in out


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
