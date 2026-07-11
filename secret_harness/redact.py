"""Streaming byte redaction for subprocess output.

StreamRedactor scrubs a fixed set of secret byte-strings out of a stream of
chunks, even when a secret straddles two chunks or when two secrets overlap.

Masking works on the UNION of secret spans, not per-needle text replacement.
For a finalized region it finds every occurrence of every needle, merges all
overlapping or touching match intervals, and emits a single ``****`` for each
merged interval with the literal bytes between intervals copied verbatim. That
way two secrets that overlap positionally (e.g. "AAAmid" and "midBBB" over
"AAAmidBBB") mask the whole covered span and no fragment of either survives.

Between .feed() calls a tail of (max needle length - 1) bytes is held back so a
needle that spans a read boundary is still caught; the finalize cut is also
pulled back to the start of any match that reaches into the held region, so an
overlap straddling the boundary is never split. .flush() masks whatever remains
with no hold-back.
"""

MASK = b"****"


def _match_intervals(data, needles):
    """Return sorted, merged [start, end) intervals covered by any needle."""
    intervals = []
    for needle in needles:
        nlen = len(needle)
        start = data.find(needle)
        while start != -1:
            intervals.append((start, start + nlen))
            start = data.find(needle, start + 1)
    if not intervals:
        return intervals
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        # Merge overlapping or touching intervals (start <= last_end).
        if start <= last_end:
            if end > last_end:
                merged[-1] = (last_start, end)
        else:
            merged.append((start, end))
    return merged


def _mask_union(data, needles):
    """Emit data with every merged match interval replaced by a single MASK."""
    intervals = _match_intervals(data, needles)
    if not intervals:
        return data
    out = []
    pos = 0
    for start, end in intervals:
        out.append(data[pos:start])
        out.append(MASK)
        pos = end
    out.append(data[pos:])
    return b"".join(out)


class StreamRedactor(object):
    def __init__(self, needles):
        # Only keep non-empty needles; an empty needle would match between
        # every byte and mask everything. Order does not matter: masking is
        # over the union of all match spans, so overlapping or nested secrets
        # are handled regardless of the order they were passed in.
        self._needles = [n for n in needles if n]
        if self._needles:
            self._tail_len = max(len(n) for n in self._needles) - 1
        else:
            self._tail_len = 0
        self._buf = b""

    def feed(self, chunk):
        self._buf += chunk
        if self._tail_len <= 0:
            out = _mask_union(self._buf, self._needles)
            self._buf = b""
            return out

        cut = len(self._buf) - self._tail_len
        if cut <= 0:
            # Not enough buffered to finalize anything safely; hold it all.
            return b""

        # Never finalize a region that a match reaches into from the held
        # tail: pull the cut back to the start of the earliest such match so a
        # needle (or an overlap of needles) spanning the boundary stays whole.
        for start, end in _match_intervals(self._buf, self._needles):
            if start < cut < end:
                cut = start
        if cut <= 0:
            return b""

        out = _mask_union(self._buf[:cut], self._needles)
        self._buf = self._buf[cut:]
        return out

    def flush(self):
        out = _mask_union(self._buf, self._needles)
        self._buf = b""
        return out
