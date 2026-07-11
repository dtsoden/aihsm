"""Streaming byte redaction for subprocess output.

StreamRedactor scrubs a fixed set of secret byte-strings out of a stream of
chunks, even when a secret straddles two chunks. It holds back a tail buffer
of (longest needle length - 1) bytes between calls to .feed() so a needle
split across a read boundary is still caught once the rest of it arrives;
call .flush() at EOF to release whatever is left.
"""

MASK = b"****"


class StreamRedactor(object):
    def __init__(self, needles):
        # Only keep non-empty needles; an empty needle would match between
        # every byte and mask everything.
        self._needles = [n for n in needles if n]
        if self._needles:
            self._tail_len = max(len(n) for n in self._needles) - 1
        else:
            self._tail_len = 0
        self._buf = b""

    def _redact(self, data):
        for needle in self._needles:
            data = data.replace(needle, MASK)
        return data

    def feed(self, chunk):
        # Redact the whole buffer (previously held tail + new chunk) before
        # deciding what is safe to emit, so a needle split across the old
        # boundary is caught now that the rest of it has arrived.
        self._buf = self._redact(self._buf + chunk)
        if self._tail_len <= 0:
            out, self._buf = self._buf, b""
            return out
        if len(self._buf) <= self._tail_len:
            # Not enough buffered to safely emit anything yet: keep it all
            # in case it is still a prefix of a needle.
            return b""
        emit_len = len(self._buf) - self._tail_len
        out = self._buf[:emit_len]
        self._buf = self._buf[emit_len:]
        return out

    def flush(self):
        out, self._buf = self._buf, b""
        return out
