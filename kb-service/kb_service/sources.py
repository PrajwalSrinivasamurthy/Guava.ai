"""Document sources."""

from pathlib import Path
from typing import Iterator

from kb_service.domain import KnowledgeDocument

_SUFFIXES = {".md", ".txt"}


class DirectoryDocumentSource:
    """Reads every .md and .txt file under a folder. A document's id is its path relative
    to the folder, so moving the folder doesn't change ids but renaming a file does.
    Hidden files and folders and empty files are skipped."""

    def __init__(self, root: Path):
        self._root = Path(root)

    def documents(self) -> Iterator[KnowledgeDocument]:
        if not self._root.is_dir():
            raise FileNotFoundError(f"{self._root} is not a directory")
        for path in sorted(self._root.rglob("*")):
            relative = path.relative_to(self._root)
            if not path.is_file() or path.suffix.lower() not in _SUFFIXES:
                continue
            if any(part.startswith(".") for part in relative.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError as error:
                raise ValueError(f"{path} is not valid UTF-8 text") from error
            if text:
                yield KnowledgeDocument(id=relative.as_posix(), text=text)
