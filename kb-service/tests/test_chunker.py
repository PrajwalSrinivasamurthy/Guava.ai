import pytest

from kb_service.chunker import chunk_text


def test_empty_and_blank_text_produce_no_chunks():
    assert chunk_text("", 100, 10) == []
    assert chunk_text("  \n\n  ", 100, 10) == []


def test_short_text_is_a_single_chunk():
    assert chunk_text("One paragraph.", 100, 10) == ["One paragraph."]


def test_breaks_fall_on_paragraph_boundaries():
    text = "\n\n".join(["a" * 40, "b" * 40, "c" * 40])

    chunks = chunk_text(text, 90, 0)

    assert chunks == ["a" * 40 + "\n\n" + "b" * 40, "c" * 40]


def test_overlap_carries_the_last_paragraph_into_the_next_chunk():
    text = "\n\n".join(["a" * 40, "b" * 40, "c" * 40])

    chunks = chunk_text(text, 90, 45)

    assert chunks == ["a" * 40 + "\n\n" + "b" * 40, "b" * 40 + "\n\n" + "c" * 40]


def test_overlap_larger_than_what_fits_is_trimmed():
    text = "\n\n".join(["a" * 40, "b" * 40, "c" * 80])

    chunks = chunk_text(text, 90, 45)

    assert chunks[-1] == "c" * 80


def test_a_long_paragraph_is_split_on_word_boundaries():
    paragraph = " ".join(["word"] * 50)

    chunks = chunk_text(paragraph, 40, 0)

    assert all(len(chunk) <= 40 for chunk in chunks)
    assert " ".join(chunks).split() == paragraph.split()


def test_a_word_longer_than_the_limit_is_cut():
    chunks = chunk_text("x" * 250, 100, 0)

    assert chunks == ["x" * 100, "x" * 100, "x" * 50]


@pytest.mark.parametrize("size,overlap", [(60, 0), (60, 25), (120, 50), (500, 100)])
def test_no_chunk_exceeds_the_limit_and_no_paragraph_is_lost(size, overlap):
    paragraphs = [f"Paragraph {n}: " + "text " * (n * 3) for n in range(1, 15)]

    chunks = chunk_text("\n\n".join(paragraphs), size, overlap)

    assert all(len(chunk) <= size for chunk in chunks)
    joined = "\n\n".join(chunks)
    assert all(paragraph.split()[1] in joined for paragraph in paragraphs)
