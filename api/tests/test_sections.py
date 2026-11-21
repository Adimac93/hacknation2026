import json
from typing import Any

import pytest
from conftest import REFERENCE_FILES

from formcompiler.decompile import decompile
from formcompiler.ir import Addressee, Applicant, Cond, FormIR, PageIR, SectionIR
from formcompiler.schema import Form
from formcompiler.sections import LIBRARY, assemble


def reference_ir(name: str) -> FormIR:
    data: dict[str, Any] = json.loads(REFERENCE_FILES[name].read_text(encoding="utf-8"))
    return decompile(Form.model_validate(data))


def subject_pages(ir: FormIR) -> list[PageIR]:
    """Pages between the standard data page and the contact page: what the model must produce."""
    return ir.pages[1:-2]


def sections_of(ir: FormIR) -> dict[str, SectionIR]:
    return {s.key: s for p in ir.pages for s in p.sections}


ALL = Applicant(persons=True, entities=True, proxy=True)
ULAN = Addressee(name="Urząd Gminy Ulan-Majorat", kind="URZAD")


def test_library_is_taken_from_the_references() -> None:
    ref1, ref5 = reference_ir("ref1"), reference_ir("ref5")

    assert LIBRARY.addressee["URZAD"] == ref5.pages[0].sections[0]
    assert LIBRARY.addressee["ORGAN"] == ref1.pages[0].sections[0]
    assert LIBRARY.applicant == ref5.pages[0].sections[1:]
    assert LIBRARY.contact == ref5.pages[-2]
    assert LIBRARY.finish == ref5.pages[-1]


def test_assemble_with_every_applicant_reproduces_reference_5() -> None:
    ref5 = reference_ir("ref5")

    assembled = assemble(ref5.title, ULAN, ALL, subject_pages(ref5))

    assert assembled.title == ref5.title
    assert assembled.pages == ref5.pages


def test_addressee_name_is_a_read_only_default() -> None:
    form = assemble("Wniosek", Addressee(name="Wójt Gminy Elbląg", kind="ORGAN"), ALL, [])

    field = form.pages[0].sections[0].fields[0]
    assert form.pages[0].sections[0].key == "organ_do_ktorego_jest_skladany_wniosek"
    assert (field.default, field.read_only) == ("Wójt Gminy Elbląg", True)


def test_persons_only_keeps_just_own_data() -> None:
    form = assemble("Wniosek", ULAN, Applicant(persons=True, entities=False, proxy=False), [])

    assert [s.key for s in form.pages[0].sections] == [
        "urzad_do_ktorego_jest_skladany_wniosek",
        "twoje_dane",
        "adres_zamieszkania",
    ]


def test_proxy_without_entities_prunes_entity_branches() -> None:
    form = assemble("Wniosek", ULAN, Applicant(persons=True, entities=False, proxy=True), [])
    sections = sections_of(form)

    assert sections["podmiot_wniosku"].fields[0].options == ["Swoim", "Innej osoby"]
    assert [f.key for f in sections["podmiot_wniosku"].fields] == [
        "wybierz_w_czyim_imieniu_wnioskujesz"
    ]
    assert "dane_podmiotu" not in sections
    assert "oplata_skarbowa_pelnomocnictwo_2" not in sections
    assert sections["pelnomocnictwo"].show_if == Cond(
        field="wybierz_w_czyim_imieniu_wnioskujesz", value="Innej osoby"
    )


def test_entities_without_proxy_keep_representative_branch() -> None:
    form = assemble("Wniosek", ULAN, Applicant(persons=True, entities=True, proxy=False), [])
    sections = sections_of(form)

    assert sections["podmiot_wniosku"].fields[0].options == [
        "Swoim",
        "Osoby prawnej lub jednostki organizacyjnej",
    ]
    assert {"dane_podmiotu", "adres_siedziby", "potwierdzenie_ze_jestes_reprezentantem"} <= set(
        sections
    )
    assert "dane_innej_osoby" not in sections


def test_page_order_is_data_subject_contact_finish() -> None:
    subject = PageIR(
        title="Przedmiot wniosku",
        sections=[SectionIR(key="zaswiadczenie", title="Zaświadczenie", fields=[])],
    )

    form = assemble("Wniosek", ULAN, ALL, [subject])

    assert [p.title for p in form.pages] == [
        "Dane",
        "Przedmiot wniosku",
        "Kontakt i zgody",
        "Strona końcowa",
    ]
    assert form.pages[-1].kind == "FINISH"


def test_subject_keys_must_not_collide_with_templates() -> None:
    clash = PageIR(title="Przedmiot", sections=[SectionIR(key="twoje_dane", title="X", fields=[])])

    with pytest.raises(ValueError, match="twoje_dane"):
        assemble("Wniosek", ULAN, ALL, [clash])
