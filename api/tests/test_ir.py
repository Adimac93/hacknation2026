from typing import Any

import pytest
from pydantic import ValidationError

from formcompiler.ir import Cond, FieldIR, FieldType, FormIR, Validator


def field(key: str = "imie", **overrides: Any) -> FieldIR:
    data: dict[str, Any] = {"key": key, "label": "Imię", "type": FieldType.TEXT_FIELD}
    return FieldIR.model_validate(data | overrides)


def form(*fields: FieldIR) -> FormIR:
    return FormIR.model_validate(
        {
            "title": "Wniosek o wydanie zaświadczenia",
            "addressee": {"name": "Urząd Gminy Testowo", "kind": "URZAD"},
            "applicant": {"persons": True, "entities": False, "proxy": False},
            "pages": [
                {
                    "title": "Przedmiot wniosku",
                    "sections": [{"title": "Zaświadczenie", "fields": list(fields)}],
                }
            ],
        }
    )


@pytest.mark.parametrize("key", ["Imie", "imię", "imie-nazwisko", "1pole", "", "a" * 61])
def test_field_key_must_be_ascii_snake_case(key: str) -> None:
    with pytest.raises(ValidationError):
        field(key)


def test_unknown_validator_is_rejected() -> None:
    with pytest.raises(ValidationError):
        field(validators=["PHONE"])


def test_known_validators_are_accepted() -> None:
    validators = field(validators=["REQUIRED", "PESEL"]).validators

    assert validators == [Validator.REQUIRED, Validator.PESEL]


def test_dictionary_is_allowed_only_for_choice_fields() -> None:
    with pytest.raises(ValidationError, match="dictionary"):
        field(dictionary="Kraje")

    assert field(type=FieldType.SELECT, dictionary="Kraje").dictionary == "Kraje"


def test_dictionary_field_must_not_list_options() -> None:
    with pytest.raises(ValidationError, match="options"):
        field(type=FieldType.SELECT, dictionary="Kraje", options=["Polska"])


def test_field_keys_must_be_unique_in_form() -> None:
    with pytest.raises(ValidationError, match="imie"):
        form(field("imie"), field("imie"))


def test_condition_must_reference_existing_field() -> None:
    show_if = Cond(field="nie_ma_takiego", value="Tak")

    with pytest.raises(ValidationError, match="nie_ma_takiego"):
        form(field("imie", show_if=show_if))


def test_condition_must_reference_existing_option() -> None:
    choice = field("czy_pelnomocnik", type=FieldType.RADIO, options=["Tak", "Nie"])
    dependent = field("imie_pelnomocnika", show_if=Cond(field="czy_pelnomocnik", value="Może"))

    with pytest.raises(ValidationError, match="Może"):
        form(choice, dependent)


def test_valid_condition_passes() -> None:
    choice = field("czy_pelnomocnik", type=FieldType.RADIO, options=["Tak", "Nie"])
    dependent = field("imie_pelnomocnika", show_if=Cond(field="czy_pelnomocnik", value="Tak"))

    assert form(choice, dependent).pages[0].sections[0].fields[1].show_if is not None
