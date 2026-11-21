"""Format matrix: send every blank of forms 3-9 in every format and tabulate the results.

Development tool only, never part of the image. Standard library only, so it runs on a bare
python3 next to the docker stack:

    python3 devtools/format_matrix.py --api http://127.0.0.1:8080
    uv run --project api python devtools/format_matrix.py --api http://127.0.0.1:8000

For every folder `Docs/[3-9]. *` and every blank in it (no reference JSON, no "wizualizacja"
document) it POSTs the file to /api/v1/forms?details=true and records HTTP status, wall time,
report mode, field count, lint errors and title. Requests are paced (nginx allows 10 POST per
minute per IP) and a 429 is retried after its Retry-After. The result is a Markdown report,
by default research/08-macierz-formatow.md.
"""

import argparse
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SKIP_SUFFIXES = {".json"}
SKIP_NAME_PART = "wizualizacja"
DASH = "\u2013"  # en dash for ranges in the Polish report


@dataclass
class Row:
    form: str
    path: Path
    status: int
    seconds: float
    mode: str = "—"
    fields: int | None = None
    lint_errors: int | None = None
    lint_total: int | None = None
    pages: int | None = None
    title: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == 200 and self.lint_errors == 0


def blanks(docs: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    for folder in sorted(docs.glob("[3-9]. *")):
        number = folder.name.split(".", 1)[0]
        for path in sorted(folder.iterdir(), key=lambda p: (p.suffix.lower(), p.name)):
            if path.suffix.lower() in SKIP_SUFFIXES or SKIP_NAME_PART in path.name.lower():
                continue
            found.append((number, path))
    return found


def multipart(path: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    body = head + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def post(api: str, path: Path, token: str | None) -> tuple[int, dict[str, Any], dict[str, str]]:
    body, content_type = multipart(path)
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{api}/api/v1/forms?details=true", data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return response.status, json.loads(response.read()), dict(response.headers)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"detail": raw[:200].decode(errors="replace")}
        return error.code, payload, dict(error.headers)


def measure(api: str, number: str, path: Path, token: str | None) -> Row:
    while True:
        started = time.monotonic()
        status, payload, headers = post(api, path, token)
        seconds = time.monotonic() - started
        if status != 429:
            break
        wait = int(headers.get("Retry-After", "10") or 10)
        print(f"  429, retry in {wait} s", file=sys.stderr)
        time.sleep(wait)
    if status != 200:
        detail = str(payload.get("title") or payload.get("detail") or "")[:80]
        return Row(number, path, status, seconds, error=detail)
    form, report = payload["form"], payload["report"]
    lint = report.get("lint", [])
    return Row(
        number,
        path,
        status,
        seconds,
        mode=report.get("mode", "—"),
        fields=len(report.get("fields", [])),
        lint_errors=sum(1 for issue in lint if issue.get("severity") == "error"),
        lint_total=len(lint),
        pages=len(report.get("document", {}).get("pages", [])),
        title=form.get("title", ""),
    )


def machine() -> str:
    cpu = platform.processor() or platform.machine()
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return f"{platform.system()} {platform.machine()}, {cpu}, {os.cpu_count()} rdzeni CPU"


def cell(value: object) -> str:
    return "—" if value is None else str(value).replace("|", "\\|")


def render(rows: list[Row], api: str, health: dict[str, Any], started: datetime) -> str:
    mode = (
        "model (LLM)" if health.get("llm_enabled") else "reguły (bez modelu, `LLM_ENABLED=false`)"
    )
    ok200 = sum(1 for r in rows if r.status == 200)
    errors = sum(r.lint_errors or 0 for r in rows)
    slowest = max(rows, key=lambda r: r.seconds)
    lines = [
        "# Macierz formatów: jeden formularz, osiem formatów wejścia",
        "",
        f"Każdy blankiet z folderów `Docs/3.`{DASH}`Docs/9.` (bez wzorcowego JSON-a i bez "
        "dokumentu „wizualizacja” w folderze 5) wysłaliśmy do działającej usługi przez "
        "`POST /api/v1/forms?details=true`. Skrypt: `devtools/format_matrix.py`, "
        "wynik niepoprawiany ręcznie.",
        "",
        f"- Data: {started:%Y-%m-%d %H:%M} UTC",
        f"- Maszyna: {machine()}",
        f"- Usługa: stos `docker compose` (web + api + tika), adres `{api}`",
        f"- Tryb: {mode}",
        "- Czas: zegar ścienny po stronie klienta, cały request przez nginx "
        "(wczytanie, OCR lub Tika, heurystyki, kompilacja, linter)",
        "",
        f"**Razem:** plików {len(rows)}, HTTP 200: {ok200}, błędy lintera: {errors}, "
        f"najwolniejszy plik: `{slowest.path.name}` ({slowest.seconds:.1f} s).",
        "",
        "## Podsumowanie na formularz",
        "",
        f"| Formularz | Formaty OK | Pola (min{DASH}maks) | Tytuły zgodne | Najwolniejszy format |",
        "|---|---|---|---|---|",
    ]
    for number in sorted({r.form for r in rows}):
        group = [r for r in rows if r.form == number]
        good = [r for r in group if r.ok]
        counts = [r.fields for r in group if r.fields is not None]
        titles = {r.title for r in group if r.status == 200}
        slow = max(group, key=lambda r: r.seconds)
        span = f"{min(counts)}{DASH}{max(counts)}" if counts else "—"
        same = "tak" if len(titles) == 1 else f"nie (wariantów: {len(titles)})"
        lines.append(
            f"| {number} | {len(good)}/{len(group)} | {span} | {same} "
            f"| `{slow.path.suffix.lstrip('.').lower()}` ({slow.seconds:.1f} s) |"
        )
    lines += [
        "",
        "## Wszystkie pliki",
        "",
        "| Formularz | Plik | HTTP | Czas [s] | Tryb | Strony | Pola | Błędy lintera "
        "| Uwagi lintera | Tytuł |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        title = r.title or (f"_{r.error}_" if r.error else "")
        lines.append(
            f"| {r.form} | `{cell(r.path.name)}` | {r.status} | {r.seconds:.1f} | {r.mode} "
            f"| {cell(r.pages)} | {cell(r.fields)} | {cell(r.lint_errors)} "
            f"| {cell(r.lint_total)} | {cell(title)} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8080")
    parser.add_argument("--docs", type=Path, default=ROOT / "Docs")
    parser.add_argument("--out", type=Path, default=ROOT / "research" / "08-macierz-formatow.md")
    parser.add_argument("--pace", type=float, default=6.0, help="seconds between requests")
    parser.add_argument("--token", default=None, help="JWT, when AUTH_ENABLED=true")
    args = parser.parse_args()

    with urllib.request.urlopen(f"{args.api}/health", timeout=30) as response:
        health: dict[str, Any] = json.loads(response.read())
    started = datetime.now(UTC)
    files = blanks(args.docs)
    rows: list[Row] = []
    for index, (number, path) in enumerate(files, 1):
        if index > 1:
            time.sleep(args.pace)
        row = measure(args.api, number, path, args.token)
        rows.append(row)
        print(
            f"[{index}/{len(files)}] {number} {path.name}: {row.status} {row.seconds:.1f}s "
            f"fields={row.fields} errors={row.lint_errors}",
            file=sys.stderr,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(rows, args.api, health, started), encoding="utf-8")
    print(f"written {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
