"""Plain text <-> the HTML document format used for descriptions in the output JSON."""

import html
from html.parser import HTMLParser

EMPTY_DOCUMENT = "<html><head></head><body></body></html>"


def to_html(text: str) -> str:
    """Paragraphs separated by a blank line become <p> elements."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    body = "".join(f"<p>{html.escape(p, quote=False)}</p>" for p in paragraphs)
    return f"<html><head></head><body>{body}</body></html>"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paragraphs: list[str] = []
        self._current: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self._current.append("\n")
        elif tag in {"p", "li", "div"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "li", "div"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        self._current.append(data)

    def _flush(self) -> None:
        if text := "".join(self._current).strip():
            self.paragraphs.append(text)
        self._current = []

    def close(self) -> None:
        super().close()
        self._flush()


def to_text(document: str) -> str:
    """Readable text of an HTML description: tags dropped, paragraphs separated by a blank line."""
    extractor = _TextExtractor()
    extractor.feed(document)
    extractor.close()
    return "\n\n".join(extractor.paragraphs)
