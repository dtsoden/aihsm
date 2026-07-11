from aihsm.redact import StreamRedactor


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


def test_three_needle_overlap_chain():
    # A chain of three secrets each overlapping the next: the union of spans
    # covers the whole buffer regardless of the order they are supplied.
    text = b"AAAmidYYYbbb"
    orderings = [
        [b"AAAmid", b"midYYY", b"YYYbbb"],
        [b"YYYbbb", b"midYYY", b"AAAmid"],
        [b"midYYY", b"AAAmid", b"YYYbbb"],
    ]
    for needles in orderings:
        r = StreamRedactor(needles)
        out = _run(r, [text])
        assert out == b"****"
        for frag in (b"AAA", b"bbb", b"mid", b"YYY"):
            assert frag not in out
        for needle in needles:
            assert needle not in out

    # Unequal-length chain variant.
    for needles in (
        [b"AAAmi", b"midYY", b"YYYbbb"],
        [b"YYYbbb", b"midYY", b"AAAmi"],
    ):
        r = StreamRedactor(needles)
        out = _run(r, [text])
        assert out == b"****"
        for frag in (b"AAA", b"bbb"):
            assert frag not in out


def test_overlap_split_sweep():
    # Sweep the read boundary through every split index of an overlapping
    # pair; every split point must still collapse to a single mask.
    needles = [b"AAAmid", b"midBBB"]
    text = b"AAAmidBBB"
    for i in range(len(text) + 1):
        r = StreamRedactor(needles)
        out = _run(r, [text[:i], text[i:]])
        assert out == b"****", "leak at split index {0}: {1!r}".format(i, out)
        for frag in (b"AAA", b"BBB", b"mid"):
            assert frag not in out, "fragment {0!r} at split {1}".format(frag, i)


def test_multibyte_needle_split_midcodepoint():
    # Byte-level matching must survive a needle split in the middle of a
    # multi-byte UTF-8 character.
    needle = "clé-SECRET-€".encode("utf-8")
    text = b"before " + needle + b" after"
    # Split inside the multi-byte euro sign near the end of the needle.
    euro = "€".encode("utf-8")
    assert len(euro) > 1
    split_at = text.index(euro) + 1  # mid-codepoint of the euro character
    r = StreamRedactor([needle])
    out = _run(r, [text[:split_at], text[split_at:]])
    assert needle not in out
    assert b"****" in out
    assert out == b"before **** after"


def test_feed_empty_and_flush():
    r = StreamRedactor([b"SECRET"])
    assert r.feed(b"") == b""
    assert r.flush() == b""

    r2 = StreamRedactor([b"SECRET"])
    out = r2.feed(b"just some clean text")
    out += r2.feed(b"")
    out += r2.flush()
    assert out == b"just some clean text"


def test_match_completes_inside_held_tail():
    # Feed the needle's first L-1 bytes (which live entirely in the held
    # tail), then the final byte, then flush: the completed match must mask.
    needle = b"TAILSECRET"
    r = StreamRedactor([needle])
    out = r.feed(needle[:-1])
    out += r.feed(needle[-1:])
    out += r.flush()
    assert out == b"****"
    assert needle not in out


def test_needle_longer_than_buffer():
    needle = b"AVERYLONGSECRETVALUE"
    # Only a prefix of the needle is ever fed: it is not a full match, so it
    # passes through unmasked, and nothing raises.
    r = StreamRedactor([needle])
    prefix = needle[:8]
    out = _run(r, [prefix])
    assert out == prefix

    # The full needle fed across chunks IS a match and gets masked.
    r2 = StreamRedactor([needle])
    out2 = _run(r2, [needle[:5], needle[5:12], needle[12:]])
    assert out2 == b"****"
    assert needle not in out2
