"""PDF with a text layer -> Document, using pdfplumber: words with fonts, vector boxes, tables.

Checkboxes are not in the text: they are glyphs of symbol fonts or small vector squares, so both
become CHECKBOX lines here. Dotted leaders stay in the text (heuristics read them as blanks); a
horizontal rule with nothing written on it becomes `____`. A PDF without a text layer comes back
with no lines, and the pipeline answers 422 until the raster reader handles it.
"""

import io
import re
import statistics
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from itertools import count
from typing import Any

import pdfplumber
from pdfplumber.page import Page as PdfPage
from pdfplumber.table import Table
from pdfplumber.utils.exceptions import PdfminerException

from formcompiler.config import Settings
from formcompiler.document import BBox, Document, Line, LineKind, Page
from formcompiler.upload import FileKind, UploadError

# Wingdings/Symbol private-use squares and their Unicode counterparts seen in the samples.
CHECKBOX_GLYPHS = frozenset("❑□☐☒")
BOX = "☐"  # stand-in text for a vector checkbox square
RULE = "____"  # stand-in text for an empty horizontal rule or a row of character boxes
BOLD_HINTS = ("bold", "black", "heavy", "semibold")
LEADER = re.compile(r"[._…]{3,}")
FOOTNOTE = re.compile(r"^(\d+\s?\)|\*)")

ROW_TOLERANCE = 0.5  # words whose middles differ by less than this x font size share a row
COLUMN_GAP = 2.5  # a horizontal gap wider than this x font size starts a new line
HEADING_RATIO = 1.15  # font size this much above the page median makes a heading
HEADING_MAX = 120  # longer lines are prose even in a large font
HEADING_MIN_LETTERS = 3  # a lone section letter ("B") is not a heading
BOX_MIN, BOX_MAX = 5.0, 16.0  # side of a checkbox square, points
RULE_MIN = 40.0  # shortest horizontal rule treated as a blank, points
TOUCH = 2.0  # points within which two vector edges meet


@dataclass
class _Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    bold: bool = False

    @property
    def middle(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class _Item:
    """A line before it gets its id: ids follow the reading order of the whole page."""

    text: str
    kind: LineKind
    bbox: BBox
    size: float = 0.0
    bold: bool = False
    cells: list[str] = field(default_factory=list)
    row_top: float | None = None  # segments of one row keep their left-to-right order

    @property
    def order(self) -> tuple[float, float]:
        return (self.bbox[1] if self.row_top is None else self.row_top, self.bbox[0])

    def line(self, line_id: str) -> Line:
        return Line(id=line_id, text=self.text, kind=self.kind, cells=self.cells, bbox=self.bbox)


def read(data: bytes, kind: FileKind, settings: Settings) -> Document:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > settings.max_pages:
                raise UploadError(
                    413,
                    "Za dużo stron",
                    f"Dokument ma {len(pdf.pages)} stron, a limit to {settings.max_pages}.",
                )
            ids = (f"L{n}" for n in count(1))
            pages = [_page(page, ids) for page in pdf.pages]
    except PdfminerException as exc:
        raise UploadError(
            422,
            "Plik uszkodzony",
            "Nie udało się odczytać pliku PDF. Sprawdź, czy nie jest uszkodzony.",
        ) from exc
    return Document(pages=pages)


def _page(page: PdfPage, ids: Iterator[str]) -> Page:
    words = _words(page)
    if not words:
        return Page(number=page.page_number, width=page.width, height=page.height)
    median = statistics.median(c["size"] for c in page.chars if c["text"].strip())

    words.extend(_boxes(page, words, median))
    tables = [t for t in page.find_tables() if len(t.columns) >= 2]
    items: list[_Item] = []
    for table in tables:
        inside = [w for w in words if _within(w, table.bbox)]
        if _is_comb(table, inside):
            x0, top, x1, bottom = table.bbox
            words = [w for w in words if w not in inside]
            words.append(_Word(RULE, x0, x1, top, bottom, median))
        elif _is_simple(table, inside, words):
            words = [w for w in words if w not in inside]
            items.extend(_table_rows(table))
    words.extend(_rules(page, words, tables, median))

    for row in _group_rows(words):
        row_top = min(w.top for w in row)
        items.extend(replace(_item(s, median), row_top=row_top) for s in _segments(row))
    items = _join_headings(sorted(items, key=lambda i: i.order))
    lines = [item.line(next(ids)) for item in items if item.text]
    return Page(number=page.page_number, width=page.width, height=page.height, lines=lines)


def _words(page: PdfPage) -> list[_Word]:
    raw: list[dict[str, Any]] = page.extract_words(extra_attrs=["fontname", "size"])
    return [
        _Word(
            text=w["text"],
            x0=w["x0"],
            x1=w["x1"],
            top=w["top"],
            bottom=w["bottom"],
            size=w["size"],
            bold=any(hint in w["fontname"].lower() for hint in BOLD_HINTS),
        )
        for w in raw
        if w["text"].strip()
    ]


def _within(word: _Word, bbox: BBox) -> bool:
    x0, top, x1, bottom = bbox
    return x0 <= (word.x0 + word.x1) / 2 <= x1 and top <= word.middle <= bottom


def _is_comb(table: Table, inside: list[_Word]) -> bool:
    """One row of character boxes (PESEL, NIP, account number) is a single blank."""
    return len(table.rows) == 1 and all(len(w.text) <= 1 for w in inside)


def _is_simple(table: Table, inside: list[_Word], words: list[_Word]) -> bool:
    """A grid of one-line cells that owns its band of the page; anything else is read as lines."""
    _, top, _, bottom = table.bbox
    beside = any(w.bottom > top and w.top < bottom for w in words if w not in inside)
    boxes = any(w.text[0] in CHECKBOX_GLYPHS for w in inside)
    rows = table.extract()
    multiline = any("\n" in (cell or "") for row in rows for cell in row)
    columns = any(sum(bool(cell) for cell in row) >= 2 for row in rows)
    return len(rows) >= 2 and columns and not (beside or boxes or multiline)


def _table_rows(table: Table) -> Iterator[_Item]:
    for row, cells in zip(table.rows, table.extract(), strict=True):
        texts = [" ".join(cell.split()) for cell in cells if cell is not None]
        if any(texts):
            yield _Item(" ".join(t for t in texts if t), LineKind.TABLE_ROW, row.bbox, cells=texts)


def _boxes(page: PdfPage, words: list[_Word], median: float) -> list[_Word]:
    """Small standalone vector squares are checkboxes; rows of touching squares are combs."""
    squares = [
        r
        for r in page.rects
        if BOX_MIN <= r["width"] <= BOX_MAX
        and BOX_MIN <= r["height"] <= BOX_MAX
        and abs(r["width"] - r["height"]) <= TOUCH
    ]
    result = []
    for r in squares:
        in_comb = any(
            s is not r
            and abs(s["top"] - r["top"]) <= TOUCH
            and min(abs(s["x0"] - r["x1"]), abs(r["x0"] - s["x1"])) <= TOUCH
            for s in squares
        )
        filled = any(_within(w, (r["x0"], r["top"], r["x1"], r["bottom"])) for w in words)
        if not in_comb and not filled:
            result.append(_Word(BOX, r["x0"], r["x1"], r["top"], r["bottom"], median))
    return result


def _rules(page: PdfPage, words: list[_Word], tables: list[Table], median: float) -> list[_Word]:
    """Horizontal rules with nothing written on them, other than box edges and table borders."""
    segments = [(o["x0"], o["x1"], o["top"], o["bottom"]) for o in page.lines + page.rects]
    vertical = [s for s in segments if s[1] - s[0] <= TOUCH and s[3] - s[2] > TOUCH]
    result = []
    for x0, x1, top, bottom in segments:
        if bottom - top > TOUCH or x1 - x0 < RULE_MIN:
            continue
        if any(t.bbox[1] - TOUCH <= top <= t.bbox[3] + TOUCH for t in tables):
            continue
        box_edge = any(
            min(abs(v[0] - x0), abs(v[0] - x1)) <= TOUCH
            and min(abs(v[2] - top), abs(v[3] - top)) <= TOUCH
            for v in vertical
        )
        written = any(
            w.x1 > x0 and w.x0 < x1 and top - 1.2 * w.size <= w.bottom and w.top <= bottom
            for w in words
        )
        if not (box_edge or written or _above_footnotes(x0, x1, top, words, median)):
            result.append(_Word(RULE, x0, x1, top - median, top, median))
    return result


def _above_footnotes(x0: float, x1: float, top: float, words: list[_Word], median: float) -> bool:
    """The short rule that separates footnotes from the text is not a blank."""
    below = [w for w in words if top < w.top <= top + 2 * median and x0 - TOUCH <= w.x0 < x1]
    if not below:
        return False
    first = min(w.top for w in below)
    row = sorted((w for w in below if w.top - first <= TOUCH), key=lambda w: w.x0)
    return FOOTNOTE.match(" ".join(w.text for w in row)) is not None


def _group_rows(words: list[_Word]) -> list[list[_Word]]:
    rows: list[list[_Word]] = []
    for word in sorted(words, key=lambda w: (w.middle, w.x0)):
        if rows and abs(word.middle - rows[-1][0].middle) <= ROW_TOLERANCE * word.size:
            rows[-1].append(word)
        else:
            rows.append([word])
    return [sorted(row, key=lambda w: w.x0) for row in rows]


def _segments(row: list[_Word]) -> Iterator[list[_Word]]:
    """Split a row at wide gaps (columns, tab stops) and before every checkbox.

    A run of dots or a rule after a gap stays with the label to its left: it is that label's blank.
    """
    segment = [row[0]]
    for word in row[1:]:
        gap = word.x0 - segment[-1].x1
        blank = word.text == RULE or LEADER.fullmatch(word.text) is not None
        if (gap > COLUMN_GAP * word.size and not blank) or word.text[0] in CHECKBOX_GLYPHS:
            yield segment
            segment = [word]
        else:
            segment.append(word)
    yield segment


def _item(words: list[_Word], median: float) -> _Item:
    text = " ".join(w.text for w in words)
    size = min(w.size for w in words)
    bold = all(w.bold for w in words)
    kind = LineKind.TEXT
    if text[0] in CHECKBOX_GLYPHS:
        text = text.lstrip("".join(CHECKBOX_GLYPHS)).strip()
        kind = LineKind.CHECKBOX
    elif _is_heading(text, size, bold, median):
        kind = LineKind.HEADING
    bbox = (
        min(w.x0 for w in words),
        min(w.top for w in words),
        max(w.x1 for w in words),
        max(w.bottom for w in words),
    )
    return _Item(text, kind, bbox, size, bold)


def _is_heading(text: str, size: float, bold: bool, median: float) -> bool:
    letters = sum(c.isalpha() for c in text)
    if len(text) > HEADING_MAX or LEADER.search(text) or letters < HEADING_MIN_LETTERS:
        return False
    return size >= HEADING_RATIO * median or (bold and text.isupper())


def _join_headings(items: list[_Item]) -> list[_Item]:
    """A heading broken over lines becomes one line: same font, next line right below it."""
    result: list[_Item] = []
    for item in items:
        prev = result[-1] if result else None
        if prev is not None and prev.kind is LineKind.HEADING and _continues(prev, item):
            bbox = (
                min(prev.bbox[0], item.bbox[0]),
                prev.bbox[1],
                max(prev.bbox[2], item.bbox[2]),
                item.bbox[3],
            )
            result[-1] = replace(prev, text=f"{prev.text} {item.text}", bbox=bbox)
        else:
            result.append(item)
    return result


def _continues(prev: _Item, item: _Item) -> bool:
    if item.kind not in (LineKind.TEXT, LineKind.HEADING) or LEADER.search(item.text):
        return False
    same_font = abs(item.size - prev.size) <= 0.5 and item.bold == prev.bold
    gap = item.bbox[1] - prev.bbox[3]
    # An upper-case title goes on in upper case, a mixed-case one in lower case or as a heading.
    if prev.text.isupper():
        case = item.text.isupper()
    else:
        case = item.kind is LineKind.HEADING or item.text[:1].islower()
    return same_font and 0 <= gap <= item.size and case
