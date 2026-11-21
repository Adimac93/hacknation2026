"""DOC, DOCX, ODS and XLSX -> Document through the Apache Tika sidecar (XHTML, no coordinates).

Tika flattens checkboxes made as list bullets to `·`, so a short paragraph starting with `·` or a
checkbox glyph is a CHECKBOX line. Spreadsheets come back as tables; a row with a single filled
cell or with checkboxes is read as ordinary paragraphs, any other filled row is a TABLE_ROW.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser

import httpx

from formcompiler.config import Settings
from formcompiler.document import Document, Line, LineKind, Page
from formcompiler.ingest.pdf import CHECKBOX_GLYPHS
from formcompiler.upload import FileKind, UploadError

# Tika picks its parser from Content-Type; without one it returns an empty text.
CONTENT_TYPES = {
    FileKind.DOC: "application/msword",
    FileKind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileKind.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    FileKind.ODS: "application/vnd.oasis.opendocument.spreadsheet",
}
MARKERS = CHECKBOX_GLYPHS | {"·"}
CHECKBOX_MAX = 100  # longer bulleted paragraphs are prose, not options
HEADING_MIN_LETTERS = 3
HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
BLOCKS = HEADINGS | {"p", "li"}
CELLS = frozenset({"td", "th"})
BOLD = frozenset({"b", "strong"})
INLINE = BOLD | {"i", "em", "u", "span", "a", "sub", "sup", "s"}
SKIPPED = frozenset({"head", "script", "style"})


def read(data: bytes, kind: FileKind, settings: Settings) -> Document:
    return parse(_tika(data, kind, settings))


def _tika(data: bytes, kind: FileKind, settings: Settings) -> str:
    headers = {
        "Accept": "text/html",
        "Content-Type": CONTENT_TYPES.get(kind, "application/octet-stream"),
    }
    try:
        response = httpx.put(
            f"{settings.tika_url.rstrip('/')}/tika",
            content=data,
            headers=headers,
            timeout=settings.request_timeout_s,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise UploadError(
            422,
            "Dokument nieczytelny",
            "Nie udało się odczytać pliku. Sprawdź, czy nie jest uszkodzony lub zaszyfrowany.",
        ) from exc
    except httpx.HTTPError as exc:
        raise UploadError(
            503,
            "Usługa chwilowo niedostępna",
            "Usługa odczytu plików biurowych nie odpowiada. Spróbuj ponownie za chwilę "
            "albo prześlij formularz jako PDF.",
        ) from exc
    return response.text


@dataclass
class _Block:
    tag: str
    parts: list[str] = field(default_factory=list)
    bold: bool = True  # every piece of text so far was bold

    @property
    def text(self) -> str:
        return "".join(self.parts)


@dataclass
class _Row:
    cells: list[list[_Block | _Row]] = field(default_factory=list)


type _Item = _Block | _Row


class _Parser(HTMLParser):
    """Collects paragraphs and table rows from Tika's XHTML body, in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[_Item] = []
        self.rows: list[_Row] = []
        self.block: _Block | None = None
        self.bold = 0
        self.skip = 0
        self.after_inline = False  # whitespace between two inline runs is a line break

    @property
    def target(self) -> list[_Item]:
        if self.rows and self.rows[-1].cells:
            return self.rows[-1].cells[-1]
        return self.items

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIPPED:
            self.skip += 1
        elif tag in BLOCKS:
            self._flush()
            self.block = _Block(tag)
        elif tag == "tr":
            self._flush()
            self.rows.append(_Row())
        elif tag in CELLS and self.rows:
            self._flush()
            self.rows[-1].cells.append([])
        elif self.block is not None and (tag == "br" or (tag in INLINE and self.after_inline)):
            self.block.parts.append("\n")
        if tag in BOLD:
            self.bold += 1
        self.after_inline = False

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCKS or tag in CELLS:
            self._flush()
        elif tag == "tr" and self.rows:
            self._flush()
            row = self.rows.pop()
            self.target.append(row)
        if tag in BOLD:
            self.bold = max(0, self.bold - 1)
        self.after_inline = tag in INLINE

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        data = data.replace("\r", "").replace("\xa0", " ").replace("\t", " ")
        if not data.strip():
            # Tika's indentation, except that it also separates runs of separate text frames.
            if self.block is not None and not (self.after_inline and "\n" in data):
                self.block.parts.append(" ")
            return
        if self.block is None:
            self.block = _Block("p")
        # Line breaks inside the text are the document's; at its edges they are indentation.
        head = data[: len(data) - len(data.lstrip())]
        lead = "\n" if self.after_inline and "\n" in head else " " if head else ""
        tail = " " if data[-1].isspace() else ""
        self.block.parts.append(lead + data.strip() + tail)
        self.block.bold &= self.bold > 0
        self.after_inline = False

    def _flush(self) -> None:
        if self.block is not None and self.block.text.strip():
            self.target.append(self.block)
        self.block = None


def parse(xhtml: str) -> Document:
    parser = _Parser()
    parser.feed(xhtml)
    parser.close()
    parser._flush()
    lines = [
        line.model_copy(update={"id": f"L{n}"}) for n, line in enumerate(_lines(parser.items), 1)
    ]
    return Document(pages=[Page(number=1, lines=lines)])


def _lines(items: list[_Item]) -> list[Line]:
    result: list[Line] = []
    for item in items:
        if isinstance(item, _Block):
            result.extend(_block_lines(item))
            continue
        cell_lines = [_lines(cell) for cell in item.cells]
        cells = [" ".join(line.text for line in lines) for lines in cell_lines]
        filled = [i for i, text in enumerate(cells) if text]
        boxes = any(line.kind is LineKind.CHECKBOX for lines in cell_lines for line in lines)
        if len(filled) == 1 or boxes:
            result.extend(line for lines in cell_lines for line in lines)
        elif filled:
            cells = cells[: filled[-1] + 1]
            text = " ".join(text for text in cells if text)
            result.append(Line(id="L0", text=text, kind=LineKind.TABLE_ROW, cells=cells))
    return result


def _block_lines(block: _Block) -> list[Line]:
    result = []
    for raw in block.text.split("\n"):
        text = " ".join(raw.split())
        if not text:
            continue
        kind = LineKind.TEXT
        if text[0] in MARKERS and len(text) <= CHECKBOX_MAX:
            text = text.lstrip("".join(MARKERS)).strip()
            kind = LineKind.CHECKBOX
        elif block.tag in HEADINGS or (block.bold and text.isupper() and _letters(text)):
            kind = LineKind.HEADING
        if text:
            result.append(Line(id="L0", text=text, kind=kind))
    return result


def _letters(text: str) -> bool:
    return sum(c.isalpha() for c in text) >= HEADING_MIN_LETTERS
