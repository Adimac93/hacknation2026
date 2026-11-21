# /// script
# requires-python = ">=3.14"
# dependencies = ["httpx>=0.28", "pypdfium2>=4.30"]
# ///
"""Collect official form templates ("wzory") from the Sejm ELI API.

Searches in-force acts whose title names a form template, downloads each
act's PDF, cuts every attachment ("Załącznik") into its own PDF and writes a
JSONL manifest with simple form features. Offline research tool, not part of
the service.

    uv run devtools/corpus/eli.py --out corpus
"""

from __future__ import annotations

import argparse
import hashlib
import io
import itertools
import json
import re
import sys
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

API = "https://api.sejm.gov.pl/eli"
USER_AGENT = "guppy-corpus/0.1 (HackNation 2026 research; polite crawler)"
BACKOFF = (10, 30, 60, 120, 300)

QUERIES = (
    "wzoru wniosku",
    "wzorów wniosków",
    "wzoru formularza",
    "wzorów formularzy",
    "wzoru deklaracji",
    "wzorów deklaracji",
    "wzoru zgłoszenia",
    "wzorów zgłoszeń",
    "wzoru oświadczenia",
    "wzorów oświadczeń",
    "wzoru informacji",
    "wzoru zawiadomienia",
)

# Titles that match the queries but define things that are not fillable forms.
NON_FORM_TITLE = re.compile(
    r"legitymacj|odznak|pieczęci|tablic|munduru|znaku|plakiet|identyfikator|naklejk",
    re.IGNORECASE,
)

# Attachment labels sit anywhere on the page: designed forms have no reliable
# text order, and raster pages carry the label twice, often split mid-number
# ("Załącznik nr 1\r\n5", "Załącznik nr Załącznik nr 18 18"). A label must end
# its line or run into "do <act>", another label or a digit; running text such
# as "Załącznik nr 1 zawiera" or a form's "Załącznik nr 2 do wniosku" does not.
NUMBERED_LABEL = re.compile(
    r"(?:Załącznik|ZAŁĄCZNIK)[ \t]+(?:nr|NR)[ \t]+(\d+)"
    r"(?=[ \t]*(?:\r?$|\d|Załącznik|do[ \t]+(?:rozporządzenia|obwieszczenia|uchwały|zarządzenia|ustawy)))",
    re.MULTILINE,
)
GENERIC_LABEL = re.compile(
    r"^[ \t]*Załączniki?[ \t]+do[ \t]+(?:rozporządzenia|obwieszczenia|uchwały|zarządzenia|ustawy)\b",
    re.MULTILINE,
)

LEADER = re.compile(r"\.{5,}|…{2,}|_{5,}")
# Box glyphs as text, plus the Private Use Area where symbol fonts put them.
BOX = re.compile(r"[□☐☑☒■▪◻◼❑❒\ue000-\uf8ff]")
FORM_WORDS = re.compile(
    r"\b(WNIOSEK|FORMULARZ|DEKLARACJA|ZGŁOSZENIE|OŚWIADCZENIE|INFORMACJA|WZÓR)\b"
)
SIGNATURE = re.compile(r"podpis", re.IGNORECASE)

# Journal PDFs from about 2005-2010 map Polish letters to the wrong glyphs
# ("Za∏àcznik" for "Załącznik"); "∏" never occurs in correct text.
LEGACY_MARK = "\u220f"
LEGACY_GLYPHS = str.maketrans("\u220f\u00e0\u00ca\u00b4\u02dd\u0192\u00e7", "łąśężńć")


@dataclass(frozen=True)
class Act:
    eli: str
    publisher: str
    year: int
    pos: int
    title: str
    act_type: str
    promulgation: str | None
    queries: tuple[str, ...]


@dataclass
class Features:
    pages: int = 0
    text_chars: int = 0
    leaders: int = 0
    boxes: int = 0
    paths: int = 0
    images: int = 0
    form_words: list[str] = field(default_factory=list)
    signature: bool = False

    @property
    def is_raster(self) -> bool:
        # Only the journal header is text; the form itself is an image.
        return self.images >= self.pages and self.text_chars < 200 * self.pages

    @property
    def is_form_candidate(self) -> bool:
        if self.is_raster:
            return True
        return (
            self.leaders >= 5
            or self.boxes >= 3
            or self.paths >= 40 * self.pages
            or (self.signature and bool(self.form_words))
        )


def attachment_starts(page_texts: list[str]) -> list[int]:
    """Indices of pages that open a new attachment.

    Labels repeat on every page of a multi-page attachment and split numbers
    leave stray small ones, so a page starts a segment only when its highest
    number grows, or on the first unnumbered label.
    """
    starts: list[int] = []
    current: int | None = None
    for i, text in enumerate(page_texts):
        numbers = [int(n) for n in NUMBERED_LABEL.findall(text)]
        if numbers and max(numbers) > (current or 0):
            current = max(numbers)
            starts.append(i)
        elif current is None and GENERIC_LABEL.search(text):
            current = 0
            starts.append(i)
    return starts


def attachment_label(text: str) -> str | None:
    m = NUMBERED_LABEL.search(text) or GENERIC_LABEL.search(text)
    return m.group(0).strip() if m else None


def segments(starts: list[int], page_count: int) -> list[range]:
    """Split pages into attachment ranges, each ending before the next start."""
    bounds = [*starts, page_count]
    return [range(a, b) for a, b in itertools.pairwise(bounds) if b > a]


def text_features(text: str) -> Features:
    found = sorted({m.group(1) for m in FORM_WORDS.finditer(text)})
    return Features(
        text_chars=len(text.strip()),
        leaders=len(LEADER.findall(text)),
        boxes=len(BOX.findall(text)),
        form_words=found,
        signature=bool(SIGNATURE.search(text)),
    )


def slug(eli: str) -> str:
    return eli.replace("/", "_")


def search(client: httpx.Client, query: str, page_size: int = 500) -> Iterator[dict]:
    offset = 0
    while True:
        r = get(
            client,
            f"{API}/acts/search",
            params={"title": query, "inForce": 1, "limit": page_size, "offset": offset},
        )
        data = r.json()
        yield from data["items"]
        offset += data["count"]
        if data["count"] == 0 or offset >= data["totalCount"]:
            return


def find_acts(client: httpx.Client, queries: tuple[str, ...]) -> list[Act]:
    by_eli: dict[str, Act] = {}
    for q in queries:
        for item in search(client, q):
            if not item.get("textPDF") or NON_FORM_TITLE.search(item["title"]):
                continue
            eli = item["ELI"]
            prev = by_eli.get(eli)
            by_eli[eli] = Act(
                eli=eli,
                publisher=item["publisher"],
                year=item["year"],
                pos=item["pos"],
                title=item["title"],
                act_type=item["type"],
                promulgation=item.get("promulgation"),
                queries=(*prev.queries, q) if prev else (q,),
            )
    return sorted(by_eli.values(), key=lambda a: (a.year, a.publisher, a.pos), reverse=True)


def get(client: httpx.Client, url: str, params: dict | None = None) -> httpx.Response:
    """GET that waits out network outages instead of failing the act."""
    for wait in BACKOFF:
        try:
            r = client.get(url, params=params)
            r.raise_for_status()
            return r
        except httpx.TransportError as exc:
            print(f"network: {exc}; retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    r = client.get(url, params=params)
    r.raise_for_status()
    return r


def fetch_pdf(client: httpx.Client, act: Act, raw_dir: Path, delay: float) -> bytes:
    path = raw_dir / f"{slug(act.eli)}.pdf"
    if path.exists():
        return path.read_bytes()
    r = get(client, f"{API}/acts/{act.publisher}/{act.year}/{act.pos}/text.pdf")
    if not r.content.startswith(b"%PDF"):
        raise ValueError(f"not a PDF: {r.headers.get('content-type')}")
    path.write_bytes(r.content)
    time.sleep(delay)
    return r.content


def fix_legacy_text(text: str) -> str:
    text = text.replace("\ufffe", "")  # stray non-character inside words
    return text.translate(LEGACY_GLYPHS) if LEGACY_MARK in text else text


def page_text(page: pdfium.PdfPage) -> str:
    textpage = page.get_textpage()
    try:
        return fix_legacy_text(textpage.get_text_range())
    finally:
        textpage.close()


def count_objects(page: pdfium.PdfPage, kind: int) -> int:
    return sum(1 for _ in page.get_objects(filter=(kind,), max_depth=2))


def cut(pdf: pdfium.PdfDocument, pages: range) -> bytes:
    out = pdfium.PdfDocument.new()
    try:
        out.import_pages(pdf, list(pages))
        buf = io.BytesIO()
        out.save(buf)
        return buf.getvalue()
    finally:
        out.close()


def process(act: Act, data: bytes, forms_dir: Path) -> Iterator[dict]:
    pdf = pdfium.PdfDocument(data)
    try:
        texts = [page_text(pdf[i]) for i in range(len(pdf))]
        starts = attachment_starts(texts)
        for n, pages in enumerate(segments(starts, len(pdf)), start=1):
            feats = text_features("\n".join(texts[i] for i in pages))
            feats.pages = len(pages)
            feats.paths = sum(count_objects(pdf[i], pdfium_c.FPDF_PAGEOBJ_PATH) for i in pages)
            feats.images = sum(count_objects(pdf[i], pdfium_c.FPDF_PAGEOBJ_IMAGE) for i in pages)
            blob = cut(pdf, pages)
            name = f"{slug(act.eli)}_z{n:02d}.pdf"
            (forms_dir / name).write_bytes(blob)
            yield {
                "source": "eli",
                "eli": act.eli,
                "title": act.title,
                "act_type": act.act_type,
                "promulgation": act.promulgation,
                "queries": list(act.queries),
                "url": f"{API}/acts/{act.publisher}/{act.year}/{act.pos}/text.pdf",
                "attachment": n,
                "label": attachment_label(texts[pages.start]),
                "pages": [pages.start + 1, pages.stop],
                "path": f"forms/{name}",
                "sha256": hashlib.sha256(blob).hexdigest(),
                "size": len(blob),
                "features": asdict(feats),
                "is_raster": feats.is_raster,
                "is_form_candidate": feats.is_form_candidate,
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
    finally:
        pdf.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("corpus"))
    parser.add_argument("--limit", type=int, default=0, help="max acts, 0 = all")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between downloads")
    args = parser.parse_args(argv)

    root: Path = args.out / "eli"
    raw_dir, forms_dir = root / "raw", root / "forms"
    raw_dir.mkdir(parents=True, exist_ok=True)
    forms_dir.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": USER_AGENT}
    transport = httpx.HTTPTransport(retries=3)
    with httpx.Client(
        headers=headers, timeout=60, follow_redirects=True, transport=transport
    ) as client:
        acts = find_acts(client, QUERIES)
        if args.limit:
            acts = acts[: args.limit]
        print(f"acts: {len(acts)}", file=sys.stderr)

        stats = {
            "acts": len(acts),
            "no_attachment": 0,
            "errors": 0,
            "attachments": 0,
            "rasters": 0,
            "forms": 0,
        }
        with (root / "manifest.jsonl").open("w", encoding="utf-8") as manifest:
            for i, act in enumerate(acts, start=1):
                try:
                    rows = list(
                        process(act, fetch_pdf(client, act, raw_dir, args.delay), forms_dir)
                    )
                except (httpx.HTTPError, ValueError, pdfium.PdfiumError) as exc:
                    stats["errors"] += 1
                    print(f"[{i}/{len(acts)}] {act.eli} error: {exc}", file=sys.stderr)
                    continue
                if not rows:
                    stats["no_attachment"] += 1
                for row in rows:
                    manifest.write(json.dumps(row, ensure_ascii=False) + "\n")
                stats["attachments"] += len(rows)
                stats["forms"] += sum(r["is_form_candidate"] for r in rows)
                stats["rasters"] += sum(r["is_raster"] for r in rows)
                print(f"[{i}/{len(acts)}] {act.eli}: {len(rows)} attachments", file=sys.stderr)

    (root / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
