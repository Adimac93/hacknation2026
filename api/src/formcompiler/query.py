"""JSONata visibility queries: rendered from IR conditions, parsed only to decompile references."""

import re
from collections.abc import Callable
from dataclasses import dataclass

from formcompiler.ir import Cond, CondGroup, Condition


@dataclass(frozen=True)
class Location:
    page: str
    section: str
    field: str


ATOM = re.compile(
    r"""(?P<neg>\$not)?\(\s*"(?P<value>[^"]*)"\s+in\s+"""
    r"""tabs\['(?P<page>[^']*)'\s+in\s+title\]"""
    r"""\.questions\['(?P<section>[^']*)'\s+in\s+field\.techName\]"""
    r"""\.field\.repeatingSectionGrid\['(?P<field>[^']*)'\s+in\s+field\.techName\]"""
    r"""\.field\.__userAnswer\s*\)"""
)
TOKEN = re.compile(r"\s*(?:(?P<paren>[()])|(?P<op>and|or)\b)")
OPERATORS = {"and": "all", "or": "any"}
KEYWORDS = {"all": "and", "any": "or"}


def render(condition: Condition, locate: Callable[[str], Location], *, nested: bool = False) -> str:
    match condition:
        case Cond(field=key, op=op, value=value):
            loc = locate(key)
            if '"' in value or "'" in loc.page + loc.section + loc.field:
                raise ValueError(f"quote characters are not allowed in conditions: {value!r}")
            path = (
                f"tabs['{loc.page}' in title].questions['{loc.section}' in field.techName]"
                f".field.repeatingSectionGrid['{loc.field}' in field.techName].field.__userAnswer"
            )
            atom = f'"{value}" in {path}'
            return f"$not({atom})" if op == "NOT_IN" else f"({atom})"
        case CondGroup(match=match, conds=conds):
            body = f" {KEYWORDS[match]} ".join(render(c, locate, nested=True) for c in conds)
            return f"({body})" if nested else body


def normalize(query: str) -> str:
    """Whitespace-insensitive form, for comparing hand-written reference queries."""
    query = re.sub(r"\s+", " ", query).strip()
    return re.sub(r"\s*\)", ")", re.sub(r"\(\s*", "(", query))


def parse(query: str) -> tuple[Condition, dict[str, Location]]:
    """Parse a reference query back into an IR condition and the location of each field."""
    tokens: list[Cond | str] = []
    locations: dict[str, Location] = {}
    pos, text = 0, query.strip()
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
        elif atom := ATOM.match(text, pos):
            loc = Location(atom["page"], atom["section"], atom["field"])
            locations[loc.field] = loc
            tokens.append(
                Cond(field=loc.field, op="NOT_IN" if atom["neg"] else "IN", value=atom["value"])
            )
            pos = atom.end()
        elif token := TOKEN.match(text, pos):
            tokens.append(token["paren"] or token["op"])
            pos = token.end()
        else:
            raise ValueError(f"unsupported query syntax at {pos}: {text[pos : pos + 40]!r}")

    condition, rest = _expression(tokens)
    if rest:
        raise ValueError(f"unexpected tokens after condition: {rest}")
    return condition, locations


def _expression(tokens: list[Cond | str]) -> tuple[Condition, list[Cond | str]]:
    first, tokens = _term(tokens)
    terms, operator = [first], None
    while tokens and tokens[0] in OPERATORS:
        op = str(tokens[0])
        if operator is not None and op != operator:
            raise ValueError("mixing 'and' and 'or' without parentheses is not supported")
        operator = op
        term, tokens = _term(tokens[1:])
        terms.append(term)
    if operator is None:
        return first, tokens
    return CondGroup(match=OPERATORS[operator], conds=terms), tokens


def _term(tokens: list[Cond | str]) -> tuple[Condition, list[Cond | str]]:
    if not tokens:
        raise ValueError("unexpected end of query")
    head, rest = tokens[0], tokens[1:]
    if isinstance(head, Cond):
        return head, rest
    if head == "(":
        inner, rest = _expression(rest)
        if not rest or rest[0] != ")":
            raise ValueError("missing closing parenthesis")
        return inner, rest[1:]
    raise ValueError(f"unexpected token: {head}")
