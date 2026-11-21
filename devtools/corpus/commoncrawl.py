# /// script
# requires-python = ">=3.14"
# dependencies = ["duckdb>=1.4", "httpx>=0.28", "warcio>=1.7"]
# ///
"""Collect Polish office form documents from the Common Crawl archive.

`index` queries the columnar URL index (Parquet over HTTPS, only the row
groups covering `.pl`) for PDF and office documents whose URL path names a
form. `fetch` reads each document from the WARC archive with a range request,
so municipal servers are never hit. Offline research tool, not part of the
service.

    uv run devtools/corpus/commoncrawl.py index --crawls 6 --out corpus
    uv run devtools/corpus/commoncrawl.py fetch --out corpus
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import httpx
from warcio.archiveiterator import ArchiveIterator

DATA = "https://data.commoncrawl.org"
USER_AGENT = "guppy-corpus/0.1 (HackNation 2026 research)"
BACKOFF = (10, 30, 60, 120, 300)
INDEX_BACKOFF = (60, 300, 600, 1200, 1800)

MIMES = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
    "application/rtf",
    "text/rtf",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.oasis.opendocument.spreadsheet",
)
# Matched against the lower-cased URL path, with and without Polish letters.
FORM_PATH = (
    r"wniosek|wnioski|wniosku|formularz|druk|deklaracj|zgloszeni|zgłoszeni"
    r"|wzor|wzór|oswiadczeni|oświadczeni"
)

# Form types from the task, matched against the lower-cased URL.
FORM_TYPES = {
    "numer_porzadkowy": r"numer\w*.porz|porzadkow|porządkow",
    "zaswiadczenie": r"zaswiadcz|zaświadcz",
    "swietlica": r"swietlic|świetlic",
    "nadplata": r"nadplat|nadpłat",
    "pas_drogowy": r"pas\w*.drog|zajeci\w*.pas|zajęci\w*.pas",
    "psy_agresywne": r"agresywn|ras\w*.ps",
    "odpady": r"odpad|smieci|śmieci",
    "stypendium_sportowe": r"stypendi\w*.sport|sportow\w*.stypendi|nagrod\w*.sport",
}
_FORM_TYPE_RES = {k: re.compile(v) for k, v in FORM_TYPES.items()}

# Public offices: gov.pl, BIP portals, municipalities, counties, social services.
OFFICIAL_HOST = re.compile(
    r"\.gov\.pl$|(?:^|[.-])(?:bip|gmina|gminy|powiat|starostwo|urzad|umig|ugm|mops|gops)(?:[.-]|$)"
    r"|^u[gm]\.|^www\.u[gm]\."
)


def form_type(url: str) -> str | None:
    low = url.lower()
    return next((k for k, rx in _FORM_TYPE_RES.items() if rx.search(low)), None)


def is_official(host: str) -> bool:
    return not host.endswith(".edu.pl") and bool(OFFICIAL_HOST.search(host))


def detect_kind(data: bytes) -> str | None:
    """File type from the signature, never from the URL or the server's MIME."""
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "ole"  # binary DOC or XLS; Tika tells them apart
    if data.lstrip().startswith(b"{\\rtf"):
        return "rtf"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = set(zf.namelist())
                if "mimetype" in names:
                    mime = zf.read("mimetype").decode("ascii", "replace")
                    return {
                        "application/vnd.oasis.opendocument.text": "odt",
                        "application/vnd.oasis.opendocument.spreadsheet": "ods",
                    }.get(mime)
        except zipfile.BadZipFile:
            return None
        if "word/document.xml" in names:
            return "docx"
        if "xl/workbook.xml" in names:
            return "xlsx"
    return None


def latest_crawls(client: httpx.Client, n: int) -> list[str]:
    r = get(client, "https://index.commoncrawl.org/collinfo.json")
    return [c["id"] for c in r.json()[:n]]


def get(
    client: httpx.Client,
    url: str,
    headers: dict[str, str] | None = None,
    backoff: tuple[int, ...] = BACKOFF,
) -> httpx.Response:
    """GET that waits out outages and throttling (CloudFront answers 403 or 503)."""
    for wait in (*backoff, None):
        try:
            r = client.get(url, headers=headers)
            if r.status_code not in (403, 429, 503) or wait is None:
                r.raise_for_status()
                return r
            reason = f"HTTP {r.status_code}"
        except httpx.TransportError as exc:
            if wait is None:
                raise
            reason = str(exc)
        print(f"{reason}; retry in {wait}s", file=sys.stderr)
        time.sleep(wait)
    raise AssertionError("unreachable")


def pl_files(
    con: duckdb.DuckDBPyConnection, client: httpx.Client, crawl: str, cache: Path
) -> list[str]:
    """Index files whose SURT range covers `pl,`, cached per crawl.

    Footers are read one file at a time: a burst over all 300 files gets the
    address blocked by CloudFront for about 20 minutes.
    """
    if cache.exists():
        return cache.read_text().split()
    paths = gzip.decompress(
        get(client, f"{DATA}/crawl-data/{crawl}/cc-index-table.paths.gz").content
    )
    urls = [f"{DATA}/{p}" for p in paths.decode().split() if "subset=warc" in p]
    files = []
    for url in urls:
        for wait in (*INDEX_BACKOFF, None):
            try:
                hit = con.execute(
                    "select count(*) from parquet_metadata(?) where path_in_schema = 'url_surtkey'"
                    " and stats_max_value >= 'pl,' and stats_min_value < 'pl-'",
                    [url],
                ).fetchall()[0][0]
                break
            except duckdb.HTTPException as exc:
                if wait is None:
                    raise
                print(f"{exc}; retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
        if hit:
            files.append(url)
        time.sleep(0.5)
    cache.write_text("\n".join(files))
    return files


def download(client: httpx.Client, url: str, dest: Path) -> None:
    """Fetch a whole file with one streaming GET, resuming a partial download.

    CloudFront tolerates a few long transfers but blocks the address after
    dense bursts of small range requests, which is what a remote scan sends.
    """
    if dest.exists():
        return
    part = dest.with_name(dest.name + ".part")
    for wait in (*INDEX_BACKOFF, None):
        have = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            with client.stream("GET", url, headers=headers, timeout=300) as r:
                r.raise_for_status()
                with part.open("ab" if r.status_code == 206 else "wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
            part.rename(dest)
            return
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else 0
            if wait is None or status not in (0, 403, 429, 503):
                raise
            print(f"{dest.name}: {exc}; retry in {wait}s", file=sys.stderr)
            time.sleep(wait)


def index_crawl(con: duckdb.DuckDBPyConnection, crawl: str, files: list[Path], dest: Path) -> None:
    """Write one crawl's candidates from local index files to `dest`."""
    tmp = dest.with_suffix(".tmp")
    con.execute(
        f"""
        copy (
            select ? crawl, url, url_host_name host, content_mime_detected mime,
                   content_digest digest, warc_filename, warc_record_offset,
                   warc_record_length, fetch_time
            from read_parquet(?)
            where url_surtkey >= 'pl,' and url_surtkey < 'pl-' and fetch_status = 200
              and list_contains(?, content_mime_detected)
              and regexp_matches(lower(url_path), ?)
        ) to '{tmp}' (format parquet)
        """,
        [crawl, [str(f) for f in files], list(MIMES), FORM_PATH],
    )
    tmp.rename(dest)


def cmd_index(args: argparse.Namespace) -> int:
    out: Path = args.out / "cc"
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET http_retries = 8; SET http_retry_wait_ms = 2000;")
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=120) as client:
        crawls = args.crawl or latest_crawls(client, args.crawls)
        for crawl in crawls:
            dest = out / f"cand-{crawl}.parquet"
            if dest.exists():
                continue
            t = time.monotonic()
            urls = pl_files(con, client, crawl, out / f"files-{crawl}.txt")
            local_dir = out / "index" / crawl
            local_dir.mkdir(parents=True, exist_ok=True)
            local = [local_dir / url.rsplit("/", 1)[1] for url in urls]
            for url, path in zip(urls, local, strict=True):
                download(client, url, path)
            index_crawl(con, crawl, local, dest)
            if not args.keep_index:
                for path in local:
                    path.unlink()
            print(f"{crawl}: {len(urls)} files, {time.monotonic() - t:.0f}s", file=sys.stderr)

    # One row per content digest, the latest capture wins.
    parts = [str(out / f"cand-{c}.parquet") for c in crawls]
    con.execute(f"create table cand as select * from read_parquet({parts!r})")
    con.execute(
        f"copy (select * from cand qualify row_number() over"
        f" (partition by digest order by fetch_time desc) = 1 order by host, url)"
        f" to '{out / 'candidates.parquet'}' (format parquet)"
    )
    total, unique = con.execute("select count(*), count(distinct digest) from cand").fetchall()[0]
    print(json.dumps({"crawls": crawls, "rows": total, "unique": unique}), file=sys.stderr)
    return 0


def read_record(client: httpx.Client, row: dict) -> tuple[bytes, bool]:
    """Payload of one WARC record and whether the crawler truncated it."""
    start = row["warc_record_offset"]
    end = start + row["warc_record_length"] - 1
    r = get(
        client,
        f"{DATA}/{row['warc_filename']}",
        headers={"Range": f"bytes={start}-{end}"},
        backoff=INDEX_BACKOFF,
    )
    for record in ArchiveIterator(io.BytesIO(r.content)):
        if record.rec_type == "response":
            truncated = bool(record.rec_headers.get_header("WARC-Truncated"))
            return record.content_stream().read(), truncated
    raise ValueError("no response record")


def select_rows(path: Path, everything: bool) -> list[dict]:
    rows = duckdb.sql(f"select * from read_parquet('{path}')").fetchall()
    cols = [
        "crawl", "url", "host", "mime", "digest",
        "warc_filename", "warc_record_offset", "warc_record_length", "fetch_time",
    ]  # fmt: skip
    picked = []
    for values in rows:
        row = dict(zip(cols, values, strict=True))
        row["form_type"] = form_type(row["url"])
        row["official"] = is_official(row["host"])
        if everything or row["official"] or row["form_type"]:
            picked.append(row)
    # Task form types first, so an interrupted run has the most useful files.
    picked.sort(key=lambda r: (r["form_type"] is None, r["host"], r["url"]))
    return picked


def fetch_one(client: httpx.Client, row: dict, forms_dir: Path) -> dict:
    base = {
        "source": "commoncrawl",
        "crawl": row["crawl"],
        "url": row["url"],
        "host": row["host"],
        "mime": row["mime"],
        "form_type": row["form_type"],
        "official": row["official"],
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    try:
        data, truncated = read_record(client, row)
    except (httpx.HTTPError, ValueError) as exc:
        return {**base, "error": str(exc)}
    kind = detect_kind(data)
    sha = hashlib.sha256(data).hexdigest()
    result = {**base, "kind": kind, "sha256": sha, "size": len(data), "truncated": truncated}
    if kind and not truncated:
        name = f"{sha[:16]}.{kind}"
        (forms_dir / name).write_bytes(data)
        result["path"] = f"forms/{name}"
    return result


def done_urls(manifest: Path) -> set[str]:
    if not manifest.exists():
        return set()
    # Failed fetches are retried on the next run.
    rows = (json.loads(line) for line in manifest.open(encoding="utf-8"))
    return {r["url"] for r in rows if "error" not in r}


def cmd_fetch(args: argparse.Namespace) -> int:
    root: Path = args.out / "cc"
    forms_dir = root / "forms"
    forms_dir.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest.jsonl"
    seen = done_urls(manifest)
    rows = [r for r in select_rows(root / "candidates.parquet", args.all) if r["url"] not in seen]
    if args.limit:
        rows = rows[: args.limit]
    print(f"to fetch: {len(rows)} (already done: {len(seen)})", file=sys.stderr)

    stats = {"fetched": 0, "saved": 0, "truncated": 0, "unknown": 0, "errors": 0}
    with (
        httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=120) as client,
        ThreadPoolExecutor(args.workers) as pool,
        manifest.open("a", encoding="utf-8") as out,
    ):
        results: Iterable[dict] = pool.map(lambda r: fetch_one(client, r, forms_dir), rows)
        for i, res in enumerate(results, start=1):
            out.write(json.dumps(res, ensure_ascii=False) + "\n")
            stats["fetched"] += 1
            stats["errors"] += "error" in res
            stats["truncated"] += bool(res.get("truncated"))
            stats["unknown"] += "error" not in res and res.get("kind") is None
            stats["saved"] += "path" in res
            if i % 500 == 0:
                out.flush()
                print(f"[{i}/{len(rows)}] {json.dumps(stats)}", file=sys.stderr)
    (root / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats), file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("index", help="query the URL index into candidates.parquet")
    p.add_argument("--out", type=Path, default=Path("corpus"))
    p.add_argument("--crawls", type=int, default=6, help="number of latest crawls")
    p.add_argument("--crawl", action="append", help="explicit crawl id, repeatable")
    p.add_argument("--keep-index", action="store_true", help="keep downloaded index files")
    p.set_defaults(func=cmd_index)
    p = sub.add_parser("fetch", help="download candidates from WARC files")
    p.add_argument("--out", type=Path, default=Path("corpus"))
    p.add_argument("--all", action="store_true", help="also non-official hosts without a type")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=2)
    p.set_defaults(func=cmd_fetch)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
