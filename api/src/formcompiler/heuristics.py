"""Rule-based reading of a Document: title, addressee, applicant flags and subject fields.

Works without the model and is the fallback when the model fails. The applicant's identity,
address, contact data and consents are left to the predefined sections (sections.py), so this
module only extracts what is specific to the form.
"""

import itertools
import re
from dataclasses import dataclass, field

from pydantic import BaseModel

from formcompiler.compiler import slugify
from formcompiler.document import Document, Line, LineKind
from formcompiler.ir import (
    Addressee,
    Applicant,
    Cond,
    Consent,
    FieldIR,
    FieldType,
    PageIR,
    SectionIR,
    Validator,
)
from formcompiler.sections import RESERVED_KEYS

BLANK = re.compile(r"[._…]{3,}")
# A whole run of leaders, including gaps between runs ("…...  ……"), split out of a line.
LEADER = re.compile(r"[._…]{3,}(?:[\s._…]*[._…]{2,})*")
# OCR keeps only the first dots of a leader at the end of a line ("w miejscowości..").
TRAILING_DOTS = re.compile(r"(?<=\w)\.{2}\s*$")
STARTS_BLANK = re.compile(r"^[\s.]*[._…]{3,}")
ENDS_BLANK = re.compile(r"[._…]{3,}[\s.]*$")
CAPTION = re.compile(r"^/\s*(.*?)\s*/$")
# A caption under a dotted line: "(imię i nazwisko)", "/ rodzaj robót /".
CAPTION_LINE = re.compile(r"^\s*(?:\(\s*(.*?)\s*\)|/\s*(.*?)\s*/)\s*$")
NUMBERING = re.compile(r"^(\d+|[a-z]|[IVX]+)[.)]\s+")
# List markers in front of a label: "1.", "5 .", "a)", "b/", "1.2.", "-", "•".
MARKER = re.compile(
    r"^\s*(?:(?:\d{1,3}(?:\.\d{1,3})*\s?[.)]|[a-z][)/]|[IVX]+\.)\s*|[-\u2013•·]\s*)"
)
LIST_ITEM = re.compile(
    r"^\s*(?:\d{1,2}\)|[a-z][)/]|[-\u2013•·])(?:\s*\S|\s*$)|^\s*\d{1,2}\.\s+[a-ząćęłńóśźż]"
)
# A numbered box of a printed form: "11. Miejscowość", "16. Numer/y działki (…)".
BOX = re.compile(r"^\s*\d{1,3}\s?\.\s*(?P<label>[A-ZĄĆĘŁŃÓŚŹŻ][^.:;]*?)\s*$")
FOOTNOTE = re.compile(
    r"(?<=[^\W\d_])\s?\d{1,2}\s?\)|(?<=[a-ząćęłńóśźż])\d{1,2}\.?(?=\s|$)|[¹²³⁴⁵⁶⁷⁸⁹⁰]+\)?|\*+"
)
LEAD_PAREN = re.compile(r"^\s*\([^()]*\)\s*")
TAIL_PAREN = re.compile(r"\s*\(\s*([^()]*?)\s*\)\s*$")
OPTIONAL = re.compile(r"^(opcjonalnie|nieobowiązkowe|pole nieobowiązkowe)$", re.I)
REQUEST = re.compile(r"^.*?\b(proszę|wnoszę|zwracam się)( uprzejmie)?( o)?\s+", re.I)
# Words that start a sentence fragment rather than a field name ("w miejscowości", "przy ulicy").
LEADING_WORDS = frozenset(
    {"w", "we", "przy", "na", "z", "ze", "do", "od", "o", "i", "oraz", "a", "lub", "tj.", "tj"}
)
RANGE_WORDS = frozenset({"od", "do", "od dnia", "do dnia"})
ABBREVIATIONS = [
    (re.compile(r"\bnr\b\.?", re.I), "numer"),
    (re.compile(r"\bewid\b\.?", re.I), "ewidencyjny"),
    (re.compile(r"^tel\.?$", re.I), "telefon"),
    (re.compile(r"^zam\.?$", re.I), "adres zamieszkania"),
    (re.compile(r"^ul\.?$", re.I), "ulica"),
]
# Inflected nouns that open a label after its preposition is dropped -> the nominative.
NOMINATIVE = {
    "miejscowości": "miejscowość",
    "ulicy": "ulica",
    "obrębie": "obręb",
    "kwocie": "kwota",
    "terminie": "termin",
    "gminie": "gmina",
    "wysokości": "wysokość",
    "ilości": "ilość",
    "powierzchni": "powierzchnia",
    "tytułu": "tytuł",
    "załączeniu": "załączniki",
    "celu": "cel",
    "osobą": "osoba",
    "wykonawcą": "wykonawca",
}
UNIT = re.compile(r"^(m\s?2|m²|m\s?3|m³|m|km|ha|zł|gr|szt\.?|dni|osób|osoby|%)(?=\W|$)", re.I)
COUNTED_UNITS = frozenset({"dni", "osób", "osoby", "szt", "szt."})
LABEL_MAX = 100
# Where the head of a long caption or list item ends: a comma, a dash or a qualifier clause.
QUALIFIER = re.compile(
    r",\s|\s[\u2013-]\s|;\s|\s(?:jeżeli|jeśli|w przypadku|stosownie do|zgodnie z|"
    r"z zaznaczeniem|wraz z)\s",
    re.I,
)
VERB = re.compile(r"\b(będzie|będą|jest|są)$", re.I)
DATA_HEADING = re.compile(r"^dane\b", re.I)
PUNCTUATION = " :;,.-\u2013"
DASH = " \u2013 "
UNITS = {"m2": "m²", "m3": "m³"}
RANGE_START = re.compile(r"\s*\bod(\s+dnia)?\s*$", re.I)
RANGE_NOUN = re.compile(r"(?:^|\s)(?:w|we|na|z|ze|od|przez)\s+(\S+)$", re.I)
SECTION_ONLY = re.compile(r"^([A-Z]|[IVX]+)$")
BOX_PAREN = re.compile(r"\s*\([^()]*\)")
LONG_LABEL_WORDS = 6
TITLE = re.compile(r"^(wniosek|deklaracja|zgłoszenie|oświadczenie|podanie)\b", re.I)
# A mixed-case title line: "Wniosek o …", "Deklaracja w sprawie …".
TITLE_PHRASE = re.compile(
    r"^(wniosek|deklaracja|zgłoszenie|oświadczenie|podanie) (o|w sprawie|dotycząc)\b", re.I
)
SECTION_MARK = re.compile(r"^([A-Z]|[IVX]+|\d+)[.)]?\s")
TITLE_MAX_LINES = 4
ADDRESSEE = re.compile(r"\b(Urząd|Wójt|Burmistrz|Prezydent|Starosta|Zarząd|Rada|Marszałek)\b[^,;]*")
# Lines that end the name in an addressee block: street, number, postcode, department, caption.
ADDRESS_LINE = re.compile(
    r"\d|^(ul|al|pl|os)\b\.?|^(wydział|referat|biuro|departament)\b|^[(/]", re.I
)
LOWER_WORDS = frozenset({"i", "w", "we", "na", "z", "ze", "do", "o"})
ORGANS = ("Wójt", "Burmistrz", "Prezydent", "Starosta", "Zarząd", "Rada", "Marszałek")
SKIP = re.compile(
    r"podpis|pieczęć|pieczątk|^\W*(\w+\W+)?dnia\b|data wpływu|data (wypełnienia|sporządzenia)|"
    r"miejscowość i data|wypełnia (urząd|organ|pracownik)|adnotacj|^nr sprawy",
    re.I,
)
# Information headings: "INFORMACJE:", "Informacja o przetwarzaniu danych", "Pouczenie", but not
# a data section such as "Informacja o posiadanym psie" or "Informacja o załącznikach".
INFO = re.compile(
    r"^(informacj\w*\s*:?$|informacj\w* (dotycząc\w* )?(o )?(przetwarzani|ochron)|pouczeni|"
    r"objaśnieni|uwagi\s*:?$|klauzul)",
    re.I,
)
CONSENT = re.compile(r"^(?:[\w,]+\s){0,2}?(oświadczam\b|wyrażam zgodę)", re.I)
CONSENT_PREFIX = "Oświadczam, że "
ATTACHMENTS = re.compile(r"załącz", re.I)
ACCOUNT = re.compile(r"rachun|przelew", re.I)
# Personal and address data of the applicant are covered by the predefined sections.
PERSONAL = re.compile(
    r"imię|nazwisk|pesel|\bnip\b|\bregon\b|telefon|e-?mail|obywatelstw|dowodu osobistego|"
    r"^adres zamieszkania",
    re.I,
)
ADDRESS_PART = re.compile(
    r"\badres|ulica|kod pocztowy|miejscowość|\bnumer (domu|lokalu)|\bkraj\b|województwo|"
    r"\bgmina\b|\bpowiat\b|\bpoczta\b|^numer\b|działk",
    re.I,
)
APPLICANT_CONTEXT = re.compile(
    r"wnioskodaw|składając|zobowiązan|identyfikac|zamieszkani|siedzib|korespondenc|kontakt|"
    r"podpis|pełnomocni|reprezent",
    re.I,
)
COVERED_MAX_WORDS = 5
PROXY = re.compile(r"pełnomocni", re.I)
ENTITY = re.compile(
    r"\b(NIP|REGON|KRS)\b|osob\w* prawn|nazwa (firmy|podmiotu|przedsiębiorcy)|przedsiębiorc", re.I
)
FEE = re.compile(r"opłat.*\d+\s*zł|\d+\s*zł.*opłat", re.I)
OTHER = re.compile(r"^inne\b", re.I)
MULTIPLE = re.compile(r"\*|zaznacz\w* (kilka|wszystkie|właściwe)", re.I)

KEYWORDS: list[tuple[re.Pattern[str], FieldType, list[Validator]]] = [
    (re.compile(r"załącz|dołącz|kopi[ae]|skan", re.I), FieldType.FILE_UPLOADER, []),
    (re.compile(r"\bdata\b|\btermin\b", re.I), FieldType.DATEPICKER, []),
    (
        re.compile(r"kwota|wysokość|liczba|ilość|powierzchnia|długość|szerokość|\bzł\b", re.I),
        FieldType.NUMBER,
        [],
    ),
    (re.compile(r"uzasadnieni|opis|\bcel\b|uwagi|powód", re.I), FieldType.TEXTAREA, []),
    (re.compile(r"\bNIP\b"), FieldType.TEXT_FIELD, [Validator.NIP]),
    (re.compile(r"\bREGON\b"), FieldType.TEXT_FIELD, [Validator.REGON]),
    (re.compile(r"\bPESEL\b"), FieldType.TEXT_FIELD, [Validator.PESEL]),
    (re.compile(r"e-?mail", re.I), FieldType.TEXT_FIELD, [Validator.EMAIL]),
    (re.compile(r"kod pocztowy", re.I), FieldType.TEXT_FIELD, [Validator.ZIP_CODE]),
    (re.compile(r"\bepuap\b", re.I), FieldType.TEXT_FIELD, [Validator.EPUAP]),
    (
        re.compile(r"dowodu osobistego|dowód osobisty", re.I),
        FieldType.TEXT_FIELD,
        [Validator.SERIAL_NUMBER_ID_CARD],
    ),
]

SUBJECT_PAGE = "Szczegóły wniosku"
DEFAULT_SECTION = "Zakres wniosku"
HEURISTIC_CONFIDENCE = 0.5


class Analysis(BaseModel):
    title: str
    addressee: Addressee | None
    applicant: Applicant
    pages: list[PageIR]


def classify(label: str) -> tuple[FieldType, list[Validator]]:
    for pattern, field_type, validators in KEYWORDS:
        if pattern.search(label):
            return field_type, validators
    return FieldType.TEXT_FIELD, []


def clean(text: str) -> str:
    text = BLANK.sub(" ", text).strip()
    if caption := CAPTION.match(text):
        text = caption.group(1)
    text = NUMBERING.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" :*").strip()
    return text[:1].upper() + text[1:]


def label_of(text: str) -> tuple[str, str]:
    """A field name from the words next to a blank, and a description from its trailing
    parenthesis: "w miejscowości 1)" -> "Miejscowość", "Numer telefonu (opcjonalnie)" -> no note."""
    text = LEADER.sub(" ", text)
    text = FOOTNOTE.sub("", text)
    text = LEAD_PAREN.sub("", text)
    text = MARKER.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(PUNCTUATION)
    description = ""
    if (tail := TAIL_PAREN.search(text)) and tail.start() > 0:
        text, note = text[: tail.start()].strip(PUNCTUATION), tail.group(1).strip(" ,;")
        description = "" if OPTIONAL.match(note) else note[:1].upper() + note[1:]
    if len(text.split()) > LONG_LABEL_WORDS:
        text = REQUEST.sub("", text)
        head = _short(text)
        if head != text:
            description = description or _sentence(text)
            text = head
    words = text.split()
    while words and words[0].lower() in LEADING_WORDS:
        words.pop(0)
    text = " ".join(words)
    for pattern, replacement in ABBREVIATIONS:
        text = pattern.sub(replacement, text)
    first, _, rest = text.partition(" ")
    if nominative := NOMINATIVE.get(first.lower()):
        text = f"{nominative} {rest}".strip()
    if len(text) > LABEL_MAX:
        text = text[:LABEL_MAX].rsplit(" ", 1)[0]
    text = text.strip(PUNCTUATION + "=+")
    if not re.search(r"[^\W\d_]{2}", text) or UNIT.fullmatch(text):
        return "", description
    return text[:1].upper() + text[1:], description


def _option(text: str) -> str:
    option = clean(LEADER.split(text)[0] if LEADER.search(text) else text)
    option = FOOTNOTE.sub("", option).strip(PUNCTUATION)
    if OTHER.match(option):
        return "Inne"
    return option[:1].upper() + option[1:]


def _sentence_like(label: str) -> bool:
    """A sentence fragment rather than a field name: long, or a request ("Wnoszę o …")."""
    long = len(label.split()) > LONG_LABEL_WORDS - 2
    return long or REQUEST.match(label) is not None or VERB.search(label) is not None


def _shape(text: str) -> str:
    return re.sub(r"\s+", "", LEADER.sub("_", text))


def _with_note(label: str, note: str) -> str:
    return f"{label} ({note[:1].lower()}{note[1:]})" if label and note else label


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def _range_base(text: str) -> str:
    """The noun of a date range: "Roboty będą realizowane w terminie" -> "Termin"."""
    text = re.sub(r"\s+", " ", FOOTNOTE.sub("", text)).strip(" .,:")
    if match := RANGE_NOUN.search(text):
        text = match.group(1)
    label, _ = label_of(text)
    return label or "Termin"


def _short(text: str) -> str:
    """The head of a long caption or list item: up to the first comma, dash or qualifier."""
    head = QUALIFIER.split(text, maxsplit=1)[0].strip(PUNCTUATION)
    return head if len(head.split()) >= 2 else text


def _caption(line: Line) -> str | None:
    """The caption printed under a dotted line, or None when the line is not one."""
    raw = line.text.strip()
    if BLANK.search(raw) or line.kind in (LineKind.HEADING, LineKind.CHECKBOX):
        return None
    if match := CAPTION_LINE.match(raw):
        return (match.group(1) or match.group(2) or "").strip()
    lower = raw[:1].islower() and not LIST_ITEM.match(raw)
    if lower and len(raw.split()) <= 7 and not raw.endswith((".", ":", ",")):
        return raw
    return None


def _section_title(text: str) -> str:
    """ "B.1 DANE IDENTYFIKACYJNE" -> "Dane identyfikacyjne"."""
    stripped = re.sub(r"^(?:[A-Z](?:\.\d+)*|[IVX]+|\d+(?:\.\d+)*)\s?[.)]?\s+(?=\S)", "", text)
    stripped = stripped or text
    return _sentence_case(stripped) if stripped.isupper() else stripped


def analyze(doc: Document) -> Analysis:
    lines = [line for page in doc.pages for line in page.lines]
    title_at = next((i for i, line in enumerate(lines) if _is_title(line)), None)
    if title_at is None:
        title_at = next((i for i, line in enumerate(lines) if _is_title_phrase(line)), None)
    header = lines[:title_at] if title_at is not None else []
    title, title_end = ("Wniosek", 0) if title_at is None else _title(lines, title_at)
    body = lines[title_end:] if title_at is not None else lines

    everything = " ".join(line.text for line in lines)
    applicant = Applicant(
        persons=True,
        entities=bool(ENTITY.search(everything)),
        proxy=bool(PROXY.search(everything)),
    )
    sections = _Reader().read(body)
    return Analysis(
        title=title,
        addressee=_addressee(header or body[:10]),
        applicant=applicant,
        pages=[PageIR(title=SUBJECT_PAGE, sections=sections)],
    )


def _is_title(line: Line) -> bool:
    text = clean(line.text)
    return bool(TITLE.match(text)) and (line.kind is LineKind.HEADING or text.isupper())


def _is_title_phrase(line: Line) -> bool:
    text = clean(line.text)
    return bool(TITLE_PHRASE.match(text)) and not BLANK.search(line.text) and len(text) < 150


def _title(lines: list[Line], at: int) -> tuple[str, int]:
    """Join a title split over lines ("WNIOSEK" / "o wynajęcie …"); return it and the next index."""
    first = clean(lines[at].text)
    parts = [_sentence_case(first) if first.isupper() else first]
    upper = first.isupper()
    end = at + 1
    while end < len(lines) and end - at < TITLE_MAX_LINES:
        raw = lines[end].text.strip()
        text = clean(raw)
        if not text or BLANK.search(raw) or SECTION_MARK.match(raw):
            break
        lower_start = raw[:1].islower()
        opens = text.lower().startswith(("o ", "w sprawie", "dotycząc")) or text.lower() == "o"
        if not (lower_start or (upper and (text.isupper() or opens))):
            break
        parts.append(text.lower() if text.isupper() or lower_start else text)
        upper = upper and text.isupper()
        end += 1
    title = re.sub(r"\s*\*+", "", " ".join(parts))
    return title[:1].upper() + title[1:], end


def _sentence_case(text: str) -> str:
    return text[:1] + text[1:].lower() if text.isupper() else text


def _name_case(text: str) -> str:
    """ "WÓJT GMINY PŁOSKINIA" -> "Wójt Gminy Płoskinia"; mixed case is kept."""
    if not text.isupper():
        return text
    words = text.title().split()
    return " ".join(w.lower() if i and w.lower() in LOWER_WORDS else w for i, w in enumerate(words))


def _addressee(lines: list[Line]) -> Addressee | None:
    """The addressee block: the line naming the office or organ, plus following name lines up to
    the street, postcode, department or an empty line."""
    for i, line in enumerate(lines):
        text = _name_case(line.text.strip())
        match = ADDRESSEE.search(text)
        if match is None:
            continue
        name = [match.group(0).strip(" .")]
        for following in lines[i + 1 : i + 3]:
            extra = _name_case(following.text.strip())
            if not extra or BLANK.search(extra) or ADDRESS_LINE.search(extra):
                break
            if _is_title(following) or _is_title_phrase(following):
                break
            name.append(extra.strip(" ."))
        full = " ".join(name)
        return Addressee(name=full, kind="ORGAN" if full.startswith(ORGANS) else "URZAD")
    return None


@dataclass
class _Section:
    title: str
    fields: list[FieldIR] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    info_src: list[str] = field(default_factory=list)


@dataclass
class _Prompt:
    """A text line waiting to become the label of what follows (a blank, choices, a list)."""

    text: str
    src: str
    raw: str
    index: int
    box: bool

    @property
    def colon(self) -> bool:
        return self.raw.rstrip(" *").endswith(":")


@dataclass
class _Spec:
    """One blank of a line, before it becomes a field."""

    label: str
    description: str = ""
    unit: str = ""
    before: str = ""


@dataclass
class _Item:
    text: str
    src: list[str]


class _Keys:
    def __init__(self) -> None:
        self.used = set(RESERVED_KEYS)

    def make(self, label: str, fallback: str = "pole") -> str:
        base = slugify(label)[:50].strip("_") or fallback
        if base[0].isdigit():
            base = f"{fallback}_{base}"[:50]
        key, n = base, 2
        while key in self.used:
            key, n = f"{base}_{n}", n + 1
        self.used.add(key)
        return key


class _Reader:
    """Single pass over the body lines, grouping fields into sections."""

    def __init__(self) -> None:
        self.keys = _Keys()
        self.sections = [_Section(DEFAULT_SECTION)]
        self.consents: list[_Item] = []
        self.consent_open = False
        self.consent_intro = False
        self.prompt: _Prompt | None = None
        self.fee_src: str | None = None
        self.info_mode = False
        self.skip_section = False
        self.rows: dict[str, int] = {}
        self.joined: dict[str, list[str]] = {}
        self.labels: set[str] = set()

    @property
    def current(self) -> _Section:
        return self.sections[-1]

    def read(self, body: list[Line]) -> list[SectionIR]:
        lines = self._join(body)
        i = 0
        while i < len(lines):
            i = self._step(lines, i)
        self._flush()
        return self._finish()

    def _join(self, body: list[Line]) -> list[Line]:
        """Glue a dotted line that continues on the next line into one line ("… z tytułu ……" /
        "…… w kwocie ……"), counting the rows it spans."""
        out: list[Line] = []
        for line in body:
            text = TRAILING_DOTS.sub(" ...", line.text)
            if text != line.text:
                line = line.model_copy(update={"text": text})
            prev = out[-1] if out else None
            if (
                prev is not None
                and prev.kind is not LineKind.HEADING
                and line.kind is LineKind.TEXT
                and ENDS_BLANK.search(prev.text)
                and STARTS_BLANK.match(line.text)
            ):
                out[-1] = prev.model_copy(update={"text": f"{prev.text} {line.text}"})
                self.rows[prev.id] = self.rows.get(prev.id, 1) + 1
                self.joined.setdefault(prev.id, []).append(line.id)
            else:
                out.append(line)
        return out

    def _step(self, lines: list[Line], i: int) -> int:
        line = lines[i]
        raw = line.text
        text = clean(raw)
        if FEE.search(raw) and self.fee_src is None:
            self.fee_src = line.id
        if not text and not BLANK.search(raw):
            return i + 1
        if self._is_heading(line, text):
            return self._heading(text, i)
        if SKIP.search(text) or self.skip_section:
            self._flush()
            return i + 1
        if self.info_mode:
            self.current.info.append(text)
            self.current.info_src.append(line.id)
            return i + 1
        if INFO.match(text) and not BLANK.search(raw) and len(text.split()) <= 8:
            return self._heading(text, i)
        if self._consent(line, text):
            return i + 1
        if line.kind is LineKind.CHECKBOX:
            return self._choice(lines, i)
        prompt = self.prompt
        listed = prompt is not None and (prompt.colon or prompt.box)
        if listed and prompt and prompt.index == i - 1 and LIST_ITEM.match(raw):
            end = self._list(lines, i, prompt)
            if end is not None:
                return end
        if line.kind is LineKind.TABLE_ROW and self._table(line):
            return i + 1
        if BLANK.search(raw):
            return self._blank(lines, i)
        if self._continues(prompt, raw, i) and prompt:
            self.prompt = _Prompt(
                f"{prompt.text} {text}", prompt.src, f"{prompt.raw} {raw}", i, box=False
            )
            return i + 1
        self._flush()
        self.prompt = _Prompt(text, line.id, raw, i, BOX.match(raw) is not None)
        return i + 1

    def _continues(self, prompt: _Prompt | None, raw: str, i: int) -> bool:
        """The line goes on with the sentence of the prompt line right above it."""
        if prompt is None or prompt.index != i - 1 or not raw.strip()[:1].islower():
            return False
        return not prompt.colon and not prompt.raw.rstrip().endswith(".")

    def _is_heading(self, line: Line, text: str) -> bool:
        if BLANK.search(line.text) or line.kind is LineKind.CHECKBOX:
            return False
        if line.kind is LineKind.HEADING:
            return True
        text = TAIL_PAREN.sub("", text)
        if not (text.isupper() and len(text) < 60):
            return False
        if SECTION_ONLY.match(text):
            return True
        if not re.search(r"[^\W\d_]{4}", text):
            return False  # OCR noise such as "TAK ]NIE"
        return len(text.split()) >= 2 or bool(INFO.match(text)) or line.text.rstrip().endswith(":")

    def _heading(self, text: str, i: int) -> int:
        if SECTION_ONLY.match(text):
            # A lone section letter printed beside its title: take the title from the line
            # before ("INFORMACJA O POSIADANYM PSIE (…)" / "B").
            words = self.prompt.text.split() if self.prompt else []
            upper = list(itertools.takewhile(str.isupper, words))
            if len(upper) < 2:
                return i + 1
            text = " ".join(upper)
            self.prompt = None
        self._flush()
        self.info_mode = bool(INFO.match(text))
        self.skip_section = bool(SKIP.search(text))
        self.consent_open = self.consent_intro = False
        title = _section_title(TAIL_PAREN.sub("", text) if text.upper() != text else text)
        self.sections.append(_Section("Informacje" if self.info_mode else title))
        return i + 1

    def _consent(self, line: Line, text: str) -> bool:
        """Statements go to the consent section; an intro ending with a colon ("Jednocześnie
        oświadczam, że:") turns the list below it into one statement per item."""
        raw = line.text
        continues = (
            self.consents
            and line.kind is LineKind.TEXT
            and not BLANK.search(raw)
            and not LIST_ITEM.match(raw)
            and not NUMBERING.match(raw)
            and not self.consents[-1].text.endswith((".", ";"))
        )
        if self.consent_intro and LIST_ITEM.match(raw):
            item = MARKER.sub("", raw).strip()
            self.consents.append(_Item(CONSENT_PREFIX + item[:1].lower() + item[1:], [line.id]))
            self.consent_open = True
            return True
        if self.consent_open and continues:
            self.consents[-1].text += " " + raw.strip()
            self.consents[-1].src.append(line.id)
            self._consent_intro(raw)
            return True
        self.consent_open = self.consent_intro = False
        if CONSENT.match(text):
            self._flush()
            self.consents.append(_Item(text, [line.id]))
            self.consent_open = True
            self._consent_intro(raw)
            return True
        return False

    def _consent_intro(self, raw: str) -> None:
        if self.consents and raw.rstrip(" *").endswith(":"):
            self.consents.pop()
            self.consent_intro, self.consent_open = True, False

    def _choice(self, lines: list[Line], i: int) -> int:
        group = []
        while i < len(lines) and lines[i].kind is LineKind.CHECKBOX:
            group.append(lines[i])
            i += 1
        while i < len(lines) and not clean(lines[i].text):
            i += 1  # blank lines after "inne ……" belong to the other option
        options = [_option(line.text) for line in group]
        options = [o or f"Opcja {n}" for n, o in enumerate(options, 1)]
        prompt = self.prompt
        label, description = label_of(prompt.raw) if prompt else ("", "")
        if not prompt and not self.current.fields and self.current.title != DEFAULT_SECTION:
            label = self.current.title  # choices right under a heading ("Wnioskodawca")
        multiple = bool(MULTIPLE.search(prompt.raw)) if prompt else False
        field_type = FieldType.CHECKBOX if multiple else FieldType.RADIO
        if field_type is FieldType.RADIO and len(options) > 5:
            field_type = FieldType.SELECT
        src = [prompt.src] if prompt else []
        choice = self._field(
            label or "Wybierz",
            field_type,
            [],
            src + [line.id for line in group],
            list(dict.fromkeys(options)),
            description=description,
        )
        for line, option in zip(group, options, strict=True):
            if not BLANK.search(line.text):
                continue
            detail, _ = label_of(LEADER.split(line.text)[0])
            if option == "Inne" or not detail or detail == option:
                detail = "Podaj inny zakres" if option == "Inne" else f"{option}: szczegóły"
            field_type, validators = classify(detail)
            self._field(
                detail,
                field_type,
                validators,
                [line.id],
                show_if=Cond(field=choice.key, value=option),
            )
        self.prompt = None
        return i

    def _list(self, lines: list[Line], i: int, prompt: _Prompt) -> int | None:
        """A list under a prompt ending with a colon: attachments or one choice."""
        items: list[_Item] = []
        seen: set[str] = set()
        j = i
        while j < len(lines):
            line = lines[j]
            raw = line.text
            if line.kind is LineKind.HEADING or SKIP.search(raw):
                break
            if LIST_ITEM.match(raw) or (items and line.kind is LineKind.CHECKBOX):
                items.append(_Item(raw, [line.id]))
            elif items and not clean(raw):
                items[-1].text += " ....."
                items[-1].src.append(line.id)
            elif items and raw.strip()[:1].islower() and not NUMBERING.match(raw):
                one_slot = len(LEADER.split(raw)) == 2 and not LEADER.split(raw)[1].strip()
                if (BLANK.search(raw) and not one_slot) or raw.strip() in seen:
                    return None  # its own fields ("długość …… szerokość ……"), not a list
                seen.add(raw.strip())
                items[-1].text += " " + raw.strip()
                items[-1].src.append(line.id)
            else:
                break
            j += 1
        if len(items) < 2:
            return None
        self.prompt = None
        src = [prompt.src]
        if ATTACHMENTS.search(prompt.raw):
            other: list[str] = []
            for item in items:
                label, description = label_of(LEADER.split(item.text)[0])
                if not label:
                    other += item.src
                    continue
                short = _short(label)
                note = label if short != label else description
                self._field(short, FieldType.FILE_UPLOADER, [], src + item.src, description=note)
            if other:
                self._field("Inne załączniki", FieldType.FILE_UPLOADER, [], src + other)
            return j
        options = [_with_note(*label_of(LEADER.split(item.text)[0])) for item in items]
        options = [o or f"Opcja {n}" for n, o in enumerate(options, 1)]
        label, description = label_of(prompt.raw)
        field_type = FieldType.CHECKBOX if MULTIPLE.search(prompt.raw) else FieldType.RADIO
        if field_type is FieldType.RADIO and len(options) > 5:
            field_type = FieldType.SELECT
        choice = self._field(
            label or "Wybierz",
            field_type,
            [],
            src + [s for item in items for s in item.src],
            list(dict.fromkeys(options)),
            description=description,
        )
        for item, option in zip(items, options, strict=True):
            show_if = Cond(field=choice.key, value=option)
            if ACCOUNT.search(item.text):
                self._field(
                    "Numer rachunku bankowego", FieldType.TEXT_FIELD, [], item.src, show_if=show_if
                )
            elif BLANK.search(item.text):
                field_type, validators = classify(option)
                self._field(option, field_type, validators, item.src, show_if=show_if)
        return j

    def _table(self, line: Line) -> bool:
        """Label cells of a table row: "Ulica: | Nr domu: | Nr lokalu:" or one short cell."""
        cells = [c.strip() for c in line.cells if c.strip()]
        labels = [c for c in cells if c.endswith(":")]
        if not labels and len(cells) == 1 and len(cells[0].split()) <= COVERED_MAX_WORDS:
            labels = cells
        if not labels:
            return False
        self._flush()
        for cell in labels:
            label, description = label_of(cell)
            if label and not self._covered(label):
                field_type, validators = classify(label)
                self._field(label, field_type, validators, [line.id], description=description)
        return True

    def _blank(self, lines: list[Line], i: int) -> int:
        line = lines[i]
        if i > 0 and _shape(line.text) == _shape(lines[i - 1].text):
            return i + 1  # a repeated row of the same dotted lines
        parts = LEADER.split(line.text)
        prompt = self.prompt
        sentence = prompt is not None and not MARKER.match(prompt.raw)
        sentence = sentence and _sentence_like(label_of(parts[0])[0])
        if parts[0].strip() and sentence and self._continues(prompt, line.text, i) and prompt:
            parts[0] = f"{prompt.raw} {parts[0]}"  # "a osobą odpowiedzialną …" / "… będzie ……"
            self.prompt = None
        src = [line.id, *self.joined.get(line.id, [])]
        end = i + 1
        caption = _caption(lines[end]) if end < len(lines) else None
        if caption is not None:
            src.append(lines[end].id)
            end += 1
        if caption is not None and UNIT.fullmatch(caption.strip()):
            caption = None  # "____" / "zł" under a box of a calculation table
        specs = self._specs(parts)
        prompt, used_prompt = self.prompt, False
        if caption is not None and SKIP.search(caption):
            unlabeled = [s for s in specs if not s.label]
            if len(unlabeled) == len(specs):
                self._flush()
                return end
            if unlabeled:
                specs.remove(unlabeled[0])
            caption = None
        first = specs[0] if specs else None
        if first is not None and not first.label and prompt and (prompt.colon or not caption):
            first.label, first.description = label_of(prompt.raw)
            used_prompt = True
            if caption:
                first.description, caption = _sentence(caption), None
        if caption:
            target = next(
                (s for s in specs if not s.label or _sentence_like(s.label)),
                None,
            )
            if target is not None:
                target.label, note = label_of(_short(caption))
                target.description = target.description or note
            elif len(specs) == 1 and not specs[0].description:
                specs[0].description = _sentence(caption)
        specs = [s for s in specs if s.label]
        short = len(specs) >= 2 and all(len(s.label.split()) <= 2 for s in specs)
        repeated = any(s.label in self.labels for s in specs)
        subheading = prompt is not None and (MARKER.match(prompt.raw) is not None or repeated)
        if short and subheading and prompt and not used_prompt and prompt.index == i - 1:
            context = _with_note(*label_of(prompt.raw))
            if context:
                for s in specs:
                    s.label = f"{context}{DASH}{s.label[:1].lower()}{s.label[1:]}"
                used_prompt = True
        if used_prompt and prompt:
            src.insert(0, prompt.src)
            self.prompt = None
        else:
            self._flush()
        rows = self.rows.get(line.id, 1)
        for spec in specs:
            label = f"{spec.label} ({spec.unit})" if spec.unit else spec.label
            if SKIP.search(label) or self._covered(spec.label):
                continue
            field_type, validators = classify(label)
            if spec.unit and not validators:
                field_type = FieldType.NUMBER
            if rows > 1 and len(specs) == 1 and field_type is FieldType.TEXT_FIELD:
                field_type = FieldType.TEXTAREA if not validators else field_type
            self._field(label, field_type, validators, src, description=spec.description)
        return end

    def _specs(self, parts: list[str]) -> list[_Spec]:
        """One spec per blank, labelled by the text before it; the text after the last blank is
        a unit ("…… m 2") or, when the leader got lost in OCR, one more label."""
        specs: list[_Spec] = []
        for before in parts[:-1]:
            word = re.sub(r"\s+", " ", FOOTNOTE.sub("", before)).strip(" .,:").lower()
            if word in RANGE_WORDS and specs and RANGE_START.search(specs[-1].before):
                base = _range_base(RANGE_START.sub("", specs[-1].before))
                specs[-1].label = f"{base} od"
                specs.append(_Spec(f"{base} do", before=before))
                continue
            label, description = label_of(before)
            specs.append(_Spec(label, description, before=before))
        trailing = re.sub(r"\s+", " ", parts[-1]).strip(" ,")
        if specs and (unit := UNIT.match(trailing)):
            name = unit.group(1).lower()
            specs[-1].unit = UNITS.get(name.replace(" ", ""), name)
            if not specs[-1].label and name in COUNTED_UNITS:
                specs[-1].label, specs[-1].unit = f"Liczba {name}", ""
        elif trailing[:1].islower() and len(trailing.split()) <= 4:
            label, description = label_of(trailing)
            if label:
                specs.append(_Spec(label, description, before=trailing))
        return specs

    def _covered(self, label: str) -> bool:
        """Applicant data that the predefined sections already ask for."""
        if len(label.split()) > COVERED_MAX_WORDS:
            return False
        title = self.current.title
        applicant = bool(APPLICANT_CONTEXT.search(title) or APPLICANT_CONTEXT.search(label))
        if PERSONAL.search(label):
            return applicant or title == DEFAULT_SECTION or TITLE.match(title) is not None
        return bool(ADDRESS_PART.search(label)) and applicant

    def _flush(self) -> None:
        """A prompt nobody used: a numbered box ("11. Miejscowość") or a short "Label:" whose
        kind is clear from its words ("Uzasadnienie:") is a field on its own."""
        prompt, self.prompt = self.prompt, None
        if prompt is None:
            return
        label, description = label_of(BOX_PAREN.sub("", prompt.raw) if prompt.box else prompt.raw)
        if not label or SKIP.search(label) or self._covered(label):
            return
        if prompt.box and DATA_HEADING.match(label):
            self.sections.append(_Section(label))
            return
        field_type, validators = classify(label)
        words = len(label.split())
        box = prompt.box and words <= 8
        date = field_type is FieldType.DATEPICKER and not label.lower().startswith("data")
        typed = prompt.colon and words <= 3 and field_type is not FieldType.TEXT_FIELD and not date
        if box or typed:
            self._field(label, field_type, validators, [prompt.src], description=description)

    def _field(
        self,
        label: str,
        field_type: FieldType,
        validators: list[Validator],
        src: list[str],
        options: list[str] | None = None,
        show_if: Cond | None = None,
        **extra: object,
    ) -> FieldIR:
        self.labels.add(label)
        f = FieldIR.model_validate(
            {
                "key": self.keys.make(label),
                "label": label,
                "type": field_type,
                "validators": validators,
                "options": options or [],
                "show_if": show_if,
                "src": src,
                "confidence": HEURISTIC_CONFIDENCE,
                **extra,
            }
        )
        self.current.fields.append(f)
        return f

    def _finish(self) -> list[SectionIR]:
        if self.fee_src is not None:
            self.sections.append(_Section("Opłata"))
            self._field(
                "Potwierdzenie zapłaty opłaty skarbowej",
                FieldType.FILE_UPLOADER,
                [],
                [self.fee_src],
            )
        if self.consents:
            self.sections.append(_Section("Oświadczenia"))
            self._field(
                "",
                FieldType.CONSENT_SECTION,
                [],
                [s for item in self.consents for s in item.src],
                consents=[Consent(text=item.text) for item in self.consents],
            )
        for section in self.sections:
            if section.info:
                block = FieldIR(
                    key=self.keys.make(f"{section.title} tekst"),
                    label="",
                    type=FieldType.TEXT_BLOCK,
                    description="\n\n".join(section.info),
                    src=section.info_src,
                    confidence=HEURISTIC_CONFIDENCE,
                )
                section.fields.insert(0, block)
        result = [
            SectionIR(key=self.keys.make(s.title, "sekcja"), title=s.title, fields=s.fields)
            for s in self.sections
            if s.fields
        ]
        if result:
            return result
        fallback = FieldIR(
            key=self.keys.make("Treść wniosku"),
            label="Treść wniosku",
            type=FieldType.TEXTAREA,
            required=True,
            confidence=HEURISTIC_CONFIDENCE,
        )
        return [
            SectionIR(key=self.keys.make("Wniosek", "sekcja"), title="Wniosek", fields=[fallback])
        ]
