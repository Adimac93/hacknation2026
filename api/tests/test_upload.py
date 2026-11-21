import io
import struct
import unicodedata
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import anyio
import pytest

from formcompiler.config import Settings
from formcompiler.upload import (
    OLE2_MAGIC,
    PNG_MAGIC,
    FileKind,
    UploadError,
    read_upload,
    validate,
)

DOCS = Path(__file__).resolve().parents[2] / "Docs"


def sample(pattern: str) -> Path:
    return next(DOCS.glob(pattern))


def make(**env: Any) -> Settings:
    return Settings(_env_file=None, **env)


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def ole2_bytes(*children: tuple[str, int]) -> bytes:
    """Minimal OLE2 file: a root storage with the given (name, type) children, all empty."""
    end, free, no_stream = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF
    # Version 3, 512-byte sectors: sector 0 holds the FAT, sector 1 the directory.
    header = OLE2_MAGIC + bytes(16)
    header += struct.pack("<HHHHH6s", 0x3E, 3, 0xFFFE, 9, 6, bytes(6))
    header += struct.pack("<IIIIIIIII", 0, 1, 1, 0, 4096, end, 0, end, 0)
    header += struct.pack("<I", 0) + struct.pack("<I", free) * 108
    fat = struct.pack("<II", 0xFFFFFFFD, end) + struct.pack("<I", free) * 126

    def entry(name: str, kind: int, left: int, right: int, child: int) -> bytes:
        encoded = (name + "\0").encode("utf-16-le")
        return (
            encoded.ljust(64, b"\0")
            + struct.pack("<HBBIII", len(encoded), kind, 1, left, right, child)
            + bytes(36)
            + struct.pack("<IQ", end, 0)
        )

    entries = [entry("Root Entry", 5, no_stream, no_stream, 1 if children else no_stream)]
    for i, (name, kind) in enumerate(children, start=1):
        right = i + 1 if i < len(children) else no_stream
        entries.append(entry(name, kind, no_stream, right, no_stream))
    directory = b"".join(entries).ljust(512, b"\0")
    return header + fat + directory


def png_header(width: int, height: int) -> bytes:
    return PNG_MAGIC + struct.pack(">I4sII", 13, b"IHDR", width, height) + bytes(5)


def jpeg_header(width: int, height: int) -> bytes:
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\0" + bytes(9)
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + bytes(3)
    return b"\xff\xd8" + app0 + sof + b"\xff\xd9"


SAMPLES = [
    ("3. */*.pdf", FileKind.PDF),
    ("5. */*.PDF", FileKind.PDF),
    ("3. */*.png", FileKind.PNG),
    ("3. */*.jpg", FileKind.JPEG),
    ("3. */*.jpeg", FileKind.JPEG),
    ("7. */*.JPE", FileKind.JPEG),
    ("3. */*.docx", FileKind.DOCX),
    ("3. */*.doc", FileKind.DOC),
    ("5. */*.DOC", FileKind.DOCX),
    ("7. */*.DOC", FileKind.DOCX),
    ("3. */*.xlsx", FileKind.XLSX),
    ("3. */*.ods", FileKind.ODS),
    ("5. */*.ODS", FileKind.ODS),
]


@pytest.mark.parametrize(("pattern", "kind"), SAMPLES)
def test_organiser_samples_are_accepted_by_signature(pattern: str, kind: FileKind) -> None:
    path = sample(pattern)

    assert validate(path.name, path.read_bytes(), make()) is kind


PDF = sample("3. */*.pdf").read_bytes()
DOCX = sample("3. */*.docx").read_bytes()
PNG = sample("3. */*.png").read_bytes()
XLSX = sample("3. */*.xlsx").read_bytes()
OOXML = {"[Content_Types].xml": b""}
ODS_MIMETYPE = {"mimetype": b"application/vnd.oasis.opendocument.spreadsheet"}
DOCX_WITH_MACRO = zip_bytes(OOXML | {"word/vbaProject.bin": b""})
ODS_WITH_MACRO = zip_bytes(ODS_MIMETYPE | {"Basic/script-lc.xml": b""})
ODT = zip_bytes({"mimetype": b"application/vnd.oasis.opendocument.text"})
ZIP_ENTRY_BOMB = zip_bytes(OOXML | {f"word/{i}.xml": b"" for i in range(1001)})
ZIP_SIZE_BOMB = zip_bytes(OOXML | {"word/document.xml": bytes(2 * 1024 * 1024)})


@pytest.mark.parametrize(
    ("filename", "data", "env", "status"),
    [
        *[(f"wniosek{c}.pdf", PDF, {}, 400) for c in ";:></\\|'*%$"],
        ("a" * 247 + ".pdf", PDF, {}, 400),
        ("wniosek\n.pdf", PDF, {}, 400),
        ("", PDF, {}, 400),
        ("wniosek.pdf", b"", {}, 400),
        ("wniosek.pdf", PDF, {"max_upload_mb": 0}, 413),
        ("wniosek.pdf", PDF + bytes(1024 * 1024), {"max_upload_mb": 1}, 413),
        ("wniosek.exe", PDF, {}, 415),
        ("wniosek", PDF, {}, 415),
        (".pdf", PDF, {}, 415),
        ("wniosek.png", PDF, {}, 415),
        ("wniosek.pdf", PNG, {}, 415),
        ("wniosek.doc", PDF, {}, 415),
        ("wniosek.doc", XLSX, {}, 415),
        ("wniosek.xlsx", DOCX, {}, 415),
        ("wniosek.pdf", b"plain text", {}, 415),
        ("wniosek.docx", DOCX[:2000], {}, 415),
        ("wniosek.docx", DOCX_WITH_MACRO, {}, 415),
        ("arkusz.ods", ODS_WITH_MACRO, {}, 415),
        ("tekst.ods", ODT, {}, 415),
        ("wniosek.docx", ZIP_ENTRY_BOMB, {}, 413),
        ("wniosek.docx", ZIP_SIZE_BOMB, {"max_unzipped_mb": 1}, 413),
        ("skan.png", png_header(100_000, 100_000), {}, 413),
        ("skan.png", PNG, {"max_image_pixels": 1000}, 413),
        ("skan.png", png_header(0, 10), {}, 415),
        ("skan.png", PNG_MAGIC + bytes(8), {}, 415),
        ("skan.jpg", jpeg_header(65_000, 65_000), {}, 413),
        ("skan.jpg", b"\xff\xd8\xff\xe0" + bytes(20), {}, 415),
        ("stary.doc", ole2_bytes(("WordDocument", 2), ("Macros", 1)), {}, 415),
        ("stary.doc", ole2_bytes(("Workbook", 2)), {}, 415),
        ("stary.doc", OLE2_MAGIC + bytes(600), {}, 415),
    ],
)
def test_invalid_uploads_are_rejected(
    filename: str, data: bytes, env: dict[str, Any], status: int
) -> None:
    with pytest.raises(UploadError) as error:
        validate(filename, data, make(**env))

    assert error.value.status == status


def test_name_of_250_characters_is_accepted() -> None:
    assert validate("a" * 246 + ".pdf", PDF, make()) is FileKind.PDF


def test_name_is_normalised_to_nfc_before_length_check() -> None:
    # 125 letters "ó" decomposed are 250 code points, composed only 125.
    name = unicodedata.normalize("NFD", "ó" * 125) + ".pdf"

    assert validate(name, PDF, make()) is FileKind.PDF


def test_minimal_ole2_with_word_stream_is_a_doc() -> None:
    assert validate("stary.doc", ole2_bytes(("WordDocument", 2)), make()) is FileKind.DOC


def test_jpeg_header_within_limit_is_accepted() -> None:
    assert validate("skan.jpg", jpeg_header(1654, 2339), make()) is FileKind.JPEG


async def chunks(body: bytes, size: int = 1000) -> AsyncIterator[bytes]:
    for start in range(0, len(body), size):
        yield body[start : start + size]


def multipart(filename: str, data: bytes, field: str = "file") -> tuple[str, bytes]:
    boundary = "granica123"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="note"\r\n\r\nx\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return f"multipart/form-data; boundary={boundary}", body


def read(
    content_type: str, body: bytes, length: str | None = None, **env: Any
) -> tuple[str, bytes]:
    return anyio.run(read_upload, content_type, length, chunks(body), make(**env))


def test_multipart_file_field_is_read_into_memory() -> None:
    content_type, body = multipart("wniosek ó.pdf", PDF)

    assert read(content_type, body) == ("wniosek ó.pdf", PDF)


def test_multipart_is_cut_off_once_file_passes_the_limit() -> None:
    content_type, body = multipart("duzy.pdf", PDF + bytes(1024 * 1024))

    with pytest.raises(UploadError) as error:
        read(content_type, body, max_upload_mb=1)

    assert error.value.status == 413


def test_declared_content_length_over_limit_is_rejected_before_reading() -> None:
    with pytest.raises(UploadError) as error:
        read("multipart/form-data; boundary=x", b"", length=str(50 * 1024 * 1024))

    assert error.value.status == 413


@pytest.mark.parametrize(
    ("content_type", "body", "status"),
    [
        ("application/pdf", PDF, 415),
        ("multipart/form-data", b"", 415),
        (*multipart("wniosek.pdf", PDF, field="dokument"), 400),
        ("multipart/form-data; boundary=granica123", b"--granica123\r\nzepsute", 400),
    ],
)
def test_malformed_multipart_is_rejected(content_type: str, body: bytes, status: int) -> None:
    with pytest.raises(UploadError) as error:
        read(content_type, body)

    assert error.value.status == status
