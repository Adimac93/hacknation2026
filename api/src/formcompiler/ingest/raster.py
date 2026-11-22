"""PNG and JPEG images, and PDF pages without a text layer -> Document through OCR (D5).

RapidOCR with the PP-OCRv6 small models reads each page, always with `use_cls=False`: the
orientation classifier it ships flips random lines and raised CER from 1.8% to 16%
(research/01). Tesseract 5 `pol` re-reads a page when RapidOCR is unsure or unavailable. The image
never touches the disk: Tesseract gets the page as PNG on stdin and answers on stdout, and model
paths are always explicit, so RapidOCR never downloads anything.

Tall images are several A4 pages stacked vertically; they are cut into pages first, because OCR of
the whole strip returns noise. OCR loses dot leaders and most checkboxes, so a line is CHECKBOX only
when the engine returned a box glyph.

A page that is a whole image (a scan or a phone photo, not a page cut from a stack) is first put
upright (research/11): a page photographed on a darker desk is cut out and its perspective undone,
a page turned by 90 degrees is turned back, and skew up to 15 degrees is removed. All three come
from a cheap projection profile of the text on a ~1000 px copy. A page upside down is caught after
OCR by its low confidence and read again turned by 180 degrees, so upright pages pay nothing for it.
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
from concurrent.futures import ThreadPoolExecutor
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
OCR_THREADS_PER_PAGE = 2
MAX_PARALLEL_PAGES = 4
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

# Page geometry of a whole-image page, research/11.
MAX_WIDTH = 2000  # wider images (phone photos) are scaled down to NOMINAL_WIDTH first
NOMINAL_WIDTH = 1654  # A4 at 200 DPI, the width of the organiser's rasters
WORK = 1000  # longer side of the copy that page geometry is measured on
GLYPH_MAX = 0.04  # ink blobs larger than this share of WORK are rules or edges, not letters
MAX_SKEW = 15  # degrees of skew searched for
COARSE = 0.5  # degrees between skew candidates before refining by 0.1; a peak is ~0.8 degrees wide
MIN_SKEW = 0.5  # smaller skew is left alone: OCR reads it fine, interpolation costs detail
TURNED = 2.0  # column profile this many times sharper than the row profile = text runs vertically
UPSIDE_DOWN = 0.6  # ink above the x-height band over ink below it; below this the text is inverted
PAGE_AREA = (0.3, 0.97)  # share of the photo a page cut out of a desk must cover
DESK_CONTRAST = 40  # grey levels by which the desk just outside the sheet's edge is darker
EDGE_BAND = 5  # px of the work copy on each side of the sheet's edge compared for that contrast
DESK_INK = 0.3  # the desk may hold at most this share of the paper's ink density


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
    image = limit_width(decode(data))
    slices = split_pages(image)
    check_pages(len(slices), settings)
    if len(slices) == 1:  # a single page: a scan or a photo whose geometry is unknown
        return ocr_pages([PageImage(image)], settings)
    return ocr_pages(
        (
            PageImage(image[s.top : s.bottom], (s.keep_top - s.top, s.keep_bottom - s.top))
            for s in slices
        ),
        settings,
    )


def limit_width(image: Gray) -> Gray:
    """Scale a wide image (a phone photo) down to A4 at 200 DPI; OCR gains nothing above that."""
    height, width = image.shape
    if width <= MAX_WIDTH:
        return image
    size = (NOMINAL_WIDTH, round(height * NOMINAL_WIDTH / width))
    return np.asarray(cv2.resize(image, size, interpolation=cv2.INTER_AREA), dtype=np.uint8)


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


def upright(pixels: Gray) -> Gray:
    """Cut the page out of a photo, turn vertical text by 90° and remove skew (research/11)."""
    small, scale = _work_copy(pixels)
    quad = _page_quad(small)
    if quad is not None:
        pixels = _unwarp(pixels, quad / scale)
        small, scale = _work_copy(pixels)
    ink = _glyphs(small)
    if not ink.any():
        return pixels
    rows = _sharpest(ink, axis=1, step=COARSE)
    columns = _sharpest(ink, axis=0, step=1.0)
    if columns[1] > TURNED * rows[1]:  # text runs vertically: turn clockwise, then check below
        pixels = np.ascontiguousarray(np.rot90(pixels, -1))
        ink = np.ascontiguousarray(np.rot90(ink, -1))
        rows = _sharpest(ink, axis=1, step=COARSE)
    angle, _ = _sharpest(ink, axis=1, step=0.1, around=rows[0], radius=COARSE)
    if abs(angle) >= MIN_SKEW:
        pixels = rotate(pixels, angle)
        ink = _glyphs(_work_copy(pixels)[0])
    if _upside_down(ink):  # a guess; a wrong one is undone by OCR confidence in _read_page
        pixels = np.ascontiguousarray(pixels[::-1, ::-1])
    return pixels


def _upside_down(ink: Gray) -> bool:
    """Latin and Polish text has more ink above the x-height band (ascenders, capitals, accents)
    than below it (descenders, ogoneks); level text where it is the other way round is inverted."""
    profile = ink.sum(axis=1, dtype=np.float64)
    rows = np.flatnonzero(profile)
    above = below = 0.0
    for line in np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1):
        if len(line) < 4:
            continue
        span = profile[line[0] : line[-1] + 1]
        core = np.flatnonzero(span >= span.max() / 2)
        above += float(span[: core[0]].sum())
        below += float(span[core[-1] + 1 :].sum())
    return above < UPSIDE_DOWN * below


def _work_copy(pixels: Gray) -> tuple[Gray, float]:
    height, width = pixels.shape
    scale = WORK / max(height, width)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    method = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return np.asarray(cv2.resize(pixels, size, interpolation=method), dtype=np.uint8), scale


def _ink(small: Gray) -> Gray:
    """Dark-on-light strokes; a local threshold copes with uneven light."""
    return np.asarray(
        cv2.adaptiveThreshold(small, 1, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 15),
        dtype=np.uint8,
    )


def _glyphs(small: Gray) -> Gray:
    """Ink of letter-sized blobs only: table rules and page edges would mislead the profiles."""
    ink = _ink(small)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    limit = GLYPH_MAX * WORK
    width, height = stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT]
    keep = (width <= limit) & (height <= limit) & (stats[:, cv2.CC_STAT_AREA] >= 3)
    keep[0] = False  # background
    return np.asarray(keep[labels], dtype=np.uint8) if count > 1 else np.zeros_like(ink)


def _sharpest(
    ink: Gray, axis: int, step: float, around: float = 0.0, radius: float = MAX_SKEW
) -> tuple[float, float]:
    """Angle (degrees, counter-clockwise) whose rotation makes the ink profile sharpest.

    Text lines turned level make the row profile jump between full rows and empty gaps, so the
    energy of its steps peaks (Postl's method); `axis=0` measures the column profile, which peaks
    for vertical text. Steps, unlike plain variance, ignore where the text block sits on the page.
    """
    height, width = ink.shape
    best = (around, -1.0)
    for angle in np.arange(around - radius, around + radius + step / 2, step):
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), float(angle), 1.0)
        turned = cv2.warpAffine(ink, matrix, (width, height), flags=cv2.INTER_NEAREST)
        sharpness = float(np.square(np.diff(turned.sum(axis=axis, dtype=np.float64))).sum())
        if sharpness > best[1]:
            best = (round(float(angle), 2), sharpness)
    return best


def rotate(pixels: Gray, angle: float) -> Gray:
    """Rotate counter-clockwise by `angle` degrees on a canvas grown to keep the corners."""
    height, width = pixels.shape
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    size = (round(height * sin + width * cos), round(height * cos + width * sin))
    matrix[0, 2] += size[0] / 2 - width / 2
    matrix[1, 2] += size[1] / 2 - height / 2
    turned = cv2.warpAffine(pixels, matrix, size, flags=cv2.INTER_LINEAR, borderValue=255)
    return np.asarray(turned, dtype=np.uint8)


def _page_quad(small: Gray) -> NDArray[np.float32] | None:
    """Corners (tl, tr, br, bl) of a sheet photographed on a darker desk, or None for a scan."""
    _, paper = cv2.threshold(
        cv2.GaussianBlur(small, (5, 5), 0), 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    paper = cv2.morphologyEx(paper, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(paper, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    hull = cv2.convexHull(max(contours, key=cv2.contourArea))
    share = cv2.contourArea(hull) / small.size
    if not PAGE_AREA[0] <= share <= PAGE_AREA[1]:
        return None
    quad = cv2.approxPolyDP(hull, 0.02 * cv2.arcLength(hull, True), True)
    if len(quad) != 4:
        return None
    inside = np.zeros_like(small)
    cv2.fillConvexPoly(inside, quad, 1)
    sheet, desk = inside.astype(bool), ~inside.astype(bool)
    # A sheet's edge is a sharp step down to the desk; uneven light only fades slowly.
    band = np.ones((2 * EDGE_BAND + 1, 2 * EDGE_BAND + 1), np.uint8)
    edge_in = sheet & ~cv2.erode(inside, band, borderValue=1).astype(bool)
    edge_out = desk & cv2.dilate(inside, band).astype(bool)
    if not edge_out.any() or not edge_in.any():
        return None
    if float(np.median(small[edge_out])) > float(np.median(small[edge_in])) - DESK_CONTRAST:
        return None
    # Text on the "desk" means an unevenly lit page, not a sheet lying on a desk. The step at the
    # sheet's edge itself thresholds as ink, so a margin along the edge is left out of both sides.
    ink = _ink(small).astype(bool)
    margin = cv2.dilate(edge_in | edge_out, band, iterations=2).astype(bool)
    far_desk, core = desk & ~margin, sheet & ~margin
    if not core.any():
        return None
    if far_desk.any() and ink[far_desk].mean() > DESK_INK * max(float(ink[core].mean()), 1e-6):
        return None
    return _order(quad.reshape(4, 2).astype(np.float32))


def _order(points: NDArray[np.float32]) -> NDArray[np.float32]:
    total, diff = points.sum(axis=1), np.diff(points, axis=1).ravel()
    return np.array(
        [
            points[np.argmin(total)],
            points[np.argmin(diff)],
            points[np.argmax(total)],
            points[np.argmax(diff)],
        ],
        dtype=np.float32,
    )


def _unwarp(pixels: Gray, quad: NDArray[np.float32]) -> Gray:
    """Map the sheet's corners onto an upright rectangle of the same size."""
    tl, tr, br, bl = quad
    width = round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    target = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad.astype(np.float32), target)
    flat = cv2.warpPerspective(
        pixels, matrix, (width, height), flags=cv2.INTER_LINEAR, borderValue=255
    )
    return np.asarray(flat, dtype=np.uint8)


def ocr_pages(pages: Iterable[PageImage], settings: Settings, scale: float = 1.0) -> Document:
    """OCR page images into a Document; `scale` converts pixels into the Document's units."""
    ids = itertools.count(1)
    out: list[Page] = []
    tail: list[str] = []  # lines the previous page kept next to its bottom cut
    # Pages are independent until _own, so they are read in parallel; map keeps their order.
    with ThreadPoolExecutor(max_workers=_ocr_workers()) as pool:
        read = list(pool.map(lambda image: _read_image(image, settings), pages))
    for number, (page, pixels, boxes) in enumerate(read, 1):
        if page.keep is not None:
            boxes, tail = _own(boxes, page.keep, tail)
        height, width = pixels.shape
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


def _read_image(image: PageImage, settings: Settings) -> tuple[PageImage, Gray, list[_Box]]:
    """OCR one page; a whole-image page is put upright first. Returns the pixels that were read."""
    if image.keep is not None:  # cut from a stack of clean rasters, read as it is
        return image, image.pixels, _read_page(image.pixels, settings)
    pixels = upright(image.pixels)
    return image, pixels, _read_page(pixels, settings, may_be_upside_down=True)


def _read_page(pixels: Gray, settings: Settings, may_be_upside_down: bool = False) -> list[_Box]:
    """OCR a page; boxes fit `pixels`, turned by 180° when that reads better."""
    boxes: list[_Box] | None = None
    engine = _rapidocr(settings.ocr_model_dir)
    if engine is not None:
        boxes = _try_rapidocr(engine, pixels)
        if (
            may_be_upside_down
            and boxes
            and confidence(boxes) < settings.ocr_min_confidence
            and (turned := _try_rapidocr(engine, pixels[::-1, ::-1])) is not None
            and confidence(turned) > confidence(boxes)
        ):
            # Upside-down text reads at ~0.65 against ~0.98 upright. Boxes of the turned page
            # still fit the page's size, and the turned pixels are what Tesseract gets below.
            boxes, pixels = turned, np.ascontiguousarray(pixels[::-1, ::-1])
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


def _try_rapidocr(engine: RapidOCR, pixels: Gray) -> list[_Box] | None:
    try:
        return _rapidocr_boxes(engine, np.ascontiguousarray(pixels))
    except Exception as exc:  # any engine failure falls back to Tesseract
        log.warning("RapidOCR failed on a page: %s", type(exc).__name__)
        return None


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


def _cpus() -> int:
    """CPUs this process may run on (the container's share, not the host's count)."""
    if hasattr(os, "sched_getaffinity"):
        return max(1, len(os.sched_getaffinity(0)))
    return max(1, os.cpu_count() or 1)


def _ocr_threads() -> int:
    # Measured on form 9 (16 pages, M1 Pro): 4 threads x 1 page 20.9 s, 2 threads x 4 pages
    # 13.9 s, 1 thread x 8 pages 14.7 s; same boxes in every setup.
    return min(OCR_THREADS_PER_PAGE, _cpus())


def _ocr_workers() -> int:
    return max(1, min(MAX_PARALLEL_PAGES, _cpus() // _ocr_threads()))


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
