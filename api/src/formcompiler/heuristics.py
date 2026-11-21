"""Rule-based reading of a Document: title, addressee, applicant flags and subject fields.

Works without the model and is the fallback when the model fails. The applicant's identity,
address, contact data and consents are left to the predefined sections (sections.py), so this
module only extracts what is specific to the form.
"""

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
CAPTION = re.compile(r"^/\s*(.*?)\s*/$")
NUMBERING = re.compile(r"^(\d+|[a-z]|[IVX]+)[.)]\s+")
TITLE = re.compile(r"^(wniosek|deklaracja|zgłoszenie|oświadczenie|podanie)\b", re.I)
ADDRESSEE = re.compile(r"\b(Urząd|Wójt|Burmistrz|Prezydent|Starosta|Zarząd|Rada|Marszałek)\b[^,;]*")
ORGANS = ("Wójt", "Burmistrz", "Prezydent", "Starosta", "Zarząd", "Rada", "Marszałek")
SKIP = re.compile(
    r"podpis|pieczęć|pieczątk|\bdnia\b|data wpływu|wypełnia (urząd|organ|pracownik)|adnotacj",
    re.I,
)
INFO = re.compile(r"^(informacj|pouczeni|objaśnieni|uwag)", re.I)
CONSENT = re.compile(r"^(oświadczam|wyrażam zgodę)", re.I)
COVERED = re.compile(
    r"imię|nazwisk|pesel|adres|ulica|kod pocztowy|miejscowość|telefon|e-?mail|nr domu|"
    r"nr lokalu|obywatelstw|dowodu osobistego",
    re.I,
)
PROXY = re.compile(r"pełnomocni", re.I)
ENTITY = re.compile(
    r"\b(NIP|REGON|KRS)\b|osob\w* prawn|nazwa (firmy|podmiotu|przedsiębiorcy)|przedsiębiorc", re.I
)
FEE = re.compile(r"opłat.*\d+\s*zł|\d+\s*zł.*opłat", re.I)
OTHER = re.compile(r"^inne\b", re.I)
MULTIPLE = re.compile(r"\*|zaznacz\w* (kilka|wszystkie|właściwe)", re.I)

KEYWORDS: list[tuple[re.Pattern[str], FieldType, list[Validator]]] = [
    (re.compile(r"załącz|dołącz|kopi[ae]|skan", re.I), FieldType.FILE_UPLOADER, []),
    (re.compile(r"\bdata\b", re.I), FieldType.DATEPICKER, []),
    (re.compile(r"kwota|wysokość|liczba|powierzchnia|\bzł\b", re.I), FieldType.NUMBER, []),
    (re.compile(r"uzasadnieni|opis|\bcel\b|uwagi|powód", re.I), FieldType.TEXTAREA, []),
    (re.compile(r"\bNIP\b"), FieldType.TEXT_FIELD, [Validator.NIP]),
    (re.compile(r"\bREGON\b"), FieldType.TEXT_FIELD, [Validator.REGON]),
    (re.compile(r"\bPESEL\b"), FieldType.TEXT_FIELD, [Validator.PESEL]),
    (re.compile(r"e-?mail", re.I), FieldType.TEXT_FIELD, [Validator.EMAIL]),
    (re.compile(r"kod pocztowy", re.I), FieldType.TEXT_FIELD, [Validator.ZIP_CODE]),
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


def analyze(doc: Document) -> Analysis:
    lines = [line for page in doc.pages for line in page.lines]
    title_at = next((i for i, line in enumerate(lines) if _is_title(line)), None)
    header = lines[:title_at] if title_at is not None else []
    body = lines[title_at + 1 :] if title_at is not None else lines
    title = _sentence_case(clean(lines[title_at].text)) if title_at is not None else "Wniosek"

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


def _sentence_case(text: str) -> str:
    return text[:1] + text[1:].lower() if text.isupper() else text


def _addressee(lines: list[Line]) -> Addressee | None:
    for line in lines:
        if match := ADDRESSEE.search(line.text):
            name = match.group(0).strip(" .")
            return Addressee(name=name, kind="ORGAN" if name.startswith(ORGANS) else "URZAD")
    return None


@dataclass
class _Section:
    title: str
    fields: list[FieldIR] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    info_src: list[str] = field(default_factory=list)


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
        self.consents: list[tuple[str, str]] = []
        self.prompt: tuple[str, str] | None = None
        self.fee_src: str | None = None
        self.info_mode = False

    @property
    def current(self) -> _Section:
        return self.sections[-1]

    def read(self, body: list[Line]) -> list[SectionIR]:
        i = 0
        while i < len(body):
            i = self._step(body, i)
        return self._finish()

    def _step(self, body: list[Line], i: int) -> int:
        line = body[i]
        text = clean(line.text)
        if FEE.search(line.text) and self.fee_src is None:
            self.fee_src = line.id
        if not text or SKIP.search(text):
            return i + 1
        if self._is_heading(line, text):
            self.info_mode = bool(INFO.match(text))
            self.sections.append(_Section("Informacje" if self.info_mode else text))
            self.prompt = None
            return i + 1
        if self.info_mode:
            self.current.info.append(text)
            self.current.info_src.append(line.id)
            return i + 1
        if CONSENT.match(text):
            self.consents.append((text, line.id))
            return i + 1
        if line.kind is LineKind.CHECKBOX:
            return self._choice(body, i)
        if BLANK.search(line.text):
            return self._blank(body, i, text)
        self.prompt = (text, line.id)
        return i + 1

    def _is_heading(self, line: Line, text: str) -> bool:
        if BLANK.search(line.text):
            return False
        return line.kind is LineKind.HEADING or (text.isupper() and len(text) < 60)

    def _choice(self, body: list[Line], i: int) -> int:
        group = []
        while i < len(body) and body[i].kind is LineKind.CHECKBOX:
            group.append(body[i])
            i += 1
        while i < len(body) and not clean(body[i].text):
            i += 1  # blank lines after "inne ……" belong to the other option
        options = ["Inne" if OTHER.match(clean(line.text)) else clean(line.text) for line in group]
        label = self.prompt[0] if self.prompt else "Wybierz"
        raw_prompt = next(
            (line.text for line in body if self.prompt and line.id == self.prompt[1]), ""
        )
        multiple = bool(MULTIPLE.search(raw_prompt))
        field_type = FieldType.CHECKBOX if multiple else FieldType.RADIO
        if field_type is FieldType.RADIO and len(options) > 5:
            field_type = FieldType.SELECT
        src = [self.prompt[1]] if self.prompt else []
        choice = self._field(label, field_type, [], src + [line.id for line in group], options)
        if "Inne" in options:
            self._field(
                "Podaj inny zakres",
                FieldType.TEXT_FIELD,
                [],
                [group[-1].id],
                show_if=Cond(field=choice.key, value="Inne"),
            )
        self.prompt = None
        return i

    def _blank(self, body: list[Line], i: int, label: str) -> int:
        src = [body[i].id]
        if not label and self.prompt:
            label, src = self.prompt[0], [self.prompt[1], *src]
        self.prompt = None
        if not label or COVERED.search(label):
            return i + 1
        field_type, validators = classify(label)
        continued = i + 1 < len(body) and not clean(body[i + 1].text)
        if continued and field_type is FieldType.TEXT_FIELD and not validators:
            field_type = FieldType.TEXTAREA
        self._field(label, field_type, validators, src)
        return i + 2 if continued else i + 1

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
                [src for _, src in self.consents],
                consents=[Consent(text=text) for text, _ in self.consents],
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
