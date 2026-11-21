import io
import zipfile
from pathlib import Path

import commoncrawl
import httpx
import pytest
from commoncrawl import detect_kind, done_urls, download, form_type, is_official


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (b"%PDF-1.7\n", "pdf"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1rest", "ole"),
        (b"  {\\rtf1\\ansi", "rtf"),
        (zip_bytes({"word/document.xml": b"<w/>"}), "docx"),
        (zip_bytes({"xl/workbook.xml": b"<x/>"}), "xlsx"),
        (zip_bytes({"mimetype": b"application/vnd.oasis.opendocument.text"}), "odt"),
        (zip_bytes({"mimetype": b"application/vnd.oasis.opendocument.spreadsheet"}), "ods"),
        (zip_bytes({"mimetype": b"application/epub+zip"}), None),
        (b"PK\x03\x04broken", None),
        (b"<html>", None),
    ],
)
def test_detect_kind_by_signature(data: bytes, kind: str | None) -> None:
    assert detect_kind(data) == kind


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://bip.x.pl/wniosek-o-zajecie-pasa-drogowego.pdf", "pas_drogowy"),
        ("https://x.pl/druki/deklaracja_odpady_2026.docx", "odpady"),
        ("https://x.pl/Wniosek_Świetlica.odt", "swietlica"),
        ("https://x.pl/wniosek-stypendium-sportowe.pdf", "stypendium_sportowe"),
        ("https://x.pl/zezwolenie-psy-rasy-agresywnej-wniosek.doc", "psy_agresywne"),
        ("https://x.pl/wniosek-numer-porzadkowy.pdf", "numer_porzadkowy"),
        ("https://x.pl/wniosek-o-wydanie-zaswiadczenia.pdf", "zaswiadczenie"),
        ("https://x.pl/nadplata-podatku-wniosek.pdf", "nadplata"),
        ("https://x.pl/wniosek-o-dowod-osobisty.pdf", None),
    ],
)
def test_form_type(url: str, expected: str | None) -> None:
    assert form_type(url) == expected


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("www.gov.pl", True),
        ("gminax.gov.pl", True),
        ("bip.gminax.pl", True),
        ("gminax.bip.net.pl", True),
        ("www.ug.zlota.pl", True),
        ("um.warszawa.pl", True),
        ("ug.edu.pl", False),
        ("sklep-druki.pl", False),
        ("www.bipolar.pl", False),
    ],
)
def test_is_official(host: str, expected: bool) -> None:
    assert is_official(host) is expected


def test_download_waits_out_throttling_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []
    monkeypatch.setattr(commoncrawl.time, "sleep", waits.append)
    calls: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers.get("Range"))
        if len(calls) == 1:
            return httpx.Response(503)
        return httpx.Response(206, content=b"def")

    dest = tmp_path / "part-0.parquet"
    (tmp_path / "part-0.parquet.part").write_bytes(b"abc")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        download(client, "https://example.test/part-0.parquet", dest)

    assert dest.read_bytes() == b"abcdef"
    assert calls == ["bytes=3-", "bytes=3-"]
    assert len(waits) == 1


def test_download_gives_up_on_not_found(tmp_path: Path) -> None:
    with (
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        download(client, "https://example.test/x", tmp_path / "x")


def test_done_urls_skips_failed_fetches(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        '{"url": "https://a.pl/1.pdf", "sha256": "x"}\n'
        '{"url": "https://a.pl/2.pdf", "error": "HTTP 403"}\n',
        encoding="utf-8",
    )
    assert done_urls(manifest) == {"https://a.pl/1.pdf"}
    assert done_urls(tmp_path / "missing.jsonl") == set()
