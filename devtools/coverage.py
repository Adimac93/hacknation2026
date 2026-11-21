"""Field coverage of the organiser's reference e-forms 1 and 5, reproduced from the paper blanks.

Development tool only, never part of the image. Run from api/:

    uv run python ../devtools/coverage.py [--llm] [--runs N] [--formats pdf docx png]

Rules mode uses Settings(_env_file=None); --llm reads LLM_* from the repo .env and runs the PDF
blank in model mode twice per form, once with the production prompt ("full", whose few-shot
examples are the two references themselves) and once leaving the evaluated form out of the
examples ("loo"). DOCX needs Apache Tika at --tika-url; PNG goes through the local OCR.

Matching: subject fields are the fields on the pages between the standard data page and the
contact page, in both the reference and our output, without TEXT_BLOCK and INFO_SECTION. Labels
are normalised to slugs (lower case, ASCII, words only) and compared with difflib's ratio; pairs
are matched greedily one-to-one from the most similar down to MATCH_THRESHOLD (shared with
compare_models.py). Recall = matched / reference fields, precision = matched / our fields.
"""

import argparse
import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from compare_models import DOCS, GOLD, MATCH_THRESHOLD, Gold, similarity

from formcompiler import llm, pipeline
from formcompiler.config import Settings
from formcompiler.decompile import decompile
from formcompiler.ir import FieldIR, FieldType, FormIR
from formcompiler.schema import Form
from formcompiler.upload import detect

NON_INPUT = frozenset({FieldType.TEXT_BLOCK, FieldType.INFO_SECTION})
APPLICANT_KEYS = frozenset({"podmiot_wniosku", "twoje_dane"})
ADDRESSEE_KEYS = frozenset(
    {"urzad_do_ktorego_jest_skladany_wniosek", "organ_do_ktorego_jest_skladany_wniosek"}
)
SECTION_NAMES = {"applicant": "wnioskodawca", "addressee": "adresat", "consents": "zgody"}


def blank(gold: Gold, fmt: str) -> Path:
    folder = next(DOCS.glob(f"{gold.name}. *"))
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() == f".{fmt}" and "wizualizacja" not in path.name:
            return path
    raise SystemExit(f"form {gold.name}: no .{fmt} blank")


def subject_fields(ir: FormIR) -> list[FieldIR]:
    """Input fields of the subject pages: everything between the data page and contact page."""
    return [
        f
        for page in ir.pages[1:-2]
        for s in page.sections
        for f in s.fields
        if f.type not in NON_INPUT
    ]


def match(expected: list[FieldIR], predicted: list[FieldIR]) -> dict[int, int]:
    """Greedy one-to-one label matching, most similar pairs first."""
    pairs = sorted(
        (
            (similarity(g.label, p.label), gi, pi)
            for gi, g in enumerate(expected)
            for pi, p in enumerate(predicted)
        ),
        reverse=True,
    )
    matched: dict[int, int] = {}
    used: set[int] = set()
    for ratio, gi, pi in pairs:
        if ratio >= MATCH_THRESHOLD and gi not in matched and pi not in used:
            matched[gi] = pi
            used.add(pi)
    return matched


def predefined(ir: FormIR) -> dict[str, Any]:
    keys = {s.key for page in ir.pages for s in page.sections}
    applicant: list[str] = next(
        (f.options for f in ir.fields() if f.key == "wybierz_w_czyim_imieniu_wnioskujesz"), []
    )
    addressee = next(
        (s for page in ir.pages for s in page.sections if s.key in ADDRESSEE_KEYS), None
    )
    return {
        "applicant": bool(keys & APPLICANT_KEYS),
        "applicant_options": applicant,
        "addressee": addressee is not None,
        "addressee_section": addressee.key if addressee else None,
        "consents": any(f.type is FieldType.CONSENT_SECTION for f in ir.fields()),
    }


def score(reference: FormIR, ours: FormIR) -> dict[str, Any]:
    expected, predicted = subject_fields(reference), subject_fields(ours)
    matched = match(expected, predicted)
    same_type = sum(expected[g].type == predicted[p].type for g, p in matched.items())
    ref_sections, our_sections = predefined(reference), predefined(ours)
    sections = {name: ref_sections[name] and our_sections[name] for name in SECTION_NAMES}
    return {
        "reference_fields": len(expected),
        "our_fields": len(predicted),
        "matched": len(matched),
        "recall": len(matched) / len(expected) if expected else 0.0,
        "precision": len(matched) / len(predicted) if predicted else 0.0,
        "same_type": same_type,
        "sections": sections,
        "addressee_same_kind": ref_sections["addressee_section"]
        == our_sections["addressee_section"],
        "applicant_options": [
            len(our_sections["applicant_options"]),
            len(ref_sections["applicant_options"]),
        ],
        "pages": len(ours.pages),
        "reference_pages": len(reference.pages),
        "matches": [
            [expected[g].label, predicted[p].label, expected[g].type, predicted[p].type]
            for g, p in sorted(matched.items())
        ],
        "missed": [f.label for i, f in enumerate(expected) if i not in matched],
        "extra": [
            f"{f.label} ({f.type})" for i, f in enumerate(predicted) if i not in matched.values()
        ],
    }


@contextmanager
def leave_out(form: str) -> Iterator[None]:
    """Removes the evaluated reference from the few-shot examples of the inventory prompt."""
    original = llm.inventory_messages
    examples = tuple(e for e in llm.EXAMPLES if e.name != f"ref{form}")

    def messages(
        document_text: str, examples_: tuple[llm.Example, ...] = examples
    ) -> tuple[str, str]:
        system, user = original(document_text, examples_)
        return system, user

    llm.inventory_messages = messages
    try:
        yield
    finally:
        llm.inventory_messages = original


def run(gold: Gold, fmt: str, settings: Settings, variant: str) -> dict[str, Any]:
    reference = decompile(
        Form.model_validate(json.loads(next(DOCS.glob(gold.reference)).read_text("utf-8")))
    )
    data = blank(gold, fmt).read_bytes()
    kind = detect(data, settings)
    if kind is None:
        raise SystemExit(f"form {gold.name} {fmt}: unrecognised file signature")
    if variant == "loo":
        with leave_out(gold.name):
            form, report = pipeline.process(data, kind, settings)
    else:
        form, report = pipeline.process(data, kind, settings)
    row = {"form": gold.name, "format": fmt, "variant": variant, "mode": report.mode}
    return row | score(reference, decompile(form))


def pct(value: float) -> str:
    return f"{value:.0%}"


def table(rows: list[dict[str, Any]]) -> str:
    head = (
        "| Formularz | Wejście | Wariant | Tryb | Pola ref. | Nasze pola | Trafione "
        "| Recall | Precision | Ten sam typ | Sekcje predef. | Podmioty (ref.) | Strony (ref.) |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [head]
    for r in rows:
        present = [SECTION_NAMES[k] for k, ok in r["sections"].items() if ok]
        same_type = f"{r['same_type']}/{r['matched']}" if r["matched"] else "—"
        lines.append(
            f"| {r['form']} | {r['format'].upper()} | {r['variant']} | {r['mode']} "
            f"| {r['reference_fields']} | {r['our_fields']} | {r['matched']} "
            f"| {pct(r['recall'])} | {pct(r['precision'])} | {same_type} "
            f"| {len(present)}/3 ({', '.join(present) or '—'}) "
            f"| {r['applicant_options'][0]} ({r['applicant_options'][1]}) "
            f"| {r['pages']} ({r['reference_pages']}) |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--llm", action="store_true", help="model mode, PDF only")
    parser.add_argument("--runs", type=int, default=2, help="model runs per form and variant")
    parser.add_argument("--formats", nargs="+", default=["pdf", "docx", "png"])
    parser.add_argument("--variants", nargs="+", default=["full", "loo"], choices=["full", "loo"])
    parser.add_argument("--tika-url", default="http://127.0.0.1:9998")
    default_out = Path(tempfile.gettempdir()) / "formcompiler-coverage.jsonl"
    parser.add_argument("--out", type=Path, default=default_out)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    if args.llm:
        settings = Settings(tika_url=args.tika_url, llm_enabled=True)
        jobs = [
            (gold, "pdf", variant)
            for variant in args.variants
            for gold in GOLD
            for _ in range(args.runs)
        ]
    else:
        settings = Settings(_env_file=None, tika_url=args.tika_url)
        jobs = [(gold, fmt, "rules") for gold in GOLD for fmt in args.formats]
    with args.out.open("a", encoding="utf-8") as log:
        for gold, fmt, variant in jobs:
            row = run(gold, fmt, settings, variant)
            row["date"] = date.today().isoformat()
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            rows.append(row)
            print(
                f"form {gold.name} {fmt} {variant}: mode={row['mode']} "
                f"{row['matched']}/{row['reference_fields']} matched, {row['our_fields']} ours",
                flush=True,
            )
    print()
    print(f"Próg dopasowania etykiet: {MATCH_THRESHOLD}; wyniki szczegółowe: {args.out}")
    print(table(rows))


if __name__ == "__main__":
    main()
