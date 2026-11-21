"""Model client and the three model steps; the model returns IR only, never the final JSON.

The client sends only the part of the OpenAI chat API that EdenAI and llama-server share:
messages, temperature, seed, max_tokens and response_format with a JSON schema.
"""

import difflib
import json
import logging
import re
import time
from enum import StrEnum
from typing import Any, NamedTuple

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

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
# Step A completion budget, measured 2026-11-21 on Qwen3.5-9B via EdenAI. One field object
# costs 83-96 completion tokens. Complete answers used at most 0.36 tokens per character of
# the linearised blank (form 8: 6359 tokens for 17 747 characters, form 6: 1742 / 5039,
# form 7: 1080 / 6542, form 4: 960 / 1594). Rules mode undercounts fields (form 8: 8 rules
# fields against 66 model fields; its raster: 3), while OCR keeps 75-100% of the text, so the
# budget follows whichever signal is larger. A looping answer runs to the budget at ~140
# tokens/s; the cap of 8192 (form 8 needs ~6.4k) costs ~60 s, the floor ~15 s.
INVENTORY_BASE_TOKENS = 1024
INVENTORY_TOKENS_PER_FIELD = 150
INVENTORY_TOKENS_PER_CHAR = 0.45
INVENTORY_MIN_TOKENS = 2048
INVENTORY_MAX_TOKENS = 8192
MAX_KEY_LENGTH = 60
MAX_TITLE_LENGTH = 255
TITLE_WORDS = ("Wniosek", "Zgłoszenie", "Deklaracja", "Oświadczenie")
# An addressee named after an official is an ORGAN, one named after an office is an URZAD.
ORGAN_NAME = re.compile(r"^(Wójt|Burmistrz|Prezydent|Starosta|Marszałek|Zarząd)\b", re.IGNORECASE)
OFFICE_NAME = re.compile(r"^(Urząd|Starostwo)\b", re.IGNORECASE)
LINE_ID = re.compile(r"^L\d+$")
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """The model did not give a usable answer; the caller falls back to heuristics."""


class TruncatedAnswer(LLMError):
    """The answer hit max_tokens; `content` keeps the partial text for salvage, never logs."""

    def __init__(self, max_tokens: int, content: str) -> None:
        super().__init__(f"answer cut off at max_tokens={max_tokens}")
        self.content = content


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
            if (partial := _truncated(response)) is not None:
                # Deterministic request (temperature 0, fixed seed): a retry ends the same way.
                raise TruncatedAnswer(max_tokens, partial)
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


def _truncated(response: httpx.Response) -> str | None:
    """The partial answer text when the answer was cut off at max_tokens, else None."""
    try:
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") != "length":
            return None
        content = choice.get("message", {}).get("content")
    except ValueError, KeyError, IndexError, TypeError, AttributeError:
        return None
    return content if isinstance(content, str) else ""


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
        # Flags follow the blank: "nazwa wnioskodawcy" admits entities, no word of a proxy.
        applicant=Applicant(persons=True, entities=True, proxy=False),
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
Gminy”; tylko z bloku adresata, nigdy z klauzuli informacyjnej ani z danych administratora; \
null, gdy blankiet go nie podaje,
- applicant.persons: wniosek może złożyć osoba fizyczna,
- applicant.entities: true tylko wtedy, gdy blankiet wprost dopuszcza firmę, osobę prawną lub \
jednostkę („nazwa firmy”, „siedziba”, „nazwa wnioskodawcy”, NIP, REGON, KRS); inaczej false,
- applicant.proxy: true tylko wtedy, gdy blankiet wspomina pełnomocnika albo osobę upoważnioną; \
inaczej false.

2. Pomijasz: podpis, pieczęć, „miejscowość i data”, datę wniosku, pola „wypełnia urząd”, \
przypisy, pouczenia, podstawy prawne, klauzule, oświadczenia do odhaczenia.

3. Wypisujesz każdą daną, którą wnioskodawca podaje w samej sprawie. Dla każdego pola:
- label: krótko i prostym językiem, bez dwukropka, wielka litera tylko na początku,
- key: snake_case z liter ASCII bez polskich znaków, cyfr i „_”, do {MAX_KEY_LENGTH} znaków, \
unikalny; nie używaj kluczy zajętych przez sekcje predefiniowane: {RESERVED_LIST},
- type: TEXT_FIELD krótki tekst; TEXTAREA dłuższy opis lub uzasadnienie; NUMBER kwota, \
liczba osób, powierzchnia lub inna liczba; DATEPICKER data; RADIO jeden wybór z kilku \
wariantów; CHECKBOX wiele wyborów; SELECT \
jeden wybór z długiej listy albo ze słownika; FILE_UPLOADER załącznik („w załączeniu”, \
„załączam”); TEXT_BLOCK informacja dla wnioskodawcy bez danych do wpisania; nie używaj \
CONSENT_SECTION ani INFO_SECTION,
- required: true, gdy bez tej danej nie da się załatwić sprawy; false, gdy blankiet oznacza \
ją jako nieobowiązkową albo potrzebną tylko w jednym wariancie,
- validators: PESEL, NIP, REGON, EMAIL, ZIP_CODE i inne tylko dla pól tego rodzaju; REQUIRED \
nie wpisuj, od tego jest required,
- options: warianty wyboru pełnymi zdaniami, tylko dla RADIO, CHECKBOX i SELECT; puste dla \
innych typów i dla pól ze słownikiem,
- show_if_option: tylko dla pola, które blankiet umieszcza wewnątrz jednego wariantu wyboru \
(np. numer rachunku w wariancie „zwrócić przelewem”, pole „inne……” przy opcji „inne”); wypisz \
je zaraz po polu wyboru, ustaw field_key na klucz tego pola, a value na dokładny tekst opcji; \
dla wszystkich innych pól null,
- dictionary: słownik dla pola wyboru (Kraje dla kraju, Województwo, Powiat, Gmina, \
Miejscowość dla jednostek adresowych, Numery kierunkowe dla prefiksu telefonu), inaczej null,
- page i section: tytuły strony i sekcji tematycznej, krótko i od przedmiotu sprawy (np. \
„Informacje o budynku”); zwykle jedna strona, a na niej kilka sekcji po kilka pól; tytuł \
strony nigdy nie zaczyna się od „Dane” ani „Kontakt”,
- src: identyfikatory linii, z których pochodzi pole.

Załączniki: jedno pole FILE_UPLOADER na każdy załącznik nazwany na blankiecie. Nie twórz pól \
dla pustych, wykropkowanych pozycji listy załączników ani dla liczby załączników.

Warianty do skreślenia: gdy blankiet zapisuje wybór jako „A/B*” z przypisem „niepotrzebne \
skreślić” (także w tytule), dodaj pole RADIO z opcjami A i B, np. „Wynajęcie” i „Użyczenie”.

4. title zaczyna się od „Wniosek”, „Zgłoszenie”, „Deklaracja” albo „Oświadczenie”, pisany \
zwykłą wielkością liter, bez skrótów.

5. Każde pole wypisz w fields dokładnie raz. Klucz (key) i etykieta (label) nie mogą się \
powtórzyć. Nie powtarzaj pola, które już wypisałeś; gdy wypiszesz ostatnie pole blankietu, \
zamknij listę fields.
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
    settings: Settings,
    document_text: str,
    *,
    max_tokens: int = INVENTORY_MAX_TOKENS,
    transport: httpx.BaseTransport | None = None,
) -> InventoryIR:
    """Step A: title, addressee, applicant flags and a flat list of subject fields."""
    system, user = inventory_messages(document_text)
    return complete_json(settings, system, user, InventoryIR, max_tokens, transport=transport)


def rules_fields(analysis: Analysis) -> list[FieldIR]:
    return [f for page in analysis.pages for s in page.sections for f in s.fields]


def inventory_budget(analysis: Analysis, document_text: str) -> int:
    """max_tokens for step A from the rules-mode field count and the length of the blank."""
    need = max(
        INVENTORY_TOKENS_PER_FIELD * len(rules_fields(analysis)),
        round(INVENTORY_TOKENS_PER_CHAR * len(document_text)),
    )
    return min(max(need + INVENTORY_BASE_TOKENS, INVENTORY_MIN_TOKENS), INVENTORY_MAX_TOKENS)


_DECODER = json.JSONDecoder()
_SPACE = re.compile(r"\s*")


def complete_parts(content: str) -> tuple[dict[str, Any], list[Any]]:
    """Top-level members and `fields` items of a JSON object cut off mid-way; complete ones only."""
    text = FENCE.sub("", content.strip())
    members: dict[str, Any] = {}
    items: list[Any] = []

    def skip(i: int) -> int:
        match = _SPACE.match(text, i)
        return match.end() if match else i

    i = skip(0)
    if not text.startswith("{", i):
        return members, items
    i += 1
    try:
        while True:
            key, i = _DECODER.raw_decode(text, skip(i))
            i = skip(i)
            if not isinstance(key, str) or not text.startswith(":", i):
                break
            i = skip(i + 1)
            if key == "fields" and text.startswith("[", i):
                i += 1
                while not text.startswith("]", i := skip(i)):
                    item, i = _DECODER.raw_decode(text, i)
                    items.append(item)
                    i = skip(i)
                    if text.startswith(",", i):
                        i += 1
                i += 1
            else:
                members[key], i = _DECODER.raw_decode(text, i)
            i = skip(i)
            if not text.startswith(",", i):
                break
            i += 1
    except ValueError:
        pass  # the cut: everything before it is kept
    return members, items


def covers_form(fields: list[InventoryField], analysis: Analysis) -> bool:
    """The salvaged fields plausibly cover the whole form, judged against rules mode.

    The fields must reach at least the line where the last rules-mode input field starts (the
    model got through the blank as far as rules mode did), and after cleanup they must number
    at least half the rules input fields (the model merges some, but never most: form 6 gave
    19-21 for 21). Counting after cleanup rejects near-duplicates that survived the loop check.
    """
    inputs = [f for f in rules_fields(analysis) if f.type is not FieldType.TEXT_BLOCK]
    starts = [min(lines) for f in inputs if (lines := _lines(f.src))]
    reach = [max(lines) for f in fields if (lines := _lines(f.src))]
    kept = clean_inventory(InventoryIR(title="", fields=fields)).fields
    return bool(starts and reach) and max(reach) >= max(starts) and 2 * len(kept) >= len(inputs)


def salvage(content: str, analysis: Analysis) -> InventoryIR | None:
    """Complete fields of a cut-off answer before its loop, if they cover the form.

    A cut-off answer has run into a loop: the same field again and again under the same key
    (form 9 repeated its second field 85 times) or under numbered keys (`..._4` to `..._33`),
    or one endless `src` list inside a field. Fields are kept up to the first repeated key;
    copies under new keys are left to `clean_inventory`, and `covers_form` counts what it
    keeps. Header parts the answer lacks (the title comes last in practice) or gives in a
    wrong shape come from rules mode.
    """
    members, items = complete_parts(content)
    fields: list[InventoryField] = []
    for item in items:
        try:
            f = InventoryField.model_validate(item)
        except ValidationError:
            break
        if any(f.key == seen.key for seen in fields):
            break
        fields.append(f)
    if not covers_form(fields, analysis):
        return None
    header: dict[str, Any] = {
        "title": analysis.title,
        "addressee": analysis.addressee,
        "applicant": analysis.applicant,
    }
    for name, value in members.items():
        if name in header:
            try:
                InventoryIR.model_validate({**header, name: value})
            except ValidationError:
                continue
            header[name] = value
    return InventoryIR.model_validate({**header, "fields": fields})


def norm(text: str) -> str:
    return slugify(text).replace("_", " ")


# Library fields that describe the applicant or contact; address parts (street, town) are left
# out because subject pages legitimately ask for them, e.g. the location of a building.
ADDRESS_LABELS = frozenset(
    norm(label)
    for label in ["Ulica", "Miejscowość", "Kod pocztowy", "Numer budynku", "Numer lokalu", "Kraj"]
)
LIBRARY_FIELDS = [
    f
    for s in [*LIBRARY.addressee.values(), *LIBRARY.applicant, *LIBRARY.contact.sections]
    for f in s.fields
    if f.label.strip() and norm(f.label) not in ADDRESS_LABELS and f.dictionary is None
]
PERSONAL_LABELS = frozenset(norm(f.label) for f in LIBRARY_FIELDS) | frozenset(
    norm(label)
    for label in [
        "Imię i nazwisko",
        "Nazwisko i imię",
        "Imię i nazwisko wnioskodawcy",
        "PESEL",
        "Telefon",
        "Nr telefonu",
        "Numer telefonu wnioskodawcy",
        "E-mail",
        "Adres",
        "Adres zamieszkania",
        "Adres siedziby",
        "Adres do korespondencji",
        "Nazwa firmy",
        "Nazwa wnioskodawcy",
        "REGON",
    ]
)
PERSONAL_KEYS = frozenset(f.key for f in LIBRARY_FIELDS)
PROXY_LABEL = re.compile(r"pełnomocni", re.IGNORECASE)
# Address parts are the applicant's own when their section is about the applicant.
APPLICANT_SECTION = re.compile(r"wnioskodaw|identyfikac|zamieszka|siedzib", re.IGNORECASE)
ADDRESS_PARTS = ADDRESS_LABELS | frozenset(
    norm(label) for label in ["Nr domu", "Numer domu", "Nr lokalu", "Adres"]
)
STATEMENT = re.compile(
    r"^(oświadcz|zapozna|zobowiąz|wyrażam|odpowiadam|ponosz|przyjmuj)", re.IGNORECASE
)
# Never on the e-form (CLAUDE.md, output contract): signatures, stamps, place and date of filling,
# office-only fields. The prompt says so too, but the model does not always listen.
OFF_FORM = re.compile(
    r"podpis|pieczęć|pieczęci|pieczątk|miejscowość i data|data (wypełnienia|złożenia|wpływu)"
    r"|wypełnia (urząd|organ|pracownik)",
    re.IGNORECASE,
)
LIBRARY_PAGE = re.compile(r"^(dane|kontakt|zgod|strona końcowa|podsumowanie)", re.IGNORECASE)
SUBJECT_PAGE = "Szczegóły wniosku"
LINE_NUMBER = re.compile(r"^L(\d+)$")
PROXY_TRACE = re.compile(r"pełnomocni|upoważnion", re.IGNORECASE)
ENTITY_TRACE = re.compile(
    r"\b(NIP|REGON|KRS)\b|osob\w* prawn|nazwa (firmy|podmiotu|przedsiębiorcy|wnioskodawcy)"
    r"|przedsiębiorc|siedzib",
    re.IGNORECASE,
)
TITLE_LINE = re.compile(
    r"^(L\d+ )?(# )?(wniosek|deklaracja|zgłoszenie|oświadczenie)\b", re.IGNORECASE
)
NAME_WORD = re.compile(r"[^\W\d_]{3,}")


def is_library_duplicate(f: InventoryField) -> bool:
    """The field repeats what the predefined applicant or contact sections already ask."""
    label = norm(f.label)
    return (
        (label in ADDRESS_PARTS and bool(APPLICANT_SECTION.search(f.section)))
        or f.key in PERSONAL_KEYS
        or label in PERSONAL_LABELS
        or any(difflib.SequenceMatcher(None, label, p).ratio() >= 0.9 for p in PERSONAL_LABELS)
        or bool(PROXY_LABEL.search(f.label))
    )


def clean_inventory(inv: InventoryIR) -> InventoryIR:
    """Deterministic cleanup of the model answer before it becomes IR.

    Drops consents, ticked statements, signatures and other off-form fields, and fields the
    predefined sections cover, turns choices
    without options into text fields, removes duplicate labels within a section, moves fields
    from pages titled like the predefined pages onto one subject page, and keeps `show_if_option`
    only when the field comes from the lines of the choice it depends on.
    """
    allowed_pages = [f.page.strip() for f in inv.fields if _subject_page(f.page)]
    subject_page = allowed_pages[0] if allowed_pages else SUBJECT_PAGE
    kept: list[InventoryField] = []
    seen: set[tuple[str, str, str]] = set()
    for f in inv.fields:
        if f.type is FieldType.CONSENT_SECTION or is_library_duplicate(f):
            continue
        if OFF_FORM.search(f.label):
            continue
        no_options = not f.options and f.dictionary is None
        if f.type in CHOICE_TYPES and no_options:
            if f.type is FieldType.CHECKBOX and STATEMENT.match(f.label.strip()):
                continue
            f = f.model_copy(update={"type": FieldType.TEXT_FIELD})
        page = f.page.strip() if _subject_page(f.page) else subject_page
        identity = (page, f.section.strip(), norm(f.label))
        if identity in seen:
            continue
        seen.add(identity)
        kept.append(f.model_copy(update={"page": page}))
    by_key = {f.key: f for f in kept}
    return inv.model_copy(update={"fields": [_checked_condition(f, by_key) for f in kept]})


def _subject_page(title: str) -> bool:
    library = {LIBRARY.data_page_title, LIBRARY.contact.title, LIBRARY.finish.title}
    return (
        bool(title.strip())
        and title.strip() not in library
        and not LIBRARY_PAGE.match(title.strip())
    )


def _lines(src: list[str]) -> list[int]:
    return [int(m.group(1)) for s in src if (m := LINE_NUMBER.match(s))]


def _checked_condition(f: InventoryField, by_key: dict[str, InventoryField]) -> InventoryField:
    """Keep a condition only if the field's lines lie within the lines of its choice field."""
    ref = f.show_if_option
    if ref is None:
        return f
    target = by_key.get(ref.field_key)
    own, choice = _lines(f.src), _lines(target.src) if target else []
    if own and choice and any(min(choice) <= n <= max(choice) for n in own):
        return f
    return f.model_copy(update={"show_if_option": None})


def header_text(document_text: str) -> str | None:
    """Lines above the form title, where the addressee block sits; None without a title."""
    lines = document_text.splitlines()
    at = next((i for i, line in enumerate(lines) if TITLE_LINE.match(line.strip())), None)
    return None if at is None else "\n".join(lines[:at])


def addressee_in_header(addressee: Addressee | None, document_text: str) -> bool:
    """Every word of the name appears above the title (prefix match tolerates inflection)."""
    if addressee is None:
        return False
    header = header_text(document_text)
    if header is None:
        return True
    words = {norm(w) for w in NAME_WORD.findall(header)}
    return all(any(h[:5] == norm(w)[:5] for h in words) for w in NAME_WORD.findall(addressee.name))


def applicant_flags(model: Applicant, rules: Applicant, document_text: str) -> Applicant:
    """Model flags for entities and proxy only where the blank shows a trace of them."""
    return Applicant(
        persons=model.persons,
        entities=model.entities if ENTITY_TRACE.search(document_text) else rules.entities,
        proxy=model.proxy if PROXY_TRACE.search(document_text) else rules.proxy,
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


def _consistent(addressee: Addressee | None) -> Addressee | None:
    """Fix the addressee kind when the name says otherwise; the model often mixes them up."""
    if addressee is None or not addressee.name.strip():
        return None
    name = addressee.name.strip()
    kind = addressee.kind
    if ORGAN_NAME.match(name):
        kind = "ORGAN"
    elif OFFICE_NAME.match(name):
        kind = "URZAD"
    return Addressee(name=name, kind=kind)


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
    budget = inventory_budget(analysis, document_text)
    try:
        inv = inventory(settings, document_text, max_tokens=budget, transport=transport)
    except TruncatedAnswer as exc:
        salvaged = salvage(exc.content, analysis)
        if salvaged is None:
            raise
        logger.warning(
            "llm answer cut off at max_tokens=%d, salvaged %d fields", budget, len(salvaged.fields)
        )
        inv = salvaged
    title = inv.title.strip()
    if not title.startswith(TITLE_WORDS) or len(title) > MAX_TITLE_LENGTH:
        title = analysis.title
    addressee = _consistent(inv.addressee)
    if not addressee_in_header(addressee, document_text):
        addressee = analysis.addressee
    refined = Analysis(
        title=title,
        addressee=addressee,
        applicant=applicant_flags(inv.applicant, analysis.applicant, document_text),
        pages=to_subject_pages(clean_inventory(inv)) or analysis.pages,
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
    elif not dictionary and (
        not options or (kind in {FieldType.RADIO, FieldType.SELECT} and len(options) < 2)
    ):
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
