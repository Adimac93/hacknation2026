"""Regenerate api/src/formcompiler/data/sections.json from the organiser's reference forms.

Development tool only: the service reads the generated JSON and never touches Docs/.
Run from api/: uv run python ../devtools/extract_sections.py
"""

import json
from pathlib import Path

from formcompiler.decompile import decompile
from formcompiler.schema import Form

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "Docs"
OUT = ROOT / "api/src/formcompiler/data/sections.json"


def load(prefix: str) -> Form:
    path = next(DOCS.glob(f"{prefix}. */konfiguracja_*.json"))
    return Form.model_validate(json.loads(path.read_text(encoding="utf-8")))


def main() -> None:
    ref1, ref5 = decompile(load("1")), decompile(load("5"))
    data_page = ref5.pages[0]
    library = {
        "source": "Docs/5 (data, contact, finish pages; URZAD addressee), Docs/1 (ORGAN addressee)",
        "data_page_title": data_page.title,
        "addressee": {
            "URZAD": data_page.sections[0].model_dump(mode="json", exclude_defaults=True),
            "ORGAN": ref1.pages[0].sections[0].model_dump(mode="json", exclude_defaults=True),
        },
        "applicant": [
            s.model_dump(mode="json", exclude_defaults=True) for s in data_page.sections[1:]
        ],
        "contact": ref5.pages[-2].model_dump(mode="json", exclude_defaults=True),
        "finish": ref5.pages[-1].model_dump(mode="json", exclude_defaults=True),
    }
    OUT.write_text(json.dumps(library, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
