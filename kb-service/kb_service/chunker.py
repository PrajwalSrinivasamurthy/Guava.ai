"""Splits a document into passages small enough to embed and search.

Passages break on paragraph boundaries where possible, so a passage reads as a unit.
Consecutive passages share trailing paragraphs (the overlap) so an answer that straddles
a boundary is still found whole. A paragraph longer than the size limit is split on
word boundaries, and a single word longer than the limit is cut.
"""

_JOINER = "\n\n"


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    pieces = [piece for paragraph in _paragraphs(text) for piece in _fit(paragraph, size)]

    chunks: list[str] = []
    current: list[str] = []
    for piece in pieces:
        if current and _length(current + [piece]) > size:
            chunks.append(_JOINER.join(current))
            current = _tail(current, overlap)
            while current and _length(current + [piece]) > size:
                current.pop(0)
        current.append(piece)
    if current:
        chunks.append(_JOINER.join(current))
    return chunks


def _paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in text.split(_JOINER) if paragraph.strip()]


def _fit(paragraph: str, size: int) -> list[str]:
    if len(paragraph) <= size:
        return [paragraph]

    parts: list[str] = []
    line = ""
    for word in paragraph.split():
        while len(word) > size:
            if line:
                parts.append(line)
                line = ""
            parts.append(word[:size])
            word = word[size:]
        candidate = f"{line} {word}" if line else word
        if len(candidate) > size:
            parts.append(line)
            candidate = word
        line = candidate
    if line:
        parts.append(line)
    return parts


def _tail(pieces: list[str], overlap: int) -> list[str]:
    carried: list[str] = []
    for piece in reversed(pieces):
        if _length([piece] + carried) > overlap:
            break
        carried.insert(0, piece)
    return carried


def _length(pieces: list[str]) -> int:
    return len(_JOINER.join(pieces))
