import pytest

from formcompiler.compiler import build
from formcompiler.document import Document, Line, LineKind, Page
from formcompiler.heuristics import analyze, classify
from formcompiler.ir import Cond, FieldIR, FieldType, Validator
from formcompiler.lint import lint
from formcompiler.sections import RESERVED_KEYS, assemble

FORM_3 = [
    ("Młynary, dnia…………………….", LineKind.TEXT),
    ("………………………………..", LineKind.TEXT),
    ("/ imię i nazwisko /", LineKind.TEXT),
    ("………………………………..", LineKind.TEXT),
    ("/ adres /", LineKind.TEXT),
    ("Urząd Miasta i Gminy Młynary", LineKind.TEXT),
    ("ul. Dworcowa 29", LineKind.TEXT),
    ("……………………………….", LineKind.TEXT),
    ("14-420 Młynary", LineKind.TEXT),
    ("/ PESEL /", LineKind.TEXT),
    ("……………………………….", LineKind.TEXT),
    ("/ nr telefonu /", LineKind.TEXT),
    ("WNIOSEK O WYDANIE ZAŚWIADCZENIA", LineKind.HEADING),
    ("Proszę o wydanie zaświadczenia o:*", LineKind.TEXT),
    ("ilości posiadanych użytków rolnych w hektarach fizycznych", LineKind.CHECKBOX),
    ("ilości dzierżawionych użytków rolnych w hektarach fizycznych", LineKind.CHECKBOX),
    ("okresie posiadania gospodarstwa rolnego", LineKind.CHECKBOX),
    ("nieposiadaniu użytków rolnych na terenie Gminy Młynary", LineKind.CHECKBOX),
    ("inne………………………………………………", LineKind.CHECKBOX),
    ("…………………………………………………...", LineKind.TEXT),
    ("Zaświadczenie potrzebne jest celem przedłożenia w ……………………", LineKind.TEXT),
    ("……………………………………………………………", LineKind.TEXT),
    ("………………………………………", LineKind.TEXT),
    ("/podpis/", LineKind.TEXT),
    ("INFORMACJE:", LineKind.HEADING),
    ("1. Opłata za wydanie zaświadczenia wynosi 17 zł (od każdego egzemplarza).", LineKind.TEXT),
    ("2. Opłatę skarbową należy wnieść w kasie lub na rachunek Urzędu.", LineKind.TEXT),
]


def document(lines: list[tuple[str, LineKind]]) -> Document:
    return Document(
        pages=[
            Page(
                number=1,
                lines=[Line(id=f"L{i}", text=t, kind=k) for i, (t, k) in enumerate(lines, 1)],
            )
        ]
    )


def all_fields(lines: list[tuple[str, LineKind]]) -> list[FieldIR]:
    result = analyze(document(lines))
    return [f for p in result.pages for s in p.sections for f in s.fields]


def test_title_is_sentence_case() -> None:
    assert analyze(document(FORM_3)).title == "Wniosek o wydanie zaświadczenia"


def test_addressee_is_found_in_the_header() -> None:
    addressee = analyze(document(FORM_3)).addressee

    assert addressee is not None
    assert (addressee.name, addressee.kind) == ("Urząd Miasta i Gminy Młynary", "URZAD")


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("Wójt Gminy Elbląg", "ORGAN"),
        ("Burmistrz Miasta Pasłęk", "ORGAN"),
        ("Urząd Gminy X", "URZAD"),
    ],
)
def test_addressee_kind(line: str, kind: str) -> None:
    addressee = analyze(document([(line, LineKind.TEXT), ("WNIOSEK", LineKind.HEADING)])).addressee

    assert addressee is not None and addressee.kind == kind


def test_applicant_data_in_header_is_left_to_predefined_sections() -> None:
    keys = {f.key for f in all_fields(FORM_3)}

    assert not keys & {"imie_i_nazwisko", "adres", "pesel", "nr_telefonu"}


def test_applicant_flags() -> None:
    assert analyze(document(FORM_3)).applicant.model_dump() == {
        "persons": True,
        "entities": False,
        "proxy": False,
    }
    proxy = analyze(document([("WNIOSEK", LineKind.HEADING), ("Dane pełnomocnika", LineKind.TEXT)]))
    entity = analyze(document([("WNIOSEK", LineKind.HEADING), ("NIP ……………", LineKind.TEXT)]))
    assert proxy.applicant.proxy and entity.applicant.entities


def test_checkbox_group_becomes_choice_with_other_option() -> None:
    fields = all_fields(FORM_3)
    choice = next(f for f in fields if f.options)
    other = next(f for f in fields if f.show_if is not None)

    assert choice.type is FieldType.CHECKBOX
    assert choice.label == "Proszę o wydanie zaświadczenia o"
    assert len(choice.options) == 5 and choice.options[-1] == "Inne"
    assert other.type is FieldType.TEXT_FIELD
    assert other.show_if == Cond(field=choice.key, value="Inne")


def test_blank_with_continuation_line_becomes_textarea() -> None:
    purpose = next(f for f in all_fields(FORM_3) if "celem" in f.label)

    assert purpose.type is FieldType.TEXTAREA
    assert purpose.label == "Zaświadczenie potrzebne jest celem przedłożenia w"


def test_signature_and_date_are_skipped() -> None:
    labels = " ".join(f.label.lower() for f in all_fields(FORM_3))

    assert "podpis" not in labels and "dnia" not in labels


def test_information_becomes_text_block() -> None:
    block = next(f for f in all_fields(FORM_3) if f.type is FieldType.TEXT_BLOCK)

    assert "17 zł" in block.description


def test_fee_adds_payment_confirmation_upload() -> None:
    upload = next(f for f in all_fields(FORM_3) if f.type is FieldType.FILE_UPLOADER)

    assert "opłat" in upload.label.lower()


@pytest.mark.parametrize(
    ("label", "field_type", "validators"),
    [
        ("Data zdarzenia", FieldType.DATEPICKER, []),
        ("Kwota nadpłaty", FieldType.NUMBER, []),
        ("Uzasadnienie", FieldType.TEXTAREA, []),
        ("Numer działki", FieldType.TEXT_FIELD, []),
        ("NIP podatnika", FieldType.TEXT_FIELD, [Validator.NIP]),
        ("REGON", FieldType.TEXT_FIELD, [Validator.REGON]),
        ("Załącznik: mapa", FieldType.FILE_UPLOADER, []),
    ],
)
def test_classify_by_keywords(
    label: str, field_type: FieldType, validators: list[Validator]
) -> None:
    assert classify(label) == (field_type, validators)


def test_keys_avoid_predefined_sections() -> None:
    fields = all_fields([("WNIOSEK", LineKind.HEADING), ("Pełnomocnictwo ………", LineKind.TEXT)])

    assert fields and not {f.key for f in fields} & RESERVED_KEYS


def test_empty_body_still_gives_a_field() -> None:
    assert all_fields([("WNIOSEK O COŚ", LineKind.HEADING)])


def test_result_compiles_without_lint_errors() -> None:
    result = analyze(document(FORM_3))
    form = build(assemble(result.title, result.addressee, result.applicant, result.pages))

    assert [i for i in lint(form) if i.severity == "error"] == []


def test_title_split_over_lines_is_joined_in_sentence_case() -> None:
    lines = [
        ("WÓJT GMINY PŁOSKINIA", LineKind.TEXT),
        ("Płoskinia 8", LineKind.TEXT),
        ("WNIOSEK", LineKind.HEADING),
        ("o", LineKind.TEXT),
        ("wynajęcie/użyczenie* świetlicy wiejskiej", LineKind.TEXT),
        ("Proszę o wynajem świetlicy ……………", LineKind.TEXT),
    ]

    result = analyze(document(lines))

    assert result.title == "Wniosek o wynajęcie/użyczenie świetlicy wiejskiej"
    assert result.addressee is not None
    assert (result.addressee.name, result.addressee.kind) == ("Wójt Gminy Płoskinia", "ORGAN")


def test_addressee_name_spans_lines_until_the_street() -> None:
    lines = [
        ("Urząd Gminy", LineKind.TEXT),
        ("Ulan-Majorat", LineKind.TEXT),
        ("Ulan-Majorat 57", LineKind.TEXT),
        ("WNIOSEK", LineKind.HEADING),
        ("o stwierdzenie nadpłaty podatku", LineKind.TEXT),
    ]

    result = analyze(document(lines))

    assert result.addressee is not None
    assert result.addressee.name == "Urząd Gminy Ulan-Majorat"
    assert result.title == "Wniosek o stwierdzenie nadpłaty podatku"
