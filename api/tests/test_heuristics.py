import pytest

from formcompiler.compiler import build
from formcompiler.document import Document, Line, LineKind, Page
from formcompiler.heuristics import analyze, classify, label_of
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


T, H, C = LineKind.TEXT, LineKind.HEADING, LineKind.CHECKBOX


def body(lines: list[tuple[str, LineKind]]) -> list[FieldIR]:
    return all_fields([("Wniosek o coś", H), ("A. SZCZEGÓŁY", H), *lines])


def labels(lines: list[tuple[str, LineKind]]) -> list[str]:
    return [f.label for f in body(lines) if f.type is not FieldType.TEXT_BLOCK]


@pytest.mark.parametrize(
    ("text", "label", "description"),
    [
        ("w miejscowości 1)", "Miejscowość", ""),
        ("przy ulicy1.", "Ulica", ""),
        ("w obrębie", "Obręb", ""),
        ("nr ewid. działki", "Numer ewidencyjny działki", ""),
        ("Numer telefonu (opcjonalnie)", "Numer telefonu", ""),
        ("Data szczepienia (w przypadku jego braku)", "Data szczepienia", "W przypadku jego braku"),
        ("3. Cel wynajęcia świetlicy:", "Cel wynajęcia świetlicy", ""),
        ("……… .", "", ""),
        ("= zł", "", ""),
    ],
)
def test_label_is_cleaned_from_blank_fragments(text: str, label: str, description: str) -> None:
    assert label_of(text) == (label, description)


def test_long_label_keeps_its_head_and_moves_the_rest_to_description() -> None:
    label, description = label_of(
        "Opinia macierzystego klubu sportowego, potwierdzająca nienaganną postawę sportowca"
    )

    assert label == "Opinia macierzystego klubu sportowego"
    assert description.startswith("Opinia macierzystego klubu sportowego, potwierdzająca")


def test_each_blank_of_a_line_is_a_field() -> None:
    assert labels([("w miejscowości………… przy ulicy 1) ……………", T)]) == ["Miejscowość", "Ulica"]


def test_ocr_leader_remnant_still_marks_a_field() -> None:
    assert labels([("w miejscowości..", T), ("... przy ulicy1.", T)]) == ["Miejscowość", "Ulica"]


def test_dotted_line_continued_on_next_line_takes_its_caption() -> None:
    fields = body(
        [
            ("Wnoszę o stwierdzenie nadpłaty z tytułu ……………", T),
            ("…………………… w kwocie ……………", T),
            ("(rodzaj podatku)", T),
        ]
    )

    assert [(f.label, f.type) for f in fields] == [
        ("Rodzaj podatku", FieldType.TEXT_FIELD),
        ("Kwota", FieldType.NUMBER),
    ]


def test_caption_with_signature_drops_the_blank() -> None:
    assert labels([("Jestem świadomy odpowiedzialności.", T), ("………………", T), ("(podpis)", T)]) == [
        "Treść wniosku"  # the fallback field: nothing came from the signature line
    ]


def test_short_caption_names_an_unlabelled_blank_and_long_caption_is_help() -> None:
    fields = body(
        [
            ("………………………", T),
            ("/ rodzaj robót /", T),
            ("Cel wynajęcia: ………………", T),
            ("( rodzaj uroczystości, np. wesele)", T),
        ]
    )

    assert [f.label for f in fields] == ["Rodzaj robót", "Cel wynajęcia"]
    assert fields[1].description == "Rodzaj uroczystości, np. wesele"


def test_colon_prompt_above_blank_lines_becomes_textarea() -> None:
    fields = body([("Uzasadnienie:", T), ("…………………", T), ("…………………", T)])

    assert [(f.label, f.type) for f in fields] == [("Uzasadnienie", FieldType.TEXTAREA)]


def test_colon_prompt_without_blank_is_kept_when_its_kind_is_clear() -> None:
    fields = body(
        [("Uzasadnienie:", T), ("Kwotę nadpłaty proszę zwrócić.", T), ("Wnioskodawca:", T)]
    )

    assert [f.label for f in fields] == ["Uzasadnienie"]


def test_date_range_gives_two_dates() -> None:
    fields = body([("Roboty będą realizowane w terminie od dnia ……… do dnia ………", T)])

    assert [(f.label, f.type) for f in fields] == [
        ("Termin od", FieldType.DATEPICKER),
        ("Termin do", FieldType.DATEPICKER),
    ]


def test_units_make_numbers() -> None:
    fields = body(
        [("Całkowita powierzchnia zajęcia: ……………m 2", T), ("tj. ………dni, zgodnie z planem.", T)]
    )

    assert [(f.label, f.type) for f in fields] == [
        ("Całkowita powierzchnia zajęcia (m²)", FieldType.NUMBER),
        ("Liczba dni", FieldType.NUMBER),
    ]


def test_repeated_rows_are_merged_and_prefixed_with_their_subheading() -> None:
    row = "długość ………… szerokość ………… razem ………… m 2"
    found = labels([("a/ jezdnia", T), (row, T), (row, T), ("b/ chodnik", T), (row, T)])

    assert found == [
        "Jezdnia \u2013 długość",
        "Jezdnia \u2013 szerokość",
        "Jezdnia \u2013 razem (m²)",
        "Chodnik \u2013 długość",
        "Chodnik \u2013 szerokość",
        "Chodnik \u2013 razem (m²)",
    ]


def test_numbered_list_under_colon_is_a_choice_with_account_number() -> None:
    fields = body(
        [
            ("Kwotę nadpłaty proszę:", T),
            ("1) zaliczyć na poczet zobowiązania z tytułu ………", T),
            ("2) zwrócić przelewem na wskazany rachunek", T),
        ]
    )
    choice, detail, account = fields

    assert choice.type is FieldType.RADIO and len(choice.options) == 2
    assert detail.show_if == Cond(field=choice.key, value=choice.options[0])
    assert account.label == "Numer rachunku bankowego"
    assert account.show_if == Cond(field=choice.key, value=choice.options[1])


def test_attachment_list_gives_uploads() -> None:
    fields = body(
        [
            ("Załączniki do wniosku:", T),
            ("- Szczegółowy plan sytuacyjny w skali 1:500 z zaznaczeniem granic.", T),
            ("· Harmonogram robót.", T),
            ("3) ……………", T),
        ]
    )

    assert [(f.label, f.type) for f in fields] == [
        ("Szczegółowy plan sytuacyjny w skali 1:500", FieldType.FILE_UPLOADER),
        ("Harmonogram robót", FieldType.FILE_UPLOADER),
        ("Inne załączniki", FieldType.FILE_UPLOADER),
    ]


def test_consent_intro_turns_list_into_statements() -> None:
    fields = body(
        [
            ("4. Jednocześnie oświadczam, że:", T),
            ("1) zapoznałem się z regulaminem,", T),
            ("2) odpowiadam za porządek w", T),
            ("świetlicy.", T),
        ]
    )
    consents = next(f for f in fields if f.type is FieldType.CONSENT_SECTION).consents

    assert [c.text for c in consents] == [
        "Oświadczam, że zapoznałem się z regulaminem,",
        "Oświadczam, że odpowiadam za porządek w świetlicy.",
    ]


def test_numbered_boxes_are_fields_outside_applicant_sections() -> None:
    fields = body(
        [
            ("B.3 ADRES ZAMIESZKANIA / SIEDZIBY", T),
            ("11. Miejscowość", T),
            ("12. Ulica", T),
            ("D.1 ADRES NIERUCHOMOŚCI", T),
            ("26. Miejscowość", T),
            ("27. Kod pocztowy", T),
        ]
    )

    assert [(f.label, f.validators) for f in fields] == [
        ("Miejscowość", []),
        ("Kod pocztowy", [Validator.ZIP_CODE]),
    ]


def test_personal_data_of_another_person_is_kept() -> None:
    found = labels([("2. Dane sportowca", T), ("Imię ………………", T), ("Data urodzenia ………………", T)])

    assert found == ["Imię", "Data urodzenia"]


def test_table_row_label_cells_are_fields() -> None:
    lines = [
        Line(id="L1", text="WNIOSEK", kind=H),
        Line(id="L2", text="DANE PSA", kind=H),
        Line(id="L3", text="Rasa: Maść:", kind=LineKind.TABLE_ROW, cells=["Rasa:", "Maść:"]),
    ]
    result = analyze(Document(pages=[Page(number=1, lines=lines)]))

    assert [f.label for s in result.pages[0].sections for f in s.fields] == ["Rasa", "Maść"]


def test_headings_with_notes_and_data_sections_are_not_information() -> None:
    fields = body(
        [
            ("F. DANE DO KONTAKTU (pola nieobowiązkowe)", T),
            ("Adres e-mail ………………", T),
            ("INFORMACJA O POSIADANYM PSIE", T),
            ("Rasa psa: ………………", T),
        ]
    )

    assert [f.label for f in fields] == ["Rasa psa"]


def test_lone_section_letter_takes_title_from_line_above() -> None:
    result = analyze(
        document(
            [
                ("Wniosek o coś", H),
                ("INFORMACJA O PSIE (w razie potrzeby dołączyć tabelę", T),
                ("B", T),
                ("Rasa psa: ………", T),
            ]
        )
    )

    assert [s.title for s in result.pages[0].sections] == ["Informacja o psie"]


def test_checkbox_option_with_blank_gets_conditional_detail() -> None:
    fields = body(
        [
            ("Sposób korespondencji", T),
            ("poczta tradycyjna", C),
            ("Skrzynka ePUAP - adres skrzynki: ………", C),
        ]
    )
    choice, detail = fields

    assert detail.validators == [Validator.EPUAP]
    assert detail.show_if == Cond(field=choice.key, value="Skrzynka ePUAP - adres skrzynki")


@pytest.mark.parametrize(
    ("label", "field_type", "validators"),
    [
        ("Przewidywana ilość uczestników", FieldType.NUMBER, []),
        ("Termin od", FieldType.DATEPICKER, []),
        (
            "Seria i numer dowodu osobistego",
            FieldType.TEXT_FIELD,
            [Validator.SERIAL_NUMBER_ID_CARD],
        ),
    ],
)
def test_classify_new_keywords(
    label: str, field_type: FieldType, validators: list[Validator]
) -> None:
    assert classify(label) == (field_type, validators)


def test_new_rules_compile_without_lint_errors() -> None:
    lines = [
        ("WNIOSEK O COŚ", H),
        ("w miejscowości………… przy ulicy 1) ……………", T),
        ("Kwotę nadpłaty proszę:", T),
        ("1) zaliczyć z tytułu ………", T),
        ("2) zwrócić przelewem na rachunek", T),
        ("w załączeniu:", T),
        ("1) korekta deklaracji", T),
        ("2) ……………", T),
        ("Roboty w terminie od ……… do ………", T),
    ]
    result = analyze(document(lines))
    form = build(assemble(result.title, result.addressee, result.applicant, result.pages))

    assert [i for i in lint(form) if i.severity == "error"] == []
