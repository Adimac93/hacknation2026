"""PNG and JPEG images, and PDF pages without a text layer -> Document through OCR (D5).

RapidOCR with the PP-OCRv6 small models reads each page, always with `use_cls=False`: the
orientation classifier it ships flips random lines and raised CER from 1.8% to 16%
(research/01). Tesseract 5 `pol` re-reads a page when RapidOCR is unsure or unavailable. The image
never touches the disk: Tesseract gets the page as PNG on stdin and answers on stdout, and model
paths are always explicit, so RapidOCR never downloads anything.

Tall images are several A4 pages stacked vertically; they are cut into pages first, because OCR of
the whole strip returns noise. OCR loses dot leaders and most checkboxes, so a line is CHECKBOX only
when the engine returned a box glyph.
"""

import difflib
import itertools
import logging
import math
import os
import re
import shutil
import statistics
import subprocess
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
import pypdfium2 as pdfium  # type: ignore[import-untyped]
from numpy.typing import NDArray

from formcompiler.config import Settings
from formcompiler.document import Document, Line, LineKind, Page
from formcompiler.upload import FileKind, UploadError, too_large, unsupported

if TYPE_CHECKING:
    from rapidocr import RapidOCR

log = logging.getLogger(__name__)

type Gray = NDArray[np.uint8]

DET_MODEL = "PP-OCRv6_det_small.onnx"
REC_MODEL = "PP-OCRv6_rec_small.onnx"
PDF_DPI = 200
POINTS_PER_INCH = 72

# Page splitting, research/01 question 4.
INK = 128  # grey level below which a pixel is ink
SEARCH = 0.15  # how far from the nominal cut to look for a blank band, as a share of page height
EXACT = 0.02  # a height within 2% of n pages is cut at k·H/n
OVERLAP = 128  # rows two pages share when there is no blank band to cut in
MARGIN = 8  # rows of slack around a cut, so a line on the cut is never dropped by both pages

JOIN_GAP = 2.0  # boxes on one row closer than this many row heights are one line
HEADING_RATIO = 1.25  # a heading is this much taller than the page's median line
BOX_GLYPHS = frozenset("□■☐☑☒❏❐❑❒▢◻◼")
SAME_LINE = 0.85  # text similarity above which two lines in an overlap are the same line
TESSERACT_TIMEOUT_S = 60


@dataclass(frozen=True)
class Slice:
    """Rows [top, bottom) of the image read as one page.

    The page owns the lines whose centre lies in [keep_top, keep_bottom); outside that band the
    rows only give context to a line cut in half by an overlapping cut.
    """

    top: int
    bottom: int
    keep_top: int
    keep_bottom: int


@dataclass(frozen=True)
class PageImage:
    pixels: Gray
    keep: tuple[int, int] | None = None  # owned rows of this image, as in Slice


@dataclass(frozen=True)
class _Box:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    score: float

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def read(data: bytes, kind: FileKind, settings: Settings) -> Document:
    image = decode(data)
    slices = split_pages(image)
    check_pages(len(slices), settings)
    return ocr_pages(
        (
            PageImage(image[s.top : s.bottom], (s.keep_top - s.top, s.keep_bottom - s.top))
            for s in slices
        ),
        settings,
    )


def ocr_pdf(data: bytes, settings: Settings) -> Document:
    """OCR every page of a PDF without a text layer, rendered at 200 DPI; bboxes in PDF points."""
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise unsupported("Plik PDF jest uszkodzony albo zaszyfrowany.") from exc
    try:
        check_pages(len(pdf), settings)
        return ocr_pages(_render(pdf), settings, scale=POINTS_PER_INCH / PDF_DPI)
    finally:
        pdf.close()


def _render(pdf: pdfium.PdfDocument) -> Iterator[PageImage]:
    """Render pages one by one, so only one page bitmap is held in memory at a time."""
    for index in range(len(pdf)):
        page = pdf[index]
        bitmap = page.render(scale=PDF_DPI / POINTS_PER_INCH, grayscale=True)
        pixels: Gray = np.ascontiguousarray(bitmap.to_numpy().reshape(bitmap.height, bitmap.width))
        yield PageImage(pixels)


def decode(data: bytes) -> Gray:
    try:
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    except cv2.error as exc:
        raise unsupported("Plik obrazu jest uszkodzony.") from exc
    if image is None or image.size == 0:
        raise unsupported("Plik obrazu jest uszkodzony.")
    return np.asarray(image, dtype=np.uint8)


def check_pages(count: int, settings: Settings) -> None:
    if count > settings.max_pages:
        raise too_large(f"Dokument ma za dużo stron (limit {settings.max_pages}).")


def split_pages(image: Gray) -> list[Slice]:
    """Cut a strip of stacked pages into A4 pages, preferring blank bands between them."""
    height, width = image.shape
    page = round(width * math.sqrt(2))
    blank = (image < INK).sum(axis=1) <= width // 400
    count = round(height / page)
    exact = count >= 2 and abs(height - count * page) <= EXACT * page

    cuts: list[tuple[int, bool]] = []  # (row, cut through a blank band)
    start = 0
    for k in itertools.count(1):
        if height - start <= page * (1 + SEARCH):
            break
        nominal = round(k * height / count) if exact else start + page
        band = _blank_band(blank, nominal, round(SEARCH * page))
        cuts.append((nominal, False) if band is None else (band, True))
        start = cuts[-1][0]

    half = OVERLAP // 2
    bounds = [(0, True), *cuts, (height, True)]
    return [
        Slice(
            top=a if a_blank else max(0, a - half),
            bottom=b if b_blank else min(height, b + half),
            keep_top=a,
            keep_bottom=b,
        )
        for (a, a_blank), (b, b_blank) in itertools.pairwise(bounds)
    ]


def _blank_band(blank: NDArray[np.bool_], nominal: int, radius: int) -> int | None:
    """Middle of the widest run of blank rows within `radius` of `nominal` (closest on ties)."""
    if blank[nominal]:
        return nominal
    lo, hi = max(0, nominal - radius), min(len(blank), nominal + radius + 1)
    best: tuple[int, int] | None = None  # (width, -distance)
    best_row = None
    for is_blank, run in itertools.groupby(range(lo, hi), key=lambda y: bool(blank[y])):
        rows = list(run)
        if not is_blank:
            continue
        middle = (rows[0] + rows[-1]) // 2
        key = (len(rows), -abs(middle - nominal))
        if best is None or key > best:
            best, best_row = key, middle
    return best_row


def ocr_pages(pages: Iterable[PageImage], settings: Settings, scale: float = 1.0) -> Document:
    """OCR page images into a Document; `scale` converts pixels into the Document's units."""
    ids = itertools.count(1)
    out: list[Page] = []
    tail: list[str] = []  # lines the previous page kept next to its bottom cut
    for number, page in enumerate(pages, 1):
        boxes = _read_page(page.pixels, settings)
        if page.keep is not None:
            boxes, tail = _own(boxes, page.keep, tail)
        height, width = page.pixels.shape
        out.append(
            Page(
                number=number,
                width=width * scale,
                height=height * scale,
                lines=_assemble(boxes, ids, scale),
            )
        )
    return Document(pages=out)


def _own(boxes: list[_Box], keep: tuple[int, int], tail: list[str]) -> tuple[list[_Box], list[str]]:
    """Keep the boxes this page owns and drop the ones the previous page already kept."""
    top, bottom = keep
    owned = [b for b in boxes if top - MARGIN <= b.cy < bottom + MARGIN]
    owned = [b for b in owned if not (b.cy < top + MARGIN and _seen(b.text, tail))]
    return owned, [b.text for b in owned if b.cy >= bottom - MARGIN]


def _seen(text: str, previous: list[str]) -> bool:
    return any(difflib.SequenceMatcher(None, text, p).ratio() >= SAME_LINE for p in previous)


def _read_page(pixels: Gray, settings: Settings) -> list[_Box]:
    boxes: list[_Box] | None = None
    engine = _rapidocr(settings.ocr_model_dir)
    if engine is not None:
        try:
            boxes = _rapidocr_boxes(engine, pixels)
        except Exception as exc:  # any engine failure falls back to Tesseract
            log.warning("RapidOCR failed on a page: %s", type(exc).__name__)
    if boxes is not None and (not boxes or confidence(boxes) >= settings.ocr_min_confidence):
        return boxes
    fallback = _tesseract_boxes(pixels, settings.tessdata_dir)
    if fallback is not None:
        return fallback
    if boxes is not None:
        return boxes
    raise UploadError(
        503, "OCR niedostępny", "Nie udało się odczytać tekstu z obrazu. Spróbuj ponownie później."
    )


def confidence(boxes: list[_Box]) -> float:
    """Mean score weighted by text length."""
    total = sum(len(b.text) for b in boxes)
    return sum(b.score * len(b.text) for b in boxes) / total if total else 0.0


@cache
def _rapidocr(model_dir: Path | None) -> RapidOCR | None:
    try:
        import rapidocr
    except ImportError:
        log.warning("rapidocr is not installed")
        return None
    root = model_dir or Path(rapidocr.__file__).parent / "models"
    det, rec = root / DET_MODEL, root / REC_MODEL
    if not (det.is_file() and rec.is_file()):
        log.warning("RapidOCR weights missing in %s", root)
        return None
    return rapidocr.RapidOCR(
        params={
            "Global.use_cls": False,
            "Global.log_level": "warning",
            "Det.model_path": str(det),
            "Rec.model_path": str(rec),
            # Explicit thread count: with the default, onnxruntime pins threads to every host CPU
            # and logs an affinity error per thread inside a CPU-limited container.
            "EngineConfig.onnxruntime.intra_op_num_threads": _ocr_threads(),
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        }
    )


def _ocr_threads() -> int:
    return max(1, min(4, len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else 4))


def ocr_available(settings: Settings) -> bool:
    return _rapidocr(settings.ocr_model_dir) is not None


def _rapidocr_boxes(engine: RapidOCR, pixels: Gray) -> list[_Box]:
    from rapidocr.utils.output import RapidOCROutput

    result = engine(pixels)
    if not isinstance(result, RapidOCROutput):
        return []
    if result.boxes is None or result.txts is None or result.scores is None:
        return []
    return [
        _Box(
            float(quad[:, 0].min()),
            float(quad[:, 1].min()),
            float(quad[:, 0].max()),
            float(quad[:, 1].max()),
            text,
            float(score),
        )
        for quad, text, score in zip(result.boxes, result.txts, result.scores, strict=True)
    ]


def _tesseract_boxes(pixels: Gray, tessdata_dir: Path | None) -> list[_Box] | None:
    exe = shutil.which("tesseract")
    if exe is None:
        return None
    ok, png = cv2.imencode(".png", pixels)
    if not ok:
        return None
    command = [exe, "stdin", "stdout", "-l", "pol", "--psm", "3", "-c", "tessedit_create_tsv=1"]
    if tessdata_dir is not None:
        command[3:3] = ["--tessdata-dir", str(tessdata_dir)]
    try:
        done = subprocess.run(
            command,
            input=png.tobytes(),
            capture_output=True,
            timeout=TESSERACT_TIMEOUT_S,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Tesseract failed on a page: %s", type(exc).__name__)
        return None
    return parse_tsv(done.stdout.decode("utf-8", errors="replace"))


def parse_tsv(tsv: str) -> list[_Box]:
    """Word boxes (level 5) from Tesseract's TSV output; confidence scaled to 0..1."""
    boxes = []
    for row in tsv.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or cols[0] != "5" or not cols[11].strip():
            continue
        left, top, width, height = (int(c) for c in cols[6:10])
        boxes.append(
            _Box(left, top, left + width, top + height, cols[11], max(0.0, float(cols[10])) / 100)
        )
    return boxes


def _assemble(boxes: list[_Box], ids: Iterator[int], scale: float) -> list[Line]:
    """Group boxes into lines in reading order: rows top to bottom, then left to right."""
    if not boxes:
        return []
    median = statistics.median(b.y1 - b.y0 for b in boxes)
    lines = []
    for row in _rows(boxes):
        for group in _split_row(row):
            text = re.sub(r"\s+", " ", " ".join(b.text for b in group)).strip()
            kind = LineKind.TEXT
            if text[:1] in BOX_GLYPHS:
                kind, text = LineKind.CHECKBOX, text[1:].strip()
            x0, y0 = min(b.x0 for b in group), min(b.y0 for b in group)
            x1, y1 = max(b.x1 for b in group), max(b.y1 for b in group)
            if kind is LineKind.TEXT and text.isupper() and y1 - y0 > HEADING_RATIO * median:
                kind = LineKind.HEADING
            if not text:
                continue
            lines.append(
                Line(
                    id=f"L{next(ids)}",
                    text=text,
                    kind=kind,
                    bbox=(x0 * scale, y0 * scale, x1 * scale, y1 * scale),
                )
            )
    return lines


def _rows(boxes: list[_Box]) -> list[list[_Box]]:
    """Cluster boxes whose vertical extents overlap by at least half the smaller height."""
    rows: list[list[_Box]] = []
    for box in sorted(boxes, key=lambda b: b.cy):
        if rows:
            ref = rows[-1][0]
            overlap = min(ref.y1, box.y1) - max(ref.y0, box.y0)
            if overlap >= 0.5 * min(ref.y1 - ref.y0, box.y1 - box.y0):
                rows[-1].append(box)
                continue
        rows.append([box])
    return [sorted(row, key=lambda b: b.x0) for row in rows]


def _split_row(row: list[_Box]) -> list[list[_Box]]:
    """Split a row where the horizontal gap shows separate columns."""
    height = max(b.y1 for b in row) - min(b.y0 for b in row)
    groups = [[row[0]]]
    for prev, box in itertools.pairwise(row):
        if box.x0 - prev.x1 > JOIN_GAP * height:
            groups.append([])
        groups[-1].append(box)
    return groups
