"""Copy the organiser's sample blanks into web/public/samples/ for the demo's sample picker.

Development tool only. From the repo root: `python3 devtools/build_samples.py`. Writes
web/public/samples/<form>/<slug>.<ext> (ASCII names, safe in URLs) and web/public/samples/index.json.
Docs/ itself is never modified; identical files share one blob in git.
"""

import json
import re
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "Docs"
OUT = ROOT / "web" / "public" / "samples"
BLANKS = {".pdf", ".doc", ".docx", ".ods", ".xlsx", ".jpg", ".jpeg", ".jpe", ".png"}
SUFFIX = re.compile(r"\s+-\s+(formularze do cyfryzacji|materiał referencyjny.*)$")
POLISH = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text.translate(POLISH)).encode("ascii", "ignore")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.decode().lower()).strip("-")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    forms = []
    for folder in sorted(DOCS.glob("[1-9]. *"), key=lambda p: int(p.name.split(".")[0])):
        number, _, rest = folder.name.partition(". ")
        title = SUFFIX.sub("", rest).strip()
        reference = "materiał referencyjny" in rest
        files = []
        for path in sorted(folder.iterdir(), key=lambda p: p.suffix.lower()):
            ext = path.suffix.lower()
            if ext not in BLANKS or "wizualizacja" in path.name.lower():
                continue
            target = OUT / number / f"{slug(path.stem)}{ext}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            files.append(
                {
                    "format": ext.lstrip(".").upper(),
                    "path": f"samples/{number}/{target.name}",
                    "name": path.name,
                    "bytes": path.stat().st_size,
                }
            )
        forms.append({"form": number, "title": title, "reference": reference, "files": files})
    (OUT / "index.json").write_text(
        json.dumps({"forms": forms}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"{sum(len(f['files']) for f in forms)} files in {len(forms)} forms -> {OUT}")


if __name__ == "__main__":
    main()
