import pytest

from kb_service.sources import DirectoryDocumentSource


def _ids(root):
    return [document.id for document in DirectoryDocumentSource(root).documents()]


def test_reads_markdown_and_text_files_with_relative_ids(tmp_path):
    (tmp_path / "a.md").write_text("  First  \n")
    (tmp_path / "guides").mkdir()
    (tmp_path / "guides" / "b.txt").write_text("Second")

    documents = list(DirectoryDocumentSource(tmp_path).documents())

    assert [(d.id, d.text) for d in documents] == [("a.md", "First"), ("guides/b.txt", "Second")]


def test_other_file_types_hidden_paths_and_empty_files_are_skipped(tmp_path):
    (tmp_path / "keep.md").write_text("keep")
    (tmp_path / "notes.pdf").write_text("skip")
    (tmp_path / ".draft.md").write_text("skip")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.md").write_text("skip")
    (tmp_path / "blank.md").write_text("  \n")

    assert _ids(tmp_path) == ["keep.md"]


def test_a_missing_folder_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        _ids(tmp_path / "nope")


def test_a_file_that_is_not_utf8_names_the_file(tmp_path):
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe\x00bad")

    with pytest.raises(ValueError, match="bad.md"):
        _ids(tmp_path)
