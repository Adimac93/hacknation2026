"""Licence gate for runtime dependencies (CLAUDE.md, hard rule 1; PLAN B6).

Development tool only, never part of the image. Standard library only. From the repo root:

    python3 devtools/check_licenses.py              # check, exit 1 on a disallowed licence
    python3 devtools/check_licenses.py --write      # also write research/09-licencje.md
    python3 devtools/check_licenses.py --simulate "GPL-3.0-only"   # prove the gate fails
    python3 devtools/check_licenses.py --self-test  # unit-style checks of the evaluator

Python: `uv export --no-dev` in api/ gives the runtime package set (dev dependencies are
excluded), `pip-licenses` (dev dependency of api/, MIT) reads their licence metadata.
npm: the `license` field of every package in web/package-lock.json, dev packages included.

Allowed: MIT, BSD, Apache-2.0, ISC, 0BSD, PSF; SIL OFL-1.1 only for the two font packages
(D25). An SPDX "OR" passes when one alternative is allowed, "AND" (or a classifier list
joined with ";") only when every part is. Everything else must be listed in EXCEPTIONS with
the licence verified by hand; an exception binds to the exact reported string, so a licence
change upstream fails the gate until someone looks again.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
LOCKFILE = ROOT / "web" / "package-lock.json"
REPORT = ROOT / "research" / "09-licencje.md"
GATE_COMMAND = "python3 devtools/check_licenses.py"

# Canonical allowed licences and the spellings seen in package metadata (lower case).
ALIASES: dict[str, str] = {
    "mit": "MIT",
    "mit license": "MIT",
    "bsd": "BSD",
    "bsd license": "BSD",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "3-clause bsd license": "BSD-3-Clause",
    "new bsd license": "BSD-3-Clause",
    "apache-2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache license, version 2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "isc": "ISC",
    "isc license": "ISC",
    "isc license (iscl)": "ISC",
    "0bsd": "0BSD",
    "psf-2.0": "PSF-2.0",
    "python software foundation license": "PSF-2.0",
}
FONT_LICENCE = "OFL-1.1"
FONT_PACKAGES = frozenset({"@fontsource/archivo", "@fontsource/ibm-plex-mono"})

PERMISSIVE = "permissive"
WEAK_COPYLEFT = "weak-copyleft"


@dataclass(frozen=True)
class Exception_:
    reported: str  # exact licence string the tool reports; mismatch fails the gate
    verified: str  # licence verified by hand (SPDX)
    kind: str  # PERMISSIVE: resolved, passes; WEAK_COPYLEFT: passes with a WARNING
    note: str  # Polish, goes into the report


# Packages whose reported licence is outside the allow-list, resolved by hand.
EXCEPTIONS: dict[str, Exception_] = {
    # cffi: MIT-0 is MIT without the attribution clause; permissive.
    "cffi": Exception_(
        "MIT-0",
        "MIT-0",
        PERMISSIVE,
        "MIT bez wymogu zachowania noty; licencja permisywna.",
    ),
    # pillow: MIT-CMU (HPND family), the historic PIL licence; permissive.
    "pillow": Exception_(
        "MIT-CMU", "MIT-CMU", PERMISSIVE, "Licencja PIL (rodzina HPND), permisywna."
    ),
    # numpy: core BSD-3-Clause; bundled code under 0BSD, MIT, Zlib (permissive) and CC0-1.0
    # (public domain dedication). No copyleft part.
    "numpy": Exception_(
        "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0",
        "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0",
        PERMISSIVE,
        "Rdzeń BSD-3-Clause; dołączone fragmenty na 0BSD, MIT, Zlib i CC0-1.0, bez copyleftu.",
    ),
    # pypdfium2: bindings Apache-2.0 OR BSD-3-Clause, PDFium BSD-3-Clause; the binary also
    # bundles FreeType (FTL chosen from FTL OR GPL-2.0), libjpeg-turbo (IJG, BSD-3, Zlib),
    # libpng, libtiff, zlib, lcms2 (MIT), OpenJPEG (BSD-2), HarfBuzz (MIT), ICU (Unicode-3.0),
    # abseil and highway (Apache-2.0). musl and libgcc licences apply only to musllinux wheels,
    # not to the glibc image. CC-BY-4.0 covers documentation and data files only.
    "pypdfium2": Exception_(
        "BSD-3-Clause, Apache-2.0, dependency licenses",
        "Apache-2.0 OR BSD-3-Clause (PDFium: BSD-3-Clause + permisywne biblioteki)",
        PERMISSIVE,
        "PDFium na BSD-3-Clause; w binarce FreeType na FTL (wybór z FTL lub GPL-2.0), "
        "libjpeg-turbo, libpng, libtiff, zlib, lcms2, OpenJPEG, HarfBuzz, ICU, abseil: "
        "licencje permisywne (`BUILD_LICENSES/` w pakiecie). Licencje musl i libgcc dotyczą "
        "tylko kół musllinux, nie obrazu na glibc.",
    ),
    # certifi: Mozilla CA bundle (data file) under MPL-2.0. Hard dependency of httpx and
    # httpcore (imported at module load) and of requests (via rapidocr). Used unmodified as a
    # separate file; MPL-2.0 is file-level copyleft and does not reach our code.
    "certifi": Exception_(
        "Mozilla Public License 2.0 (MPL 2.0)",
        "MPL-2.0",
        WEAK_COPYLEFT,
        "Twarda zależność `httpx` i `httpcore` (import przy ładowaniu modułu) oraz `requests` "
        "przez `rapidocr`. Zawiera tylko pakiet certyfikatów CA Mozilli (plik danych). Bez "
        "`httpx` nie ma klienta modelu ani Tiki, bez `rapidocr` nie ma OCR.",
    ),
    # tqdm: progress bars, MPL-2.0 AND MIT. Hard dependency of rapidocr (OCR). Used unmodified
    # as separate files; MPL-2.0 is file-level copyleft and does not reach our code.
    "tqdm": Exception_(
        "MPL-2.0 AND MIT",
        "MPL-2.0 AND MIT",
        WEAK_COPYLEFT,
        "Twarda zależność `rapidocr` (paski postępu przy pobieraniu modeli). Bez `rapidocr` "
        "nie ma OCR rastrów.",
    ),
}

# Model weights are not packages; their licences are verified by hand (research/01, 06).
WEIGHTS: tuple[tuple[str, str, str], ...] = (
    (
        "RapidOCR PP-OCRv6 small (detekcja, rozpoznawanie)",
        "Apache-2.0",
        "OCR rastrów, w obrazie",
    ),
    ("Tesseract 5, dane `pol` (tessdata)", "Apache-2.0", "zapasowy OCR, w obrazie"),
    ("Qwen3.5-9B", "Apache-2.0", "model językowy, przez `LLM_BASE_URL`, poza obrazem"),
)


@dataclass(frozen=True)
class Package:
    ecosystem: str  # "python" or "npm"
    name: str
    version: str
    licence: str
    dev: bool = False


@dataclass(frozen=True)
class Verdict:
    package: Package
    ok: bool
    kind: str  # "allowed", PERMISSIVE, WEAK_COPYLEFT, "font", or "" when not ok
    reason: str


def canonical(term: str) -> str | None:
    term = term.strip()
    if term.startswith("(") and term.endswith(")"):
        term = term[1:-1].strip()
    return ALIASES.get(term.lower())


def expression_allowed(expr: str) -> bool:
    """SPDX-like evaluation: any OR alternative whose AND parts are all allowed."""
    expr = expr.strip()
    if expr.startswith("(") and expr.endswith(")"):
        expr = expr[1:-1]
    for alternative in re.split(r"\s+OR\s+", expr):
        parts = [p for p in re.split(r"\s+AND\s+|;\s*", alternative) if p.strip()]
        if parts and all(canonical(p) is not None for p in parts):
            return True
    return False


def judge(pkg: Package) -> Verdict:
    lic = pkg.licence.strip()
    exc = EXCEPTIONS.get(pkg.name.lower()) if pkg.ecosystem == "python" else None
    if exc is not None:
        if exc.reported != lic:
            reason = f"exception expects {exc.reported!r}, metadata now says {lic!r}"
            return Verdict(pkg, False, "", reason)
        return Verdict(pkg, True, exc.kind, f"verified: {exc.verified}")
    if pkg.ecosystem == "npm" and lic == FONT_LICENCE:
        if pkg.name in FONT_PACKAGES:
            return Verdict(pkg, True, "font", "OFL-1.1, font package (D25)")
        return Verdict(pkg, False, "", "OFL-1.1 allowed only for the two font packages")
    if lic and expression_allowed(lic):
        return Verdict(pkg, True, "allowed", "")
    return Verdict(pkg, False, "", f"licence {lic or 'missing'!r} not allowed")


def run(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(
        cmd, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def python_packages() -> tuple[list[Package], list[str]]:
    """Runtime packages of api/ with licences; also names skipped by environment markers."""
    exported = run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-hashes",
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
            "--format",
            "requirements-txt",
            "-q",
        ],
        API,
    )
    wanted: dict[str, bool] = {}  # normalised name -> has an environment marker
    for line in exported.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[=<>;\s\[]", line, maxsplit=1)[0]
        wanted[normalise(name)] = ";" in line
    out = run(
        [
            "uv",
            "run",
            "--frozen",
            "pip-licenses",
            "--with-system",
            "--from=mixed",
            "--format=json",
            "--packages",
            *wanted,
        ],
        API,
    )
    found = [
        Package("python", row["Name"], row["Version"], row["License"])
        for row in json.loads(out)
    ]
    seen = {normalise(p.name) for p in found}
    missing = sorted(n for n in wanted if n not in seen)
    unexplained = [n for n in missing if not wanted[n]]
    if unexplained:
        sys.exit(f"pip-licenses found no metadata for runtime packages: {unexplained}")
    return found, missing


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def npm_packages() -> list[Package]:
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    packages = []
    for path, meta in lock["packages"].items():
        if not path:
            continue  # the root project itself
        name = path.rsplit("node_modules/", 1)[-1]
        licence = meta.get("license", "")
        if not isinstance(licence, str):  # legacy {"type": ...} objects
            licence = str(licence.get("type", "")) if isinstance(licence, dict) else ""
        packages.append(
            Package(
                "npm", name, meta.get("version", ""), licence, bool(meta.get("dev"))
            )
        )
    return packages


def summary(verdicts: list[Verdict], skipped: list[str]) -> bool:
    failed = [v for v in verdicts if not v.ok]
    for eco in ("python", "npm"):
        mine = [v for v in verdicts if v.package.ecosystem == eco]
        counts: dict[str, int] = {}
        for v in mine:
            counts[v.kind or "FAIL"] = counts.get(v.kind or "FAIL", 0) + 1
        detail = ", ".join(f"{k} {n}" for k, n in sorted(counts.items()))
        print(f"{eco}: {len(mine)} packages ({detail})")
    if skipped:
        print(
            f"python: not installed on this platform (environment marker): {', '.join(skipped)}"
        )
    for v in verdicts:
        if v.kind == PERMISSIVE:
            print(f"  resolved   {v.package.name} {v.package.version}: {v.reason}")
    for v in verdicts:
        if v.kind == WEAK_COPYLEFT:
            print(
                f"WARNING weak copyleft accepted (unmodified, transitive, separate files; "
                f"needs mentor confirmation): {v.package.name} {v.package.version} "
                f"[{v.package.licence}]"
            )
    print("model weights (verified by hand):")
    for name, licence, use in WEIGHTS:
        print(f"  {licence:<11} {name} ({use})")
    for v in failed:
        p = v.package
        print(f"FAIL {p.ecosystem} {p.name} {p.version}: {v.reason}")
    print("licence gate: " + ("FAILED" if failed else "passed"))
    return not failed


def md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def report(verdicts: list[Verdict], skipped: list[str]) -> str:
    py = [v for v in verdicts if v.package.ecosystem == "python"]
    npm = [v for v in verdicts if v.package.ecosystem == "npm"]
    status = {
        "allowed": "dozwolona",
        PERMISSIVE: "wyjątek: permisywna",
        "font": "font (D25)",
    }
    status[WEAK_COPYLEFT] = "**wyjątek: słaby copyleft, do potwierdzenia**"
    lines = [
        "# 09. Licencje zależności i wag",
        "",
        f"Raport generuje bramka licencyjna: `{GATE_COMMAND} --write`. Nie poprawiaj go ręcznie.",
        "",
        (
            "Zasada (`CLAUDE.md`, zasada twarda 1): MIT, BSD, Apache-2.0, ISC, 0BSD, PSF; SIL OFL-1.1 "
            "tylko dla fontów Archivo i IBM Plex Mono (D25). Bramka kończy się błędem, gdy pakiet ma "
            "inną licencję i nie ma go na liście wyjątków w `devtools/check_licenses.py`. Wyjątek "
            "wiąże się z dokładnym tekstem licencji z metadanych, więc zmiana licencji w nowej wersji "
            "pakietu znowu zatrzymuje bramkę."
        ),
        "",
        (
            "Zakres: zależności uruchomieniowe `api/` (`uv export --no-dev`, licencje odczytuje "
            "`pip-licenses`, sam na MIT, zależność deweloperska) oraz wszystkie pakiety z "
            "`web/package-lock.json`, także deweloperskie. Wyrażenie `OR` przechodzi, gdy dozwolona "
            "jest jedna z alternatyw, `AND` tylko wtedy, gdy dozwolone są wszystkie części."
        ),
        "",
        "## Do potwierdzenia z mentorem: słaby copyleft (MPL-2.0)",
        "",
        (
            "Dwie zależności przechodnie mają licencję MPL-2.0. MPL-2.0 to copyleft na poziomie "
            "pliku: obowiązki dotyczą tylko zmienionych plików samej biblioteki, nie naszego kodu. "
            "Używamy ich bez zmian, jako osobnych plików. Bramka je przepuszcza z ostrzeżeniem; "
            "każdy inny pakiet na MPL, LGPL lub GPL zatrzymuje bramkę."
        ),
        "",
        "| Pakiet | Wersja | Licencja | Dlaczego nie da się go usunąć |",
        "|---|---|---|---|",
    ]
    for v in py:
        if v.kind == WEAK_COPYLEFT:
            exc = EXCEPTIONS[v.package.name.lower()]
            lines.append(
                f"| `{v.package.name}` | {v.package.version} | {exc.verified} | {exc.note} |"
            )
    lines += [
        "",
        "## Wyjątki permisywne",
        "",
        "Licencje spoza listy, sprawdzone ręcznie; wszystkie są permisywne.",
        "",
        "| Pakiet | Wersja | Licencja w metadanych | Ustalenie |",
        "|---|---|---|---|",
    ]
    for v in py:
        if v.kind == PERMISSIVE:
            exc = EXCEPTIONS[v.package.name.lower()]
            lines.append(
                f"| `{v.package.name}` | {v.package.version} | {md_escape(v.package.licence)} "
                f"| {exc.note} |"
            )
    lines += [
        "",
        f"## Python: zależności uruchomieniowe `api/` ({len(py)})",
        "",
        "| Pakiet | Wersja | Licencja w metadanych | Ocena |",
        "|---|---|---|---|",
    ]
    for v in sorted(py, key=lambda v: v.package.name.lower()):
        p = v.package
        verdict = status.get(v.kind, "**niedozwolona**")
        lines.append(
            f"| `{p.name}` | {p.version} | {md_escape(p.licence)} | {verdict} |"
        )
    if skipped:
        lines += [
            "",
            "Pominięte, bo nie instalują się na tej platformie (znacznik środowiska): "
            + ", ".join(f"`{s}`" for s in skipped)
            + ".",
        ]
    runtime = [v for v in npm if not v.package.dev]
    dev = [v for v in npm if v.package.dev]
    lines += [
        "",
        f"## npm: zależności `web/` w pakiecie aplikacji ({len(runtime)})",
        "",
        "| Pakiet | Wersja | Licencja | Ocena |",
        "|---|---|---|---|",
    ]
    for v in sorted(runtime, key=lambda v: v.package.name):
        p = v.package
        verdict = status.get(v.kind, "**niedozwolona**")
        lines.append(
            f"| `{p.name}` | {p.version} | {md_escape(p.licence)} | {verdict} |"
        )
    counts: dict[str, int] = {}
    for v in dev:
        counts[v.package.licence] = counts.get(v.package.licence, 0) + 1
    lines += [
        "",
        f"## npm: narzędzia deweloperskie `web/` ({len(dev)}, poza obrazem)",
        "",
        "| Licencja | Pakietów |",
        "|---|---|",
    ]
    lines += [f"| {md_escape(lic)} | {n} |" for lic, n in sorted(counts.items())]
    lines += [
        "",
        "## Wagi modeli",
        "",
        "Wagi nie są pakietami, licencje sprawdzone ręcznie (`research/01`, `research/06`).",
        "",
        "| Wagi | Licencja | Użycie |",
        "|---|---|---|",
    ]
    lines += [f"| {name} | {lic} | {use} |" for name, lic, use in WEIGHTS]
    lines += [
        "",
        (
            "Programy uruchamiane jako osobne procesy: Apache Tika Server (Apache-2.0), Tesseract 5 "
            "(Apache-2.0), nginx (BSD-2-Clause); docelowy lokalny serwer modelu `llama-server` z "
            "llama.cpp (MIT). Bramka nie obejmuje obrazów bazowych Dockera (system, środowisko "
            "Java dla Tiki)."
        ),
        "",
    ]
    return "\n".join(lines)


def self_test() -> None:
    def py(lic: str, name: str = "fake-pkg") -> bool:
        return judge(Package("python", name, "1", lic)).ok

    def npm(lic: str, name: str = "fake-pkg") -> bool:
        return judge(Package("npm", name, "1", lic)).ok

    cases = [
        (py("MIT License"), True),
        (py("Apache Software License; MIT License"), True),
        (py("Apache-2.0 OR BSD-3-Clause"), True),
        (py("ISC License (ISCL)"), True),
        (py("Python Software Foundation License"), True),
        (py("GPL-3.0-only"), False),
        (py("GNU Affero General Public License v3"), False),
        (py("LGPL-2.1-or-later OR MIT"), True),  # OR: the MIT alternative is enough
        (py("MPL-2.0 AND MIT"), False),  # AND: every part must be allowed
        (py("Mozilla Public License 2.0 (MPL 2.0)", "orjson"), False),
        (py("UNKNOWN"), False),
        (py(""), False),
        (py("MPL-2.0 AND MIT", "tqdm"), True),  # listed exception
        (py("GPL-3.0-only", "tqdm"), False),  # exception bound to the reported string
        (npm("MIT OR Apache-2.0"), True),
        (npm("OFL-1.1", "@fontsource/archivo"), True),
        (npm("OFL-1.1", "some-font"), False),
        (npm("CC-BY-4.0"), False),
        (npm("MPL-2.0", "certifi"), False),  # Python exceptions do not apply to npm
    ]
    bad = [i for i, (got, want) in enumerate(cases) if got != want]
    if bad:
        sys.exit(f"self-test failed for cases {bad}")
    print(f"self-test: {len(cases)} cases passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write", action="store_true", help=f"write {REPORT.relative_to(ROOT)}"
    )
    parser.add_argument(
        "--simulate",
        metavar="LICENCE",
        help="add a fake Python and npm package with this licence (dry run, never writes)",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="check the evaluator and exit"
    )
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    py, skipped = python_packages()
    packages = py + npm_packages()
    if args.simulate is not None:
        packages += [
            Package("python", "fake-python-pkg", "0.0.0", args.simulate),
            Package("npm", "fake-npm-pkg", "0.0.0", args.simulate),
        ]
    verdicts = [judge(p) for p in packages]
    ok = summary(verdicts, skipped)
    if args.write and args.simulate is None:
        REPORT.write_text(report(verdicts, skipped), encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
