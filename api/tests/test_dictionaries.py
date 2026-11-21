from formcompiler import compiler, sections
from formcompiler.dictionaries import propose
from formcompiler.ir import Applicant, FieldIR, FieldType, PageIR, SectionIR
from formcompiler.report import DictionaryProposal

WORKS = ["Wykopy", "Przewierty", "Przeciski", "Inne"]


def field(key: str, label: str, options: list[str], kind: FieldType = FieldType.RADIO) -> FieldIR:
    return FieldIR(key=key, label=label, type=kind, options=options)


def proposals(*fields: FieldIR, section: str = "Szczegóły") -> list[DictionaryProposal]:
    page = PageIR(
        title="Szczegóły wniosku",
        sections=[SectionIR(key="szczegoly", title=section, fields=list(fields))],
    )
    ir = sections.assemble("Wniosek", None, Applicant(proxy=True, entities=True), [page])
    return propose(compiler.build(ir))


def test_closed_list_becomes_a_proposal_in_original_order() -> None:
    result = proposals(field("rodzaj_robot", "Rodzaj robót:", WORKS, FieldType.CHECKBOX))

    assert result == [DictionaryProposal(name="Rodzaj robót", items=WORKS, fields=["rodzaj_robot"])]


def test_fields_with_the_same_options_are_merged() -> None:
    result = proposals(
        field("rodzaj_robot", "Rodzaj robót (zaznacz właściwe)", WORKS),
        field("rodzaj_robot_2", "Rodzaj robót dodatkowych", WORKS, FieldType.SELECT),
        field("material", "Materiał", ["Asfalt", "Kostka", "Beton"]),
    )

    assert [(p.name, p.fields) for p in result] == [
        ("Rodzaj robót", ["rodzaj_robot", "rodzaj_robot_2"]),
        ("Materiał", ["material"]),
    ]


def test_yes_no_and_short_lists_are_ignored() -> None:
    assert (
        proposals(
            field("czy_zgoda", "Czy wyraża Pan zgodę?", ["Tak", "Nie", "Nie dotyczy"]),
            field("plec", "Płeć", ["Kobieta", "Mężczyzna"]),
        )
        == []
    )


def test_lists_covered_by_an_existing_dictionary_are_ignored() -> None:
    assert (
        proposals(
            field("panstwo", "Państwo urodzenia", ["Polska", "Niemcy", "Czechy"], FieldType.SELECT),
            field("region", "Region", ["Mazowieckie", "Łódzkie", "Opolskie"], FieldType.SELECT),
        )
        == []
    )


def test_predefined_sections_and_sentence_options_are_ignored() -> None:
    statements = [
        "Ilości posiadanych użytków rolnych w hektarach fizycznych i przeliczeniowych",
        "Okresie posiadania gospodarstwa rolnego",
        "Inne",
    ]

    # The applicant section of the COI library has a three-option RADIO of its own.
    assert proposals(field("zaswiadczenie", "Proszę o wydanie zaświadczenia o", statements)) == []


def test_instruction_label_is_named_after_its_section() -> None:
    result = proposals(
        field("wybierz", "A następnie wybierz z listy", ["Zespołowa", "Indywidualna", "Inna"]),
        section="Rodzaj dyscypliny",
    )

    assert [p.name for p in result] == ["Rodzaj dyscypliny"]
