import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from formcompiler.config import Settings
from formcompiler.heuristics import Analysis
from formcompiler.ir import Addressee, Applicant, Cond, FieldType, PageIR, SectionIR, Validator
from formcompiler.llm import (
    EXAMPLES,
    SEED,
    SUBJECT_PAGE,
    InventoryField,
    InventoryIR,
    LLMError,
    ShowIfOption,
    addressee_in_header,
    applicant_flags,
    clean_inventory,
    flat_schema,
    header_text,
    inventory,
    refine,
    request_json,
    to_subject_pages,
)
from formcompiler.sections import RESERVED_KEYS, assemble

KEY = "klucz-testowy-123"
ANSWER = InventoryIR(
    title="Wniosek o wydanie zaświadczenia",
    addressee=Addressee(name="Wójt Gminy Testowej", kind="ORGAN"),
    applicant=Applicant(persons=True, entities=False, proxy=True),
    fields=[
        InventoryField(
            page="Zaświadczenie",
            section="Cel",
            key="cel_zaswiadczenia",
            label="Cel zaświadczenia",
            type=FieldType.TEXTAREA,
            src=["L3"],
        )
    ],
)

type Handler = Callable[[httpx.Request], httpx.Response]


def make(**env: Any) -> Settings:
    return Settings(_env_file=None, **({"llm_api_key": KEY} | env))


def completion(content: str, status: int = 200) -> httpx.Response:
    body = {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
    }
    return httpx.Response(status, json=body)


def scripted(*responses: httpx.Response | Exception) -> tuple[Handler, list[httpx.Request]]:
    """Transport handler that answers with `responses` in order and records the requests."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = responses[len(seen) - 1]
        if isinstance(item, Exception):
            raise item
        return item

    return handler, seen


def call(handler: Handler, **env: Any) -> Any:
    return request_json(
        make(**env), "system", "user", InventoryIR, 512, transport=httpx.MockTransport(handler)
    )


def walk(node: Any) -> Any:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def test_request_uses_only_the_shared_openai_subset() -> None:
    handler, seen = scripted(completion(ANSWER.model_dump_json()))

    result = call(handler, llm_model="mistralai/Ministral-3-8B-Instruct-2512")

    assert result.parsed == ANSWER
    assert (result.usage.prompt_tokens, result.usage.completion_tokens, result.attempts) == (
        100,
        20,
        1,
    )
    request = seen[0]
    assert str(request.url) == "http://localhost:8080/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert set(body) == {
        "model",
        "messages",
        "temperature",
        "seed",
        "max_tokens",
        "response_format",
    }
    assert body["model"] == "mistralai/Ministral-3-8B-Instruct-2512"
    assert (body["temperature"], body["seed"], body["max_tokens"]) == (0, SEED, 512)
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    response_format = body["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "InventoryIR"
    assert response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]
    assert "$ref" not in json.dumps(schema)
    assert "$defs" not in schema


def test_schema_is_closed_and_keeps_properties_named_like_keywords() -> None:
    schema = flat_schema(InventoryIR)

    assert list(schema["properties"]) == ["title", "addressee", "applicant", "fields"]
    objects = [n for n in walk(schema) if n.get("type") == "object"]
    assert len(objects) == 5
    field = schema["properties"]["fields"]["items"]["properties"]
    show_if = field["show_if_option"]["anyOf"]
    assert show_if[1] == {"type": "null"}
    assert show_if[0]["required"] == ["field_key", "value"]
    for node in objects:
        assert node["additionalProperties"] is False
        assert node["required"] == list(node["properties"])


def test_local_server_without_key_gets_no_authorization_header() -> None:
    handler, seen = scripted(completion(ANSWER.model_dump_json()))

    call(handler, llm_api_key="")

    assert "authorization" not in seen[0].headers


def test_answer_wrapped_in_markdown_fence_is_accepted() -> None:
    handler, _ = scripted(completion(f"```json\n{ANSWER.model_dump_json()}\n```"))

    assert call(handler).parsed == ANSWER


@pytest.mark.parametrize(
    "first",
    [
        httpx.Response(503),
        httpx.Response(429),
        completion("{nie json"),
        completion('{"title": "brak reszty pól", "fields": [{"key": 1}]}'),
        httpx.ConnectError("offline"),
        httpx.ReadTimeout("slow"),
    ],
    ids=["503", "429", "invalid-json", "wrong-shape", "network", "timeout"],
)
def test_one_retry_after_a_transient_failure(first: httpx.Response | Exception) -> None:
    handler, seen = scripted(first, completion(ANSWER.model_dump_json()))

    result = call(handler)

    assert (result.parsed, result.attempts, len(seen)) == (ANSWER, 2, 2)


@pytest.mark.parametrize(
    "failures",
    [
        (httpx.Response(503), httpx.Response(502)),
        (completion("{"), completion("[]")),
        (httpx.ConnectError("offline"), completion("{")),
    ],
    ids=["5xx", "invalid", "mixed"],
)
def test_second_failure_raises_llm_error(failures: tuple[Any, Any]) -> None:
    handler, seen = scripted(*failures)

    with pytest.raises(LLMError):
        call(handler)

    assert len(seen) == 2


def test_client_error_is_not_retried() -> None:
    handler, seen = scripted(httpx.Response(401, json={"error": "bad key"}))

    with pytest.raises(LLMError, match="401"):
        call(handler)

    assert len(seen) == 1


def test_api_key_and_answer_never_reach_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    handler, _ = scripted(
        httpx.Response(503), completion("{zepsute"), httpx.Response(503), httpx.Response(503)
    )
    with caplog.at_level("DEBUG"):
        with pytest.raises(LLMError):
            call(handler)
        good, _ = scripted(completion(ANSWER.model_dump_json()))
        call(good)

    assert caplog.records
    assert KEY not in caplog.text
    assert "zepsute" not in caplog.text
    assert "Cel zaświadczenia" not in caplog.text


def test_inventory_prompt_has_a_static_start_with_both_reference_examples() -> None:
    handler, seen = scripted(*(completion(ANSWER.model_dump_json()) for _ in range(2)))
    transport = httpx.MockTransport(handler)

    first = inventory(make(), "L1 Pierwszy blankiet", transport=transport)
    inventory(make(), "L1 Drugi blankiet", transport=transport)

    assert first == ANSWER
    systems = [json.loads(r.content)["messages"][0]["content"] for r in seen]
    users = [json.loads(r.content)["messages"][1]["content"] for r in seen]
    assert systems[0] == systems[1]
    assert all(e.answer.title in systems[0] for e in EXAMPLES)
    assert "Pierwszy blankiet" in users[0]
    assert "Pierwszy blankiet" not in systems[0]


def field(page: str, section: str, key: str, label: str = "Pole", **kw: Any) -> InventoryField:
    return InventoryField(
        page=page, section=section, key=key, label=label, type=kw.pop("type", "TEXT_FIELD"), **kw
    )


def test_subject_pages_group_by_page_then_section_in_order_of_appearance() -> None:
    inv = InventoryIR(
        title="Wniosek",
        fields=[
            field("Budynek", "Lokalizacja", "miejscowosc_budynku"),
            field("Budynek", "Opis", "opis_budynku"),
            field("Załączniki", "Pliki", "mapa", type="FILE_UPLOADER"),
            field("Budynek", "Lokalizacja", "numer_dzialki"),
        ],
    )

    pages = to_subject_pages(inv)

    assert [(p.title, [(s.key, [f.key for f in s.fields]) for s in p.sections]) for p in pages] == [
        (
            "Budynek",
            [("lokalizacja", ["miejscowosc_budynku", "numer_dzialki"]), ("opis", ["opis_budynku"])],
        ),
        ("Załączniki", [("pliki", ["mapa"])]),
    ]


def test_subject_keys_avoid_reserved_and_duplicate_keys() -> None:
    inv = InventoryIR(
        title="Wniosek",
        fields=[
            field("Dane", "Twoje dane", "imie", "Imię psa"),
            field("Pies", "Pies", "pies"),
            field("Pies", "Pies", "pies"),
            field("Pies", "Pies", "", "Rasa psa"),
            field("Pies", "Pies", "2_numer", "Numer"),
            field("Pies", "Pies", "Kolor Sierści!"),
        ],
    )

    pages = to_subject_pages(inv)

    keys = [s.key for p in pages for s in p.sections]
    keys += [f.key for p in pages for s in p.sections for f in s.fields]
    assert [p.title for p in pages] == ["Dane (szczegóły)", "Pies"]
    assert keys == [
        "twoje_dane_2",
        "pies",
        "imie_2",
        "pies_2",
        "pies_3",
        "rasa_psa",
        "pole_2_numer",
        "kolor_siersci",
    ]
    assert not RESERVED_KEYS & set(keys)
    assemble(inv.title, None, inv.applicant, pages)


def test_subject_fields_are_cleaned_to_valid_ir() -> None:
    inv = InventoryIR(
        title="Wniosek",
        fields=[
            field("S", "A", "jedna_opcja", type="RADIO", options=["Tak"]),
            field(
                "S", "A", "kraj_urodzenia", type="SELECT", dictionary="Kraje", options=["Polska"]
            ),
            field("S", "A", "tekst", dictionary="Kraje", options=["x"]),
            field("S", "A", "pesel", validators=[Validator.REQUIRED, Validator.PESEL]),
            field("S", "A", "zgoda", type="CONSENT_SECTION"),
            field("S", "A", "zrodla", src=["L3", "linia 4", "L12"]),
            field("S", "Zgody", "rodo", type="CONSENT_SECTION"),
        ],
    )

    [page] = to_subject_pages(inv)

    [section] = page.sections
    by_key = {f.key: f for f in section.fields}
    assert set(by_key) == {"jedna_opcja", "kraj_urodzenia", "tekst", "pesel", "zrodla"}
    assert (by_key["jedna_opcja"].type, by_key["jedna_opcja"].options) == (FieldType.TEXT_FIELD, [])
    assert (by_key["kraj_urodzenia"].dictionary, by_key["kraj_urodzenia"].options) == ("Kraje", [])
    assert (by_key["tekst"].dictionary, by_key["tekst"].options) == (None, [])
    assert (by_key["pesel"].required, by_key["pesel"].validators) == (True, [Validator.PESEL])
    assert by_key["zrodla"].src == ["L3", "L12"]


def test_reference_examples_compile_into_subject_pages() -> None:
    for example in EXAMPLES:
        pages = to_subject_pages(example.answer)

        assert sum(len(s.fields) for p in pages for s in p.sections) == len(example.answer.fields)
        assemble(example.answer.title, example.answer.addressee, example.answer.applicant, pages)


REFUND = ["Zaliczyć na poczet podatku", "Zwrócić przelewem"]


def refund_fields(*dependent: InventoryField) -> InventoryIR:
    choice = field("Nadpłata", "Rozliczenie", "sposob", type="RADIO", options=REFUND)
    return InventoryIR(title="Wniosek", fields=[choice, *dependent])


def test_show_if_option_becomes_an_ir_condition() -> None:
    inv = refund_fields(
        field("Nadpłata", "Rozliczenie", "rachunek", show_if_option=ShowIfOption(
            field_key="sposob", value="zwrócić przelewem ")),
        field("Nadpłata", "Rozliczenie", "tytul", show_if_option=ShowIfOption(
            field_key="sposob", value=REFUND[0])),
    )  # fmt: skip

    [page] = to_subject_pages(inv)

    conditions = {f.key: f.show_if for f in page.sections[0].fields}
    assert conditions == {
        "sposob": None,
        "rachunek": Cond(field="sposob", value="Zwrócić przelewem"),
        "tytul": Cond(field="sposob", value="Zaliczyć na poczet podatku"),
    }
    assemble("Wniosek", None, Applicant(), [page])


def test_condition_follows_a_renamed_target_key() -> None:
    inv = InventoryIR(
        title="Wniosek",
        fields=[
            field("S", "A", "kraj", type="RADIO", options=["Polska", "Inny"]),
            field(
                "S", "A", "kraj_obcy", show_if_option=ShowIfOption(field_key="kraj", value="Inny")
            ),
        ],
    )

    [page] = to_subject_pages(inv)

    by_key = {f.key: f for f in page.sections[0].fields}
    assert by_key["kraj_obcy"].show_if == Cond(field="kraj_2", value="Inny")


@pytest.mark.parametrize(
    "ref",
    [
        ShowIfOption(field_key="nie_ma_takiego", value=REFUND[0]),
        ShowIfOption(field_key="sposob", value="Opcja spoza listy"),
        ShowIfOption(field_key="opis", value="cokolwiek"),
        ShowIfOption(field_key="zalezne", value=REFUND[0]),
    ],
    ids=["unknown-field", "unknown-value", "not-a-choice", "self"],
)
def test_bad_show_if_reference_leaves_field_unconditional(ref: ShowIfOption) -> None:
    inv = refund_fields(
        field("Nadpłata", "Rozliczenie", "opis"),
        field("Nadpłata", "Rozliczenie", "zalezne", show_if_option=ref),
    )

    [page] = to_subject_pages(inv)

    assert all(f.show_if is None for f in page.sections[0].fields)


RULES = Analysis(
    title="Wniosek z reguł",
    addressee=Addressee(name="Urząd Gminy Reguły", kind="URZAD"),
    applicant=Applicant(),
    pages=[
        PageIR(
            title="Z reguł",
            sections=[SectionIR(key="z_regul", title="Z reguł", fields=[])],
        )
    ],
)


def refine_with(answer: InventoryIR, document: str = "L1 Blankiet") -> Analysis:
    handler, _ = scripted(completion(answer.model_dump_json()))
    return refine(make(), document, RULES, transport=httpx.MockTransport(handler))


BLANK = """\
L1 Wnioskodawca: imię i nazwisko / nazwa firmy
L2 Wójt Gminy Testowej
L3 # WNIOSEK o zwrot nadpłaty
L4 Proszę: 1) zaliczyć na poczet podatku
L5 2) zwrócić przelewem na rachunek nr ......
L6 podpis"""


def test_refine_returns_model_analysis_ready_for_assembly() -> None:
    choice = field(
        "Nadpłata",
        "Rozliczenie",
        "sposob",
        "Sposób",
        type="RADIO",
        options=REFUND,
        src=["L4", "L5"],
    )
    account = field(
        "Nadpłata",
        "Rozliczenie",
        "rachunek",
        "Rachunek",
        src=["L5"],
        show_if_option=ShowIfOption(field_key="sposob", value=REFUND[1]),
    )
    answer = InventoryIR(title="x", fields=[choice, account]).model_copy(update={
        "title": "Wniosek o zwrot nadpłaty",
        "addressee": Addressee(name="Wójt Gminy Testowej", kind="ORGAN"),
        "applicant": Applicant(persons=True, entities=True, proxy=False),
    })  # fmt: skip

    result = refine_with(answer, BLANK)

    assert result.title == "Wniosek o zwrot nadpłaty"
    assert result.addressee == answer.addressee
    assert result.applicant == answer.applicant
    assert result.pages == to_subject_pages(answer)
    assert result.pages[0].sections[0].fields[1].show_if == Cond(field="sposob", value=REFUND[1])
    assemble(result.title, result.addressee, result.applicant, result.pages)


def test_refine_falls_back_to_rules_for_missing_parts() -> None:
    answer = InventoryIR(title="Podanie o cokolwiek", addressee=None, fields=[])

    result = refine_with(answer)

    assert (result.title, result.addressee, result.pages) == (
        RULES.title,
        RULES.addressee,
        RULES.pages,
    )


def test_refine_raises_when_the_model_fails() -> None:
    handler, _ = scripted(httpx.Response(503), httpx.Response(503))

    with pytest.raises(LLMError):
        refine(make(), "L1 Blankiet", RULES, transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (Addressee(name="Burmistrz Miasta i Gminy Daleszyce", kind="URZAD"), "ORGAN"),
        (Addressee(name="Urząd Gminy Ulan-Majorat", kind="ORGAN"), "URZAD"),
        (Addressee(name="Rada Gminy Testowej", kind="ORGAN"), "ORGAN"),
    ],
)
def test_refine_makes_addressee_kind_match_its_name(given: Addressee, expected: str) -> None:
    result = refine_with(InventoryIR(title="Wniosek o test", addressee=given))

    assert result.addressee == Addressee(name=given.name, kind=expected)


def test_refine_drops_a_blank_addressee() -> None:
    blank = Addressee(name=" ", kind="URZAD")

    assert refine_with(InventoryIR(title="Wniosek o test", addressee=blank)).addressee == (
        RULES.addressee
    )


def labels(inv: InventoryIR) -> list[tuple[str, str, str]]:
    return [(f.page, f.label, f.type) for f in inv.fields]


def test_clean_drops_fields_the_predefined_sections_cover() -> None:
    inv = InventoryIR(
        title="Wniosek",
        fields=[
            field("Budynek", "Lokalizacja", "ulica", "Ulica"),
            field("Budynek", "Lokalizacja", "miejscowosc", "Miejscowość"),
            field("Budynek", "Wnioskodawca", "imie_nazwisko", "Imię i nazwisko"),
            field("Budynek", "Kontakt", "numer_telefonu", "Telefon kontaktowy"),
            field("Budynek", "Kontakt", "mail", "Adres e-mail"),
            field("Budynek", "Kontakt", "nr_tel", "Nr telefonu"),
            field("Budynek", "Załączniki", "pelnomocnictwo", "Plik pełnomocnictwa"),
            field("Budynek", "Wykonawca", "telefon_wykonawcy", "Telefon wykonawcy"),
        ],
    )

    cleaned = clean_inventory(inv)

    assert [f.label for f in cleaned.fields] == ["Ulica", "Miejscowość", "Telefon wykonawcy"]


def test_clean_moves_fields_off_pages_titled_like_the_library() -> None:
    inv = InventoryIR(
        title="Wniosek",
        fields=[
            field("Dane wnioskodawcy", "Cel", "cel", "Cel zaświadczenia"),
            field("Informacje o budynku", "Budynek", "dzialka", "Numer działki"),
            field("Kontakt i zgody", "Inne", "uwagi", "Uwagi"),
        ],
    )

    pages = {f.page for f in clean_inventory(inv).fields}

    assert pages == {"Informacje o budynku"}


def test_clean_uses_a_neutral_page_when_every_page_is_forbidden() -> None:
    inv = InventoryIR(
        title="Wniosek",
        fields=[field("Dane", "Cel", "cel", "Cel"), field("Strona końcowa", "X", "x", "Uwagi")],
    )

    assert {f.page for f in clean_inventory(inv).fields} == {SUBJECT_PAGE}


def test_clean_fixes_choices_without_options_and_drops_statements() -> None:
    inv = InventoryIR(
        title="Wniosek",
        fields=[
            field("S", "A", "o1", "Zapoznałem się z regulaminem", type="CHECKBOX"),
            field("S", "A", "o2", "Oświadczam, że dane są prawdziwe", type="CHECKBOX"),
            field("S", "A", "rodzaj", "Rodzaj imprezy", type="CHECKBOX"),
            field("S", "A", "tryb", "Tryb", type="RADIO"),
            field(
                "S", "A", "kraj_pochodzenia", "Kraj pochodzenia", type="SELECT", dictionary="Kraje"
            ),
            field("S", "A", "zgoda", "Zgoda", type="CONSENT_SECTION"),
        ],
    )

    cleaned = clean_inventory(inv)

    assert [(f.label, f.type) for f in cleaned.fields] == [
        ("Rodzaj imprezy", FieldType.TEXT_FIELD),
        ("Tryb", FieldType.TEXT_FIELD),
        ("Kraj pochodzenia", FieldType.SELECT),
    ]


def test_clean_removes_duplicate_labels_within_a_section() -> None:
    inv = InventoryIR(
        title="Wniosek",
        fields=[
            field("S", "Cel", "inny", "Inny cel"),
            field("S", "Cel", "inny_2", "Inny cel:", type="TEXTAREA"),
            field("S", "Inne", "inny_3", "Inny cel"),
        ],
    )

    assert [(f.section, f.key) for f in clean_inventory(inv).fields] == [
        ("Cel", "inny"),
        ("Inne", "inny_3"),
    ]


def test_clean_keeps_conditions_only_for_fields_inside_the_choice() -> None:
    purpose = field(
        "S", "Cel", "cel", "Cel", type="CHECKBOX", options=["Rolny", "Inne"], src=["L13", "L18"]
    )
    other = ShowIfOption(field_key="cel", value="Inne")
    inv = InventoryIR(
        title="Wniosek",
        fields=[
            purpose,
            field("S", "Cel", "inny", "Inny cel", src=["L18"], show_if_option=other),
            field("S", "Cel", "podmiot", "Podmiot", src=["L20"], show_if_option=other),
            field("S", "Cel", "bez_src", "Bez źródła", show_if_option=other),
        ],
    )

    cleaned = {f.key: f.show_if_option for f in clean_inventory(inv).fields}

    assert cleaned == {"cel": None, "inny": other, "podmiot": None, "bez_src": None}


def test_choice_without_options_never_reaches_ir() -> None:
    inv = InventoryIR(title="Wniosek", fields=[field("S", "A", "x", "X", type="CHECKBOX")])

    [page] = to_subject_pages(inv)

    assert page.sections[0].fields[0].type is FieldType.TEXT_FIELD


HEADER_BLANK = """\
L1 Wnioskodawca
L2 Urząd Miasta i Gminy
L3 Miasteczko
L4 WNIOSEK
L5 Administratorem danych jest Burmistrz Miasta i Gminy w Daleszycach"""


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Urząd Miasta i Gminy Miasteczko", True),
        ("Urząd Miasta i Gminy", True),
        ("Burmistrz Miasta i Gminy w Daleszycach", False),
    ],
)
def test_addressee_must_come_from_the_header(name: str, expected: bool) -> None:
    addressee = Addressee(name=name, kind="URZAD")

    assert addressee_in_header(addressee, HEADER_BLANK) is expected


def test_addressee_inflection_and_missing_title_are_tolerated() -> None:
    elblag = Addressee(name="Wójt Gminy Elbląg", kind="ORGAN")

    assert addressee_in_header(elblag, "L1 WÓJT GMINY ELBLĄGU\nL2 WNIOSEK o numer")
    assert addressee_in_header(elblag, "L1 tekst bez tytułu")
    assert header_text("L1 tekst bez tytułu") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("L1 imię i nazwisko, PESEL", Applicant(persons=True, entities=False, proxy=False)),
        ("L1 Nazwa firmy, NIP", Applicant(persons=True, entities=True, proxy=False)),
        ("L1 podpis osoby upoważnionej", Applicant(persons=True, entities=False, proxy=True)),
    ],
)
def test_model_flags_need_a_trace_in_the_text(text: str, expected: Applicant) -> None:
    model = Applicant(persons=True, entities=True, proxy=True)
    rules = Applicant(persons=True, entities=False, proxy=False)

    assert applicant_flags(model, rules, text) == expected


def test_refine_replaces_an_addressee_taken_from_the_clause() -> None:
    clause = Addressee(name="Burmistrz Miasta i Gminy w Daleszycach", kind="ORGAN")
    answer = InventoryIR(title="Wniosek o zajęcie pasa", addressee=clause)

    result = refine_with(answer, HEADER_BLANK)

    assert result.addressee == RULES.addressee
    assert result.applicant == RULES.applicant
