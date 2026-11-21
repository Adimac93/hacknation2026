"""Generate outputs/ by sending each form to digitize through the running service (CLAUDE.md).

Development tool only, never part of the image. Start the API first (docker compose up, or
`uv run uvicorn formcompiler.main:app` in api/), then from the repo root:

    uv run --project api python devtools/generate_outputs.py [--api URL] [--format pdf]

For every form folder 3, 4, 6, 7, 8 and 9 in Docs/ it POSTs one blank to /api/v1/forms?details=true,
writes the form JSON to outputs/<number>-<slug of the Docs/ folder name>.json (stable across modes)
and a summary of all runs to outputs/README.md (mode, model, lint issues,
timings). Files in outputs/ are never edited by hand.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

from formcompiler.compiler import slugify

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "Docs"
OUTPUTS = ROOT / "outputs"
FORMS = ("3", "4", "6", "7", "8", "9")
FOLDER_SUFFIX = " - formularze do cyfryzacji"


def blank(number: str, fmt: str) -> Path:
    folder = next(DOCS.glob(f"{number}. *"))
    for path in sorted(folder.iterdir()):
        if path.suffix.lower().lstrip(".") == fmt:
            return path
    raise SystemExit(f"form {number}: no .{fmt} file in {folder.name}")


def output_name(number: str) -> str:
    """Stable file name from the Docs/ folder, independent of the title the service derives."""
    folder = next(DOCS.glob(f"{number}. *")).name
    title = folder.removeprefix(f"{number}. ").removesuffix(FOLDER_SUFFIX)
    return f"{number}-{slugify(title).replace('_', '-')}.json"


def run(client: httpx.Client, api: str, path: Path, token: str | None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with path.open("rb") as handle:
        response = client.post(
            f"{api}/api/v1/forms",
            params={"details": "true"},
            files={"file": (path.name, handle)},
            headers=headers,
        )
    if response.status_code != 200:
        raise SystemExit(f"{path.name}: HTTP {response.status_code} {response.text[:300]}")
    body: dict[str, Any] = response.json()
    return body


def summary_row(number: str, out: Path, path: Path, report: dict[str, Any]) -> str:
    lint = report.get("lint", [])
    errors = sum(1 for issue in lint if issue.get("severity") == "error")
    total = sum(report.get("timings_ms", {}).values())
    model = report.get("model") or "—"
    fields = len(report.get("fields", []))
    return (
        f"| {number} | [`{out.name}`]({out.name}) | `{path.suffix.lstrip('.').lower()}` "
        f"| {report.get('mode')} | {model} | {fields} | {errors} | {len(lint)} | {total} |"
    )


def _merged_rows(new_rows: list[str]) -> list[str]:
    """New rows replace the same form's old row; forms not run this time keep their last row."""
    readme = OUTPUTS / "README.md"
    old = readme.read_text(encoding="utf-8").splitlines() if readme.exists() else []
    by_form = {r.split("|")[1].strip(): r for r in old if r.startswith("| ") and r[2:3].isdigit()}
    by_form.update({r.split("|")[1].strip(): r for r in new_rows})
    return [by_form[k] for k in sorted(by_form, key=int)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--format", default="pdf", help="which blank to send, by extension")
    parser.add_argument("--token", default=None, help="JWT, when AUTH_ENABLED=true")
    parser.add_argument("--forms", nargs="*", default=list(FORMS))
    args = parser.parse_args()

    OUTPUTS.mkdir(exist_ok=True)
    rows: list[str] = []
    with httpx.Client(timeout=600) as client:
        health = client.get(f"{args.api}/health").json()
        for number in args.forms:
            path = blank(number, args.format.lower())
            body = run(client, args.api, path, args.token)
            form, report = body["form"], body["report"]
            out = OUTPUTS / output_name(number)
            out.write_text(json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            rows.append(summary_row(number, out, path, report))
            print(f"{number}: {out.relative_to(ROOT)} ({report.get('mode')})", file=sys.stderr)

    lines = [
        "# Wynikowe JSON-y",
        "",
        "Wygenerowane usługą przez `devtools/generate_outputs.py`. Plików nie poprawiamy ręcznie.",
        "",
        f"Usługa: `{json.dumps(health, ensure_ascii=False)}`",
        "",
        "| Formularz | Plik | Wejście | Tryb | Model | Pola | Błędy lintera | Uwagi lintera "
        "| Czas [ms] |",
        "|---|---|---|---|---|---|---|---|---|",
        *_merged_rows(rows),
        "",
    ]
    (OUTPUTS / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
