"""File bytes -> Document. One reader per format; register new readers in READERS.

A reader is `read(data: bytes, kind: FileKind, settings: Settings) -> Document` and works only in
memory (CLAUDE.md, rule 3). Owner of the format readers: track B (ingest).
"""

from collections.abc import Callable, Mapping

from formcompiler.config import Settings
from formcompiler.document import Document
from formcompiler.ingest import office, pdf, raster
from formcompiler.upload import FileKind, UploadError

type Reader = Callable[[bytes, FileKind, Settings], Document]

# Format modules add themselves here, e.g. `READERS[FileKind.PDF] = pdf.read`.
READERS: dict[FileKind, Reader] = {}


def _read_pdf(data: bytes, kind: FileKind, settings: Settings) -> Document:
    """Text layer first; a scanned PDF (no text at all) goes through OCR when it is available."""
    doc = pdf.read(data, kind, settings)
    if any(page.lines for page in doc.pages) or not raster.ocr_available(settings):
        return doc
    return raster.ocr_pdf(data, settings)


READERS[FileKind.PDF] = _read_pdf
READERS.update(dict.fromkeys(office.CONTENT_TYPES, office.read))
READERS[FileKind.PNG] = raster.read
READERS[FileKind.JPEG] = raster.read


def read(
    data: bytes, kind: FileKind, settings: Settings, readers: Mapping[FileKind, Reader] = READERS
) -> Document:
    reader = readers.get(kind)
    if reader is None:
        raise UploadError(
            422, "Nieobsługiwany format", "Ten format pliku nie jest jeszcze obsługiwany."
        )
    return reader(data, kind, settings)
