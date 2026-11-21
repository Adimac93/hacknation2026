"""Model client and the three model steps; the model returns IR only, never the final JSON.

The client sends only the part of the OpenAI chat API that EdenAI and llama-server share:
messages, temperature, seed, max_tokens and response_format with a JSON schema.
"""

import logging
import re
import time
from enum import StrEnum
from typing import Any, NamedTuple

import httpx
from pydantic import BaseModel, ConfigDict

from formcompiler.compiler import slugify
from formcompiler.config import Settings
from formcompiler.heuristics import Analysis
from formcompiler.ir import (
    CHOICE_TYPES,
    Addressee,
    Applicant,
    Cond,
    FieldIR,
    FieldType,
    PageIR,
    SectionIR,
    Validator,
)
from formcompiler.sections import LIBRARY, RESERVED_KEYS, assemble

SEED = 7
INVENTORY_MAX_TOKENS = 4096
MAX_KEY_LENGTH = 60
MAX_TITLE_LENGTH = 255
TITLE_WORDS = ("Wniosek", "Zgłoszenie", "Deklaracja", "Oświadczenie")
LINE_ID = re.compile(r"^L\d+$")
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """The model did not give a usable answer; the caller falls back to heuristics."""


class Usage(NamedTuple):
    prompt_tokens: int
    completion_tokens: int


class Completion[T: BaseModel](NamedTuple):
    parsed: T
    usage: Usage
    elapsed_s: float
    attempts: int


def flat_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema with definitions inlined, every property required and no extra keys.

    Strict structured output (and llama-server's grammar) wants a closed, flat schema.
    """
    root = model.model_json_schema()
    definitions: dict[str, Any] = root.pop("$defs", {})

    def inline(node: Any) -> Any:
        if isinstance(node, list):
            return [inline(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            target = definitions[node["$ref"].rsplit("/", 1)[-1]]
            rest = {k: v for k, v in node.items() if k != "$ref"}
            return inline(target | rest)
        # Drop the "title" and "default" keywords; names under "properties" are data, kept.
        out = {k: inline(v) for k, v in node.items() if k not in {"title", "default"}}
        if "properties" in node:
            out["properties"] = {k: inline(v) for k, v in node["properties"].items()}
        if out.get("type") == "object" and "properties" in out:
            out["required"] = list(out["properties"])
            out["additionalProperties"] = False
        return out

    result: dict[str, Any] = inline(root)
    return result


def request_json[T: BaseModel](
    settings: Settings,
    system: str,
    user: str,
    schema: type[T],
    max_tokens: int,
    *,
    transport: httpx.BaseTransport | None = None,
) -> Completion[T]:
    """One chat completion constrained to `schema`, validated, with a single retry."""
    body = {
        "model": settings.llm_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "seed": SEED,
        "max_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "strict": True, "schema": flat_schema(schema)},
        },
    }
    headers = {}
    if key := settings.llm_api_key.get_secret_value():
        headers["Authorization"] = f"Bearer {key}"
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    started = time.perf_counter()
    last_error = "no attempt"
    with httpx.Client(transport=transport, timeout=settings.llm_timeout_s) as client:
        for attempt in (1, 2):
            try:
                response = client.post(url, json=body, headers=headers)
            except httpx.TransportError as exc:
                last_error = type(exc).__name__
                logger.warning("llm attempt=%d network error=%s", attempt, last_error)
                continue
            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}"
                logger.warning("llm attempt=%d status=%d", attempt, response.status_code)
                continue
            if response.is_error:
                raise LLMError(f"HTTP {response.status_code}")
            try:
                parsed, usage = _parse(response, schema)
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                last_error = f"invalid answer: {type(exc).__name__}"
                logger.warning("llm attempt=%d %s", attempt, last_error)
                continue
            elapsed = time.perf_counter() - started
            logger.info(
                "llm model=%s attempt=%d tokens=%d+%d time=%.1fs",
                settings.llm_model,
                attempt,
                usage.prompt_tokens,
                usage.completion_tokens,
                elapsed,
            )
            return Completion(parsed, usage, elapsed, attempt)
    raise LLMError(f"no usable answer after 2 attempts ({last_error})")


def _parse[T: BaseModel](response: httpx.Response, schema: type[T]) -> tuple[T, Usage]:
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise TypeError("message content is not text")
    # Some servers wrap JSON in a Markdown fence even with a schema; ValidationError is a
    # ValueError, so a wrong shape counts as an invalid answer.
    parsed = schema.model_validate_json(FENCE.sub("", content.strip()))
    usage = payload.get("usage") or {}
    return parsed, Usage(int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)))


def complete_json[T: BaseModel](
    settings: Settings,
    system: str,
    user: str,
    schema: type[T],
    max_tokens: int,
    *,
    transport: httpx.BaseTransport | None = None,
) -> T:
    return request_json(settings, system, user, schema, max_tokens, transport=transport).parsed


# --- Step A: inventory ---------------------------------------------------------------------


class Dictionary(StrEnum):
    KRAJE = "Kraje"
    TERYT_DOWODOWY = "TERYT_DOWODOWY"
    TERYT_4G_DOWODOWY = "TERYT_4G_DOWODOWY"
    WOJEWODZTWO = "Województwo"
    POWIAT = "Powiat"
    GMINA = "Gmina"
    MIEJSCOWOSC = "Miejscowość"
    NUMERY_KIERUNKOWE = "Numery kierunkowe"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ShowIfOption(_Model):
    """The field is shown only when choice field `field_key` has the answer `value`."""

    field_key: str
    value: str


class InventoryField(_Model):
    page: str
    section: str
    key: str
    label: str
    type: FieldType
    required: bool = False
    validators: list[Validator] = []
    options: list[str] = []
    dictionary: Dictionary | None = None
    show_if_option: ShowIfOption | None = None
    src: list[str] = []


class InventoryIR(_Model):
    title: str
    addressee: Addressee | None = None
    applicant: Applicant = Applicant()
    fields: list[InventoryField] = []


class Example(NamedTuple):
    name: str
    document: str
    answer: InventoryIR


# Few-shot examples come only from the reference forms 1 and 5 (decision D12). Inputs are
# shortened blanks; answers follow the reference JSON, with `required` read from the blank.
REF1 = Example(
    name="ref1",
    document="""\
--- strona 1 ---
L1 ………………………………
L2 (data)
L3 Wnioskodawca: Adresat:
L4 (imię i nazwisko/nazwa wnioskodawcy) Wójt Gminy Elbląg
L5 ul. Browarna 85
L6 82-300 Elbląg
L7 (adres)
L8 (nr telefonu/adres e-mail)1)
L9 # WNIOSEK O USTALENIE NUMERU PORZĄDKOWEGO
L10 Wnoszę o ustalenie numeru porządkowego budynkowi zlokalizowanemu
L11 w miejscowości……………….……………… przy ulicy1)……………….…………………
L12 nr ewidencyjny działki ……………w obrębie ………………………….……………………
L13 (podpis wnioskodawcy)2)
L14 1 ) Dane nieobowiązkowe.
L15 # KLAUZULA INFORMACYJNA
L16 1. Administratorem Państwa danych osobowych jest Gmina Elbląg.""",
    answer=InventoryIR(
        title="Wniosek o ustalenie numeru porządkowego nieruchomości",
        addressee=Addressee(name="Wójt Gminy Elbląg", kind="ORGAN"),
        applicant=Applicant(persons=True, entities=True, proxy=True),
        fields=[
            InventoryField(
                page="Informacje o budynku",
                section="Lokalizacja budynku",
                key=key,
                label=label,
                type=FieldType.TEXT_FIELD,
                required=required,
                src=[src],
            )
            for key, label, required, src in [
                ("miejscowosc", "Miejscowość", True, "L11"),
                ("ulica_budynku", "Ulica", False, "L11"),
                ("numer_ewidencyjny_dzialki", "Numer ewidencyjny działki", True, "L12"),
                ("obreb_numer", "Obręb", True, "L12"),
            ]
        ],
    ),
)

REF5 = Example(
    name="ref5",
    document="""\
--- strona 1 ---
L1 Ulan-Majorat, dnia....................................
L2 Wnioskodawca:
L3 Nazwisko i imię/Nazwa firmy
L4 adres zamieszkania/siedziba firmy
L5 PESEL *.................................................
L6 NIP * ......................................................
L7 Urząd Gminy
L8 Ulan-Majorat
L9 Ulan-Majorat 57
L10 21-307 Ulan-Majorat
L11 # WNIOSEK
L12 # o stwierdzenie nadpłaty podatku
L13 Na podstawie art. 75 ustawy z dnia 29 sierpnia 1997 r. - Ordynacja podatkowa
L14 (Dz. U. z 2025 r. poz. 111 ze zm.) wnoszę o stwierdzenie nadpłaty z tytułu .......…………….
L15 .................................................... w kwocie …...........................
L16 (rodzaj podatku)
L17 Uzasadnienie:
L18 ................................................................................................
L19 Kwotę nadpłaty proszę:
L20 1) zaliczyć na poczet przyszłego zobowiązania podatkowego z tytułu ……….……………
L21 2) zwrócić przelewem na wskazany rachunek
L22 ....................……...............................
L23 podpis wnioskodawcy lub osoby upoważnionej
L24 w załączeniu:
L25 1) korekta deklaracji
L26 2) ..................................................................
L27 *Numer PESEL wpisują podatnicy będący osobami fizycznymi objętymi rejestrem PESEL""",
    answer=InventoryIR(
        title="Wniosek o stwierdzenie nadpłaty podatku",
        addressee=Addressee(name="Urząd Gminy Ulan-Majorat", kind="URZAD"),
        applicant=Applicant(persons=True, entities=True, proxy=True),
        fields=[
            InventoryField(
                page="Informacje o nadpłacie",
                section="Informacje o nadpłacie",
                key="podatek_ktorego_dotyczy_nadplata",
                label="Podatek, którego dotyczy nadpłata",
                type=FieldType.TEXT_FIELD,
                required=True,
                src=["L14", "L16"],
            ),
            InventoryField(
                page="Informacje o nadpłacie",
                section="Informacje o nadpłacie",
                key="kwota",
                label="Kwota",
                type=FieldType.NUMBER,
                required=True,
                src=["L15"],
            ),
            InventoryField(
                page="Informacje o nadpłacie",
                section="Informacje o nadpłacie",
                key="uzasadnienie",
                label="Uzasadnienie",
                type=FieldType.TEXTAREA,
                required=True,
                src=["L17", "L18"],
            ),
            InventoryField(
                page="Informacje o nadpłacie",
                section="Rozliczenie nadpłaty",
                key="wybierz_co_mamy_zrobic_z_nadplata",
                label="Wybierz, co mamy zrobić z nadpłatą",
                type=FieldType.RADIO,
                required=True,
                options=[
                    "Zaliczyć na poczet przyszłego zobowiązania podatkowego",
                    "Zwrócić przelewem na rachunek bankowy",
                ],
                src=["L19", "L20", "L21"],
            ),
            InventoryField(
                page="Informacje o nadpłacie",
                section="Rozliczenie nadpłaty",
                key="nazwa_podatku",
                label="Nazwa podatku",
                type=FieldType.TEXT_FIELD,
                show_if_option=ShowIfOption(
                    field_key="wybierz_co_mamy_zrobic_z_nadplata",
                    value="Zaliczyć na poczet przyszłego zobowiązania podatkowego",
                ),
                src=["L20"],
            ),
            InventoryField(
                page="Informacje o nadpłacie",
                section="Rozliczenie nadpłaty",
                key="numer_rachunku",
                label="Numer rachunku",
                type=FieldType.TEXT_FIELD,
                show_if_option=ShowIfOption(
                    field_key="wybierz_co_mamy_zrobic_z_nadplata",
                    value="Zwrócić przelewem na rachunek bankowy",
                ),
                src=["L21", "L22"],
            ),
            InventoryField(
                page="Informacje o nadpłacie",
                section="Korekta deklaracji",
                key="plik_deklaracji_podatkowej",
                label="Plik deklaracji podatkowej",
                type=FieldType.FILE_UPLOADER,
                src=["L24", "L25"],
            ),
        ],
    ),
)

EXAMPLES = (REF1, REF5)

RESERVED_LIST = ", ".join(sorted(RESERVED_KEYS))
INVENTORY_INSTRUCTIONS = f"""\
Jesteś projektantem formularzy elektronicznych dla Generatora Formularzy COI. Dostajesz tekst \
papierowego blankietu wniosku; każda linia ma identyfikator L<numer>, a „#” oznacza nagłówek. \
Zwracasz inwentarz pól nowego e-formularza jako JSON zgodny ze schematem.

Projektujesz formularz od nowa według standardów COI. Nie przepisujesz blankietu.

1. Sekcje predefiniowane. Każdy formularz dostaje gotową stronę „{LIBRARY.data_page_title}” \
(adresat, dane wnioskodawcy, adres, dane firmy, pełnomocnik, pełnomocnictwo, opłata skarbowa \
za pełnomocnictwo) i stronę „{LIBRARY.contact.title}” (telefon, e-mail, zgody, klauzula \
informacyjna). Tych pól NIE wypisuj: imię, nazwisko, nazwa firmy lub wnioskodawcy, PESEL, NIP, \
REGON wnioskodawcy, adres zamieszkania lub siedziby, telefon, e-mail, zgody, oświadczenia, \
klauzula RODO, pełnomocnictwo, opłata skarbowa. Zamiast tego ustaw:
- addressee: adresat z bloku adresata blankietu, bez adresu i kodu pocztowego; gdy adresatem \
jest funkcja (Wójt, Burmistrz, Prezydent Miasta, Starosta, Marszałek), kind=ORGAN, a name to \
funkcja z nazwą jednostki, np. „Wójt Gminy Elbląg”; gdy adresatem jest urząd, kind=URZAD, a name \
to pełna nazwa ze wszystkich linii bloku, np. „Urząd Gminy Ulan-Majorat”, nigdy samo „Urząd \
Gminy”; null, gdy blankiet go nie podaje,
- applicant.persons: wniosek może złożyć osoba fizyczna,
- applicant.entities: wniosek może złożyć firma, osoba prawna lub jednostka (np. „nazwa \
firmy”, „siedziba”, „nazwa wnioskodawcy”, NIP),
- applicant.proxy: wniosek może złożyć pełnomocnik; false tylko wtedy, gdy blankiet wprost \
to wyklucza.

2. Pomijasz: podpis, pieczęć, „miejscowość i data”, datę wniosku, pola „wypełnia urząd”, \
przypisy, pouczenia, podstawy prawne, klauzule.

3. Wypisujesz każdą daną, którą wnioskodawca podaje w samej sprawie. Dla każdego pola:
- label: krótko i prostym językiem, bez dwukropka, wielka litera tylko na początku,
- key: snake_case z liter ASCII bez polskich znaków, cyfr i „_”, do {MAX_KEY_LENGTH} znaków, \
unikalny; nie używaj kluczy zajętych przez sekcje predefiniowane: {RESERVED_LIST},
- type: TEXT_FIELD krótki tekst; TEXTAREA dłuższy opis lub uzasadnienie; NUMBER kwota lub \
liczba; DATEPICKER data; RADIO jeden wybór z kilku wariantów; CHECKBOX wiele wyborów; SELECT \
jeden wybór z długiej listy albo ze słownika; FILE_UPLOADER załącznik („w załączeniu”, \
„załączam”); TEXT_BLOCK informacja dla wnioskodawcy bez danych do wpisania; nie używaj \
CONSENT_SECTION ani INFO_SECTION,
- required: true, gdy bez tej danej nie da się załatwić sprawy; false, gdy blankiet oznacza \
ją jako nieobowiązkową albo potrzebną tylko w jednym wariancie,
- validators: PESEL, NIP, REGON, EMAIL, ZIP_CODE i inne tylko dla pól tego rodzaju; REQUIRED \
nie wpisuj, od tego jest required,
- options: warianty wyboru pełnymi zdaniami, tylko dla RADIO, CHECKBOX i SELECT; puste dla \
innych typów i dla pól ze słownikiem,
- show_if_option: gdy pole jest potrzebne tylko przy jednym wariancie wyboru (np. numer \
rachunku tylko przy zwrocie przelewem), wypisz je zaraz po polu RADIO i ustaw field_key na \
klucz tego pola RADIO, a value na dokładny tekst opcji; dla pozostałych pól null,
- dictionary: słownik dla pola wyboru (Kraje dla kraju, Województwo, Powiat, Gmina, \
Miejscowość dla jednostek adresowych, Numery kierunkowe dla prefiksu telefonu), inaczej null,
- page i section: tytuły strony i sekcji tematycznej, krótko; zwykle jedna strona, a na niej \
kilka sekcji po kilka pól,
- src: identyfikatory linii, z których pochodzi pole.

Załączniki: jedno pole FILE_UPLOADER na każdy załącznik nazwany na blankiecie. Nie twórz pól \
dla pustych, wykropkowanych pozycji listy załączników ani dla liczby załączników.

4. title zaczyna się od „Wniosek”, „Zgłoszenie”, „Deklaracja” albo „Oświadczenie”, pisany \
zwykłą wielkością liter, bez skrótów.
"""


def render_examples(examples: tuple[Example, ...]) -> str:
    return "\n\n".join(
        f"Przykład {i}\nBlankiet:\n{e.document}\nOdpowiedź:\n" + e.answer.model_dump_json()
        for i, e in enumerate(examples, start=1)
    )


def inventory_messages(
    document_text: str, examples: tuple[Example, ...] = EXAMPLES
) -> tuple[str, str]:
    """System prompt (static, so the server can cache it) and the user message."""
    system = INVENTORY_INSTRUCTIONS
    if examples:
        system += "\n" + render_examples(examples)
    return system, f"Blankiet:\n{document_text}\nOdpowiedź:"


def inventory(
    settings: Settings, document_text: str, *, transport: httpx.BaseTransport | None = None
) -> InventoryIR:
    """Step A: title, addressee, applicant flags and a flat list of subject fields."""
    system, user = inventory_messages(document_text)
    return complete_json(
        settings, system, user, InventoryIR, INVENTORY_MAX_TOKENS, transport=transport
    )


def to_subject_pages(inv: InventoryIR) -> list[PageIR]:
    """Group the flat inventory into pages and sections with unique, non-reserved keys."""
    taken = set(RESERVED_KEYS)
    built: list[tuple[InventoryField, FieldIR]] = []
    reserved_titles = {LIBRARY.data_page_title, LIBRARY.contact.title, LIBRARY.finish.title}
    grouped: dict[str, dict[str, list[InventoryField]]] = {}
    for f in inv.fields:
        page = f.page.strip() or "Informacje"
        grouped.setdefault(page, {}).setdefault(f.section.strip() or page, []).append(f)

    pages = []
    for page_title, sections in grouped.items():
        title = page_title
        while title in reserved_titles:
            title += " (szczegóły)"
        reserved_titles.add(title)
        page_sections = []
        for section_title, fields in sections.items():
            # Consents come from the predefined contact page, never from the model.
            kept = [f for f in fields if f.type is not FieldType.CONSENT_SECTION]
            if kept:
                key = _claim(section_title, "sekcja", taken)
                items = [_field(f, taken) for f in kept]
                built += zip(kept, items, strict=True)
                page_sections.append(SectionIR(key=key, title=section_title, fields=items))
        if page_sections:
            pages.append(PageIR(title=title, sections=page_sections))
    return _with_conditions(pages, built)


def _with_conditions(
    pages: list[PageIR], built: list[tuple[InventoryField, FieldIR]]
) -> list[PageIR]:
    """Turn `show_if_option` into IR conditions; references to unknown fields or values drop."""
    by_key: dict[str, FieldIR] = {}
    for raw, field in built:
        by_key.setdefault(field.key, field)
        by_key.setdefault(raw.key, field)
    conditions: dict[str, Cond] = {}
    for raw, field in built:
        ref = raw.show_if_option
        if ref is None:
            continue
        target = by_key.get(ref.field_key) or by_key.get(slugify(ref.field_key))
        if target is None or target.key == field.key or target.type not in CHOICE_TYPES:
            continue
        value = next(
            (o for o in target.options if o.casefold() == ref.value.strip().casefold()), None
        )
        reverse = conditions.get(target.key)
        if value is None or (reverse is not None and reverse.field == field.key):
            continue
        conditions[field.key] = Cond(field=target.key, value=value)
    if not conditions:
        return pages
    return [
        page.model_copy(
            update={
                "sections": [
                    section.model_copy(
                        update={
                            "fields": [
                                f.model_copy(update={"show_if": conditions.get(f.key)})
                                for f in section.fields
                            ]
                        }
                    )
                    for section in page.sections
                ]
            }
        )
        for page in pages
    ]


def refine(
    settings: Settings,
    document_text: str,
    analysis: Analysis,
    *,
    transport: httpx.BaseTransport | None = None,
) -> Analysis:
    """Step A on top of the rules-mode analysis, which fills whatever the model leaves out.

    Raises LLMError when the model fails or its answer does not assemble into a valid form,
    so the caller keeps `analysis`.
    """
    inv = inventory(settings, document_text, transport=transport)
    title = inv.title.strip()
    if not title.startswith(TITLE_WORDS) or len(title) > MAX_TITLE_LENGTH:
        title = analysis.title
    refined = Analysis(
        title=title,
        addressee=inv.addressee or analysis.addressee,
        applicant=inv.applicant,
        pages=to_subject_pages(inv) or analysis.pages,
    )
    try:
        assemble(refined.title, refined.addressee, refined.applicant, refined.pages)
    except ValueError as exc:
        raise LLMError(f"answer does not assemble: {type(exc).__name__}") from None
    return refined


def _claim(text: str, fallback: str, taken: set[str]) -> str:
    """A valid key from `text`, made unique against `taken` and recorded there."""
    base = slugify(text)[:MAX_KEY_LENGTH].strip("_") or fallback
    if not base[0].isalpha():
        base = f"{fallback}_{base}"[:MAX_KEY_LENGTH]
    key, n = base, 2
    while key in taken:
        suffix = f"_{n}"
        key = base[: MAX_KEY_LENGTH - len(suffix)] + suffix
        n += 1
    taken.add(key)
    return key


def _field(f: InventoryField, taken: set[str]) -> FieldIR:
    kind: FieldType = f.type
    dictionary = f.dictionary.value if f.dictionary and kind in CHOICE_TYPES else None
    options = [] if dictionary else list(dict.fromkeys(o.strip() for o in f.options if o.strip()))
    if kind not in CHOICE_TYPES:
        options = []
    elif kind in {FieldType.RADIO, FieldType.SELECT} and not dictionary and len(options) < 2:
        kind, options = FieldType.TEXT_FIELD, []
    validators = [v for v in dict.fromkeys(f.validators) if v is not Validator.REQUIRED]
    return FieldIR(
        key=_claim(f.key or f.label, "pole", taken),
        label=f.label.strip(),
        type=kind,
        required=f.required or Validator.REQUIRED in f.validators,
        validators=validators,
        options=options,
        dictionary=dictionary,
        src=[s for s in f.src if LINE_ID.match(s)],
    )
