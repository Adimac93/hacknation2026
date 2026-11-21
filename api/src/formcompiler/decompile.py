"""Output JSON -> IR. Used to test the compiler on the references and to build few-shot examples."""

from formcompiler import schema
from formcompiler.compiler import description
from formcompiler.ir import (
    Condition,
    Consent,
    FieldIR,
    FieldType,
    FormIR,
    PageIR,
    SectionIR,
    Validator,
)
from formcompiler.query import parse
from formcompiler.richtext import EMPTY_DOCUMENT, to_text


def decompile(form: schema.Form) -> FormIR:
    return FormIR(
        title=form.title,
        pages=[
            PageIR(
                title=tab.title,
                kind=tab.type,
                sections=[_section(q.field) for q in sorted(tab.questions, key=lambda q: q.y)],
            )
            for tab in form.tabs
        ],
    )


def _text_and_html(document: str, *, empty: str) -> tuple[str, str | None]:
    """Keep the original HTML only when the compiler could not regenerate it from plain text."""
    if document == empty:
        return "", None
    text = to_text(document)
    return (text, None) if description(text, None, empty=empty) == document else (text, document)


def _condition(field: schema.Field, kind: str) -> Condition | None:
    queries = [s.query for s in field.states if s.type == kind]
    if len(queries) > 1:
        raise ValueError(f"{field.techName}: more than one {kind} state")
    return parse(queries[0])[0] if queries else None


def _section(field: schema.Field) -> SectionIR:
    text, html = _text_and_html(field.description, empty=EMPTY_DOCUMENT)
    return SectionIR(
        key=field.techName,
        title=field.title,
        description=text,
        description_html=html,
        repeating=field.type == "REPEATING_SECTION",
        show_if=_condition(field, "SHOW"),
        fields=[_field(g.field) for g in sorted(field.repeatingSectionGrid, key=lambda g: g.y)],
    )


def _field(field: schema.Field) -> FieldIR:
    text, html = _text_and_html(field.description, empty="")
    validation = field.validation if isinstance(field.validation, list) else []
    initial = field.defaultValue if field.defaultValueType == "EXTERNAL_SYSTEM" else None
    default = None if initial is not None else field.defaultValue
    if isinstance(default, list):
        if len(default) > 1:
            raise ValueError(f"{field.techName}: more than one default value")
        default = default[0] if default else None
    consents = []
    if field.consentSectionConfig is not None:
        for c in field.consentSectionConfig.consents:
            consent_text, consent_html = _text_and_html(c.description, empty=EMPTY_DOCUMENT)
            consents.append(Consent(text=consent_text, html=consent_html, required=c.required))
    return FieldIR(
        key=field.techName,
        label=field.title,
        description=text,
        description_html=html,
        type=FieldType(field.type),
        required=Validator.REQUIRED in validation,
        validators=[Validator(v) for v in validation if v != Validator.REQUIRED],
        options=[o.name for o in field.options],
        dictionary=field.dictionaryName,
        initial=str(initial) if initial is not None else None,
        default=default,
        read_only=field.readOnly,
        consents=consents,
        show_if=_condition(field, "SHOW"),
        read_only_if=_condition(field, "READ_ONLY"),
    )
