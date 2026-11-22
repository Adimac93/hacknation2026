import io
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pdfplumber
import pypdfium2 as pdfium  # type: ignore[import-untyped]
import pytest

from formcompiler import heuristics
from formcompiler.config import Settings
from formcompiler.document import Document, LineKind
from formcompiler.ingest import READERS, raster
from formcompiler.ingest.raster import Gray, PageImage, Slice, _Box
from formcompiler.upload import FileKind, UploadError

DOCS = Path(__file__).resolve().parents[2] / "Docs"
FORM3 = next(DOCS.glob("3. */*.png"))
FORM3_PDF = next(DOCS.glob("3. */*.pdf"))
FORM3_JPG = next(DOCS.glob("3. */*.jpg"))
FORM7 = next(DOCS.glob("7. */*.PNG"))
FORM7_PDF = next(DOCS.glob("7. */*.PDF"))
FORM9 = next(DOCS.glob("9. */*.png"))
MAX_CER = 0.06


def make(**env: Any) -> Settings:
    return Settings(_env_file=None, **env)


HAS_WEIGHTS = raster.ocr_available(make())
needs_weights = pytest.mark.skipif(not HAS_WEIGHTS, reason="no PP-OCRv6 weights (OCR_MODEL_DIR)")


def has_tesseract_pol() -> bool:
    exe = shutil.which("tesseract")
    if exe is None:
        return False
    tessdata = make().tessdata_dir
    command = [exe, *(["--tessdata-dir", str(tessdata)] if tessdata else []), "--list-langs"]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    return "pol" in (done.stdout + done.stderr).split()


needs_tesseract = pytest.mark.skipif(not has_tesseract_pol(), reason="no tesseract with `pol`")


def box(x0: float, y0: float, x1: float, y1: float, text: str, score: float = 0.99) -> _Box:
    return _Box(x0, y0, x1, y1, text, score)


def white(height: int, width: int) -> Gray:
    return np.full((height, width), 255, np.uint8)


# --- page splitting ------------------------------------------------------------------------------


def test_form9_strip_splits_into_sixteen_clean_pages() -> None:
    slices = raster.split_pages(raster.decode(FORM9.read_bytes()))

    assert len(slices) == 16
    assert all(s.bottom - s.top == 2339 for s in slices)
    assert all((s.top, s.bottom) == (s.keep_top, s.keep_bottom) for s in slices)


def test_single_page_image_is_one_page() -> None:
    assert raster.split_pages(raster.decode(FORM3.read_bytes())) == [Slice(0, 2339, 0, 2339)]


def test_small_remainder_stays_on_the_last_page() -> None:
    page = round(400 * 2**0.5)
    assert len(raster.split_pages(white(int(page * 1.1), 400))) == 1


def test_cut_moves_to_the_blank_band_near_the_nominal_row() -> None:
    page = round(400 * 2**0.5)  # 566
    image = white(1300, 400)
    image[:, 10:20] = 0  # a margin rule on every row ...
    image[600:640, 10:20] = 255  # ... except a band 34-74 rows below the nominal cut

    slices = raster.split_pages(image)

    assert slices[0] == Slice(0, 619, 0, 619)
    assert (slices[1].top, slices[1].keep_top) == (619, 619)
    assert slices[0].bottom > page


def test_no_blank_band_cuts_with_overlap() -> None:
    image = white(1300, 400)
    image[:, 10:20] = 0  # no blank row anywhere

    first, second, *_ = raster.split_pages(image)

    half = raster.OVERLAP // 2
    assert (first.keep_bottom, second.keep_top) == (566, 566)
    assert (first.bottom, second.top) == (566 + half, 566 - half)


def test_too_many_pages_is_rejected() -> None:
    with pytest.raises(UploadError) as err:
        raster.read(FORM9.read_bytes(), FileKind.PNG, make(max_pages=10))
    assert err.value.status == 413


def test_garbage_image_is_rejected() -> None:
    with pytest.raises(UploadError) as err:
        raster.decode(b"\x89PNG\r\n\x1a\nnot really a png")
    assert err.value.status == 415


def test_png_and_jpeg_readers_are_registered() -> None:
    assert READERS[FileKind.PNG] is raster.read
    assert READERS[FileKind.JPEG] is raster.read


# --- lines from boxes ----------------------------------------------------------------------------


def assemble(boxes: list[_Box]) -> list[tuple[str, LineKind]]:
    return [(line.text, line.kind) for line in raster._assemble(boxes, iter(range(1, 99)), 1.0)]


def test_boxes_on_one_row_join_and_columns_stay_apart() -> None:
    boxes = [
        box(287, 1704, 1457, 1739, "Opłatę należy wnieść"),
        box(242, 1707, 283, 1735, "2."),
        box(189, 305, 309, 342, "/ adres /"),
        box(989, 312, 1447, 354, "Urząd Miasta"),
    ]
    assert assemble(boxes) == [
        ("/ adres /", LineKind.TEXT),
        ("Urząd Miasta", LineKind.TEXT),
        ("2. Opłatę należy wnieść", LineKind.TEXT),
    ]


def test_box_glyph_makes_a_checkbox_and_tall_capitals_a_heading() -> None:
    boxes = [
        box(100, 100, 900, 160, "WNIOSEK O WYDANIE"),
        box(100, 200, 600, 235, "□ okresie posiadania"),
        box(100, 300, 600, 335, "zwykły tekst"),
        box(100, 400, 600, 435, "NAPISANE WIELKIMI"),
    ]
    assert assemble(boxes) == [
        ("WNIOSEK O WYDANIE", LineKind.HEADING),
        ("okresie posiadania", LineKind.CHECKBOX),
        ("zwykły tekst", LineKind.TEXT),
        ("NAPISANE WIELKIMI", LineKind.TEXT),
    ]


def test_overlap_keeps_a_line_on_the_cut_once() -> None:
    upper = [box(0, 10, 100, 40, "nad cięciem"), box(0, 486, 300, 530, "linia na cięciu")]
    lower = [box(0, 48, 300, 92, "linia na cięciu"), box(0, 120, 100, 150, "pod cięciem")]

    kept_upper, tail = raster._own(upper, (0, 504), [])
    kept_lower, _ = raster._own(lower, (64, 600), tail)

    assert [b.text for b in kept_upper + kept_lower] == [
        "nad cięciem",
        "linia na cięciu",
        "pod cięciem",
    ]


def test_tesseract_tsv_gives_word_boxes() -> None:
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "4\t1\t1\t1\t1\t0\t197\t312\t1247\t37\t-1\t\n"
        "5\t1\t1\t1\t1\t1\t216\t312\t68\t24\t86.5\tadres\n"
        "5\t1\t1\t1\t1\t2\t294\t312\t8\t23\t-1\t \n"
    )
    assert raster.parse_tsv(tsv) == [box(216, 312, 284, 336, "adres", 0.865)]


# --- OCR quality (needs weights) -----------------------------------------------------------------


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[-□■☐❑❒▢◻]", " ", text)  # checkbox glyphs, PUA symbol fonts
    text = re.sub(r"[.…_]{2,}", " ", text)  # dot leaders
    return re.sub(r"\s+", " ", text).strip()


def levenshtein(a: str, b: str) -> int:
    """Edit distance, one numpy row at a time (insertions resolved with a running minimum)."""
    target = np.frombuffer(b.encode("utf-32-le"), np.uint32)
    idx = np.arange(len(b) + 1)
    row = idx.copy()
    for i, char in enumerate(a, 1):
        cost = (target != ord(char)).astype(np.int64)
        step = np.empty_like(row)
        step[0] = i
        step[1:] = np.minimum(row[1:] + 1, row[:-1] + cost)
        row = np.minimum.accumulate(step - idx) + idx
    return int(row[-1])


def cer(doc: Document, pdf: Path) -> float:
    with pdfplumber.open(pdf) as reference:
        truth = [normalize(page.extract_text() or "") for page in reference.pages]
    pages = [normalize(" ".join(line.text for line in page.lines)) for page in doc.pages]
    assert len(pages) == len(truth)
    errors = sum(levenshtein(p, t) for p, t in zip(pages, truth, strict=True))
    return errors / sum(len(t) for t in truth)


@pytest.fixture(scope="module")
def form3() -> Document:
    return raster.read(FORM3.read_bytes(), FileKind.PNG, make())


@needs_weights
def test_levenshtein_helper() -> None:
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3


@needs_weights
def test_form3_png_cer(form3: Document) -> None:
    assert cer(form3, FORM3_PDF) < MAX_CER


@needs_weights
def test_form7_png_cer() -> None:
    doc = raster.read(FORM7.read_bytes(), FileKind.PNG, make())
    assert len(doc.pages) == 2
    assert cer(doc, FORM7_PDF) < MAX_CER


@needs_weights
def test_heuristics_find_the_title_of_form3(form3: Document) -> None:
    assert heuristics.analyze(form3).title == "Wniosek o wydanie zaświadczenia"


@needs_weights
def test_lines_have_ids_bboxes_and_reading_order(form3: Document) -> None:
    lines = form3.pages[0].lines
    assert [line.id for line in lines] == [f"L{i}" for i in range(1, len(lines) + 1)]
    tops = [line.bbox[1] for line in lines if line.bbox]
    assert len(tops) == len(lines)
    assert tops.index(min(tops)) == 0
    assert form3.pages[0].width == 1654


def text_strip(lines: int, rule: bool) -> Gray:
    """Numbered lines of large print, 40 px apart, so any cut goes through text."""
    image = white(40 * lines + 60, 1000)
    for n in range(lines):
        cv2.putText(image, f"Linia numer {n:03d}", (60, 60 + 40 * n), 0, 1.0, 0, 2)
    if rule:
        image[:, 20:26] = 0
    return image


@needs_weights
def test_strip_without_blank_band_has_no_duplicate_lines() -> None:
    image = text_strip(60, rule=True)  # 2460 rows, page height 1414: one cut through text
    slices = raster.split_pages(image)
    assert len(slices) == 2 and slices[0].bottom > slices[1].top

    _, png = cv2.imencode(".png", image)
    doc = raster.read(png.tobytes(), FileKind.PNG, make())

    numbers = [
        m
        for line in doc.pages[0].lines + doc.pages[1].lines
        if (m := re.search(r"(\d{3})\s*$", line.text))
    ]
    found = [m.group(1) for m in numbers]
    assert len(found) == len(set(found))
    assert len(found) >= 57  # OCR may miss a line or two, but not the overlap


@needs_weights
def test_jpeg_reads_like_png(form3: Document) -> None:
    doc = raster.read(FORM3_JPG.read_bytes(), FileKind.JPEG, make())
    assert cer(doc, FORM3_PDF) < MAX_CER


def scanned_pdf(jpeg: bytes, width_pt: float, height_pt: float) -> bytes:
    """A PDF whose only page content is the JPEG, i.e. no text layer."""
    pdf = pdfium.PdfDocument.new()
    page = pdf.new_page(width_pt, height_pt)
    image = pdfium.PdfImage.new(pdf)
    image.load_jpeg(io.BytesIO(jpeg), inline=True)
    image.set_matrix(pdfium.PdfMatrix().scale(width_pt, height_pt))
    page.insert_obj(image)
    page.gen_content()
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


@needs_weights
def test_scanned_pdf_is_read_with_bboxes_in_points() -> None:
    data = scanned_pdf(FORM3_JPG.read_bytes(), 595.2, 841.8)

    doc = raster.ocr_pdf(data, make())

    page = doc.pages[0]
    assert page.width == pytest.approx(595.2, abs=1)
    width = page.width or 0
    assert all(line.bbox and line.bbox[2] <= width + 1 for line in page.lines)
    assert cer(doc, FORM3_PDF) < MAX_CER


def test_scanned_pdf_page_limit() -> None:
    data = scanned_pdf(FORM3_JPG.read_bytes(), 595.2, 841.8)
    with pytest.raises(UploadError) as err:
        raster.ocr_pdf(data, make(max_pages=0))
    assert err.value.status == 413


# --- page geometry of scans and photos -----------------------------------------------------------

WORDS = ["Wniosek", "Imie", "nazwisko", "adres", "Lublin", "gminy", "pozwolenie", "data", "kopia"]


def text_page(width: int = 1000, lines: int = 26) -> Gray:
    """A portrait page of prose-like lines, so letter shapes and line gaps look like a form."""
    page = white(round(width * 2**0.5), width)
    for n in range(lines):
        words = " ".join(WORDS[(n + k) % len(WORDS)] for k in range(5))
        cv2.putText(page, f"{n:02d} {words}", (50, 70 + 50 * n), 0, 0.9, 0, 2)
    return page


def skew_of(pixels: Gray) -> float:
    small, _ = raster._work_copy(pixels)
    ink = raster._glyphs(small)
    coarse, _ = raster._sharpest(ink, axis=1, step=1.0)
    return raster._sharpest(ink, axis=1, step=0.1, around=coarse, radius=1.0)[0]


def is_upright(pixels: Gray) -> bool:
    small, _ = raster._work_copy(pixels)
    ink = raster._glyphs(small)
    rows = raster._sharpest(ink, axis=1, step=1.0)[1]
    columns = raster._sharpest(ink, axis=0, step=1.0)[1]
    return rows > columns and not raster._upside_down(ink)


@pytest.mark.parametrize("angle", [-7.0, -3.0, -1.0, 1.0, 3.0, 7.0])
def test_skewed_page_is_levelled(angle: float) -> None:
    page = raster.rotate(text_page(), angle)

    assert abs(skew_of(page) + angle) < 0.3
    assert abs(skew_of(raster.upright(page))) < 0.3


@pytest.mark.parametrize("turn", [1, 2, 3])
def test_turned_page_is_put_upright(turn: int) -> None:
    page = text_page()

    out = raster.upright(np.ascontiguousarray(np.rot90(page, turn)))

    assert out.shape == page.shape
    assert is_upright(out)


def test_clean_page_is_left_alone() -> None:
    page = text_page()
    assert raster.upright(page) is page


def test_blank_and_tiny_images_pass_through() -> None:
    for image in (white(50, 300), np.zeros((40, 40), np.uint8)):
        assert raster.upright(image) is image


def photographed(page: Gray, desk: int = 60) -> Gray:
    """The page shot at an angle, lying on a darker desk with a margin around it."""
    height, width = page.shape
    pad = width // 10
    corners = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    shot = np.float32(
        [
            [pad + 0.06 * width, pad + 0.03 * height],
            [pad + 0.98 * width, pad],
            [pad + width, pad + 0.99 * height],
            [pad, pad + 0.96 * height],
        ]
    )
    matrix = cv2.getPerspectiveTransform(corners, shot)
    size = (width + 2 * pad, height + 2 * pad)
    return np.asarray(cv2.warpPerspective(page, matrix, size, borderValue=desk), np.uint8)


def test_page_is_cut_out_of_a_photo_and_flattened() -> None:
    page = text_page()

    out = raster.upright(photographed(page))

    height, width = out.shape
    assert abs(width - page.shape[1]) < 0.05 * page.shape[1]
    assert abs(height - page.shape[0]) < 0.05 * page.shape[0]
    assert out[:5].mean() > 200 and out[:, -5:].mean() > 200  # no desk left at the edges
    assert abs(skew_of(out)) < 0.3


def test_scan_and_unevenly_lit_page_are_not_cut() -> None:
    page = text_page()
    gain = np.linspace(1.0, 0.45, page.shape[1], dtype=np.float32)[None, :]
    dim = np.asarray(page * gain, np.uint8)

    for image in (page, dim):
        small, _ = raster._work_copy(image)
        assert raster._page_quad(small) is None


def test_wide_photo_is_scaled_to_a4_width() -> None:
    assert raster.limit_width(white(4400, 3300)).shape == (2205, 1654)
    narrow = white(1400, 1000)
    assert raster.limit_width(narrow) is narrow


def test_pages_cut_from_a_stack_keep_their_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_: Gray) -> Gray:
        raise AssertionError("a page cut from a stack must not be turned")

    monkeypatch.setattr(raster, "upright", fail)
    monkeypatch.setattr(raster, "_read_page", lambda *_, **__: [])
    _, png = cv2.imencode(".png", text_strip(60, rule=True))

    assert len(raster.read(png.tobytes(), FileKind.PNG, make()).pages) == 2


def test_low_confidence_page_is_read_again_upside_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def boxes(_: object, pixels: Gray) -> list[_Box]:
        upright = pixels[0, 0] == 255  # the marker corner is black at the bottom right
        return [box(0, 0, 10, 10, "Wniosek", 0.98 if upright else 0.6)]

    tesseract: list[Gray] = []
    monkeypatch.setattr(raster, "_rapidocr", lambda _: object())
    monkeypatch.setattr(raster, "_rapidocr_boxes", boxes)
    monkeypatch.setattr(raster, "_tesseract_boxes", lambda p, _: tesseract.append(p))
    page = white(100, 100)
    page[:10, :10] = 0  # inverted: the black corner is at the top left

    assert raster._read_page(page, make(), may_be_upside_down=True)[0].score == 0.98
    assert tesseract == []
    assert raster._read_page(page, make())[0].score == 0.6  # a page from a stack is not turned


@needs_weights
@pytest.mark.parametrize("turn", ["skew", "upside-down", "photo"])
def test_degraded_page_reads_like_a_clean_one(turn: str) -> None:
    page = text_page()
    degraded = {
        "skew": lambda: raster.rotate(page, 4.0),
        "upside-down": lambda: np.ascontiguousarray(page[::-1, ::-1]),
        "photo": lambda: photographed(page),
    }[turn]()
    _, png = cv2.imencode(".png", degraded)

    doc = raster.read(png.tobytes(), FileKind.PNG, make())

    numbers = {m.group(1) for line in doc.pages[0].lines if (m := re.match(r"(\d\d) ", line.text))}
    assert len(numbers) >= 24  # of 26 numbered lines


# --- fallback ------------------------------------------------------------------------------------


@needs_tesseract
def test_tesseract_reads_the_page_when_rapidocr_is_missing(tmp_path: Path) -> None:
    doc = raster.read(FORM3.read_bytes(), FileKind.PNG, make(ocr_model_dir=tmp_path))

    text = doc.linearize()
    assert "ZAŚWIADCZENIA" in text
    assert cer(doc, FORM3_PDF) < 0.15


@needs_weights
@needs_tesseract
def test_low_confidence_switches_to_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = raster._tesseract_boxes

    def spy(*args: Any) -> list[_Box] | None:
        calls.append("tesseract")
        return real(*args)

    monkeypatch.setattr(raster, "_tesseract_boxes", spy)
    raster.read(FORM3.read_bytes(), FileKind.PNG, make(ocr_min_confidence=1.0))
    assert calls == ["tesseract"]


def test_no_engine_at_all_is_a_service_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(UploadError) as err:
        raster.ocr_pages(iter([PageImage(white(100, 100))]), make(ocr_model_dir=tmp_path))
    assert err.value.status == 503


def test_pages_read_in_parallel_keep_their_order(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    def read_page(pixels: Gray, settings: Settings, **_: object) -> list[_Box]:
        number = int(pixels[0, 0])
        time.sleep(0.02 * (6 - number))  # later pages finish first
        return [box(10, 10, 200, 30, f"Strona {number}")]

    monkeypatch.setattr(raster, "_read_page", read_page)
    monkeypatch.setattr(raster, "_ocr_workers", lambda: 4)
    pages = [PageImage(np.full((50, 300), n, dtype=np.uint8)) for n in range(1, 6)]

    doc = raster.ocr_pages(pages, Settings(_env_file=None))

    assert [p.lines[0].text for p in doc.pages] == [f"Strona {n}" for n in range(1, 6)]
    assert [p.number for p in doc.pages] == [1, 2, 3, 4, 5]
