"""Upload validation: size, name, extension and content signature, all on bytes held in memory."""

import io
import struct
import unicodedata
import zipfile
from collections.abc import AsyncIterator
from enum import StrEnum

import olefile
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header

from formcompiler.config import Settings

MB = 1024 * 1024
MAX_NAME_LENGTH = 250
FORBIDDEN_NAME_CHARS = frozenset(";:></\\|'*%$")
# Room for the multipart envelope around the file in the declared Content-Length.
MULTIPART_OVERHEAD = 64 * 1024
FILE_FIELD = "file"

ODS_MIMETYPE = b"application/vnd.oasis.opendocument.spreadsheet"
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
# JPEG start-of-frame markers that carry image dimensions (all SOFn except DHT, JPG, DAC).
JPEG_SOF = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})
# OLE2 storages that hold VBA projects in Word (Macros) and Excel (_VBA_PROJECT_CUR) files.
OLE2_MACRO_STORAGES = frozenset({"macros", "_vba_project_cur", "vba"})
# OpenDocument keeps Basic macros and scripts in these top-level folders.
ODF_MACRO_DIRS = ("Basic/", "Scripts/")


class FileKind(StrEnum):
    PDF = "PDF"
    PNG = "PNG"
    JPEG = "JPEG"
    DOCX = "DOCX"
    DOC = "DOC"
    XLSX = "XLSX"
    ODS = "ODS"


WORD = frozenset({FileKind.DOC, FileKind.DOCX})
# .doc and .docx are one "Word document" family: two organiser samples are .DOC with OOXML inside.
ALLOWED_KINDS: dict[str, frozenset[FileKind]] = {
    "pdf": frozenset({FileKind.PDF}),
    "png": frozenset({FileKind.PNG}),
    "jpg": frozenset({FileKind.JPEG}),
    "jpeg": frozenset({FileKind.JPEG}),
    "jpe": frozenset({FileKind.JPEG}),
    "doc": WORD,
    "docx": WORD,
    "xlsx": frozenset({FileKind.XLSX}),
    "ods": frozenset({FileKind.ODS}),
}


class UploadError(Exception):
    """Rejected upload; `title` and `detail` are shown to the user."""

    def __init__(self, status: int, title: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail


def bad_name(detail: str) -> UploadError:
    return UploadError(400, "Nieprawidłowa nazwa pliku", detail)


def too_large(detail: str) -> UploadError:
    return UploadError(413, "Plik jest za duży", detail)


def unsupported(detail: str) -> UploadError:
    return UploadError(415, "Nieobsługiwany typ pliku", detail)


def validate(filename: str, data: bytes, settings: Settings) -> FileKind:
    """Check an upload in the order size, name, extension, content; return the detected format."""
    if len(data) > settings.max_upload_mb * MB:
        raise too_large(f"Maksymalny rozmiar pliku to {settings.max_upload_mb} MB.")
    if not data:
        raise UploadError(400, "Pusty plik", "Przesłany plik nie zawiera danych.")
    extension = check_name(filename)
    allowed = ALLOWED_KINDS.get(extension)
    if allowed is None:
        raise unsupported(
            "Dozwolone rozszerzenia: " + ", ".join(f".{e}" for e in ALLOWED_KINDS) + "."
        )
    kind = detect(data, settings)
    if kind not in allowed:
        raise unsupported("Treść pliku nie odpowiada jego rozszerzeniu.")
    return kind


def check_name(filename: str) -> str:
    """Validate the name and return its lower-case extension (empty when there is none)."""
    name = unicodedata.normalize("NFC", filename)
    if not name.strip():
        raise bad_name("Plik musi mieć nazwę.")
    if len(name) > MAX_NAME_LENGTH:
        raise bad_name(f"Nazwa pliku może mieć najwyżej {MAX_NAME_LENGTH} znaków.")
    if FORBIDDEN_NAME_CHARS & set(name) or any(unicodedata.category(c) == "Cc" for c in name):
        raise bad_name("Nazwa pliku zawiera niedozwolony znak: ; : > < / \\ | ' * % $")
    stem, dot, extension = name.rpartition(".")
    return extension.lower() if dot and stem else ""


def detect(data: bytes, settings: Settings) -> FileKind | None:
    """Recognise the format by its signature and reject macros and decompression bombs."""
    if data.startswith(b"%PDF-"):
        return FileKind.PDF
    if data.startswith(PNG_MAGIC):
        check_pixels(png_size(data), settings)
        return FileKind.PNG
    if data.startswith(b"\xff\xd8\xff"):
        check_pixels(jpeg_size(data), settings)
        return FileKind.JPEG
    if data.startswith(b"PK\x03\x04"):
        return detect_zip(data, settings)
    if data.startswith(OLE2_MAGIC):
        return detect_ole2(data)
    return None


def check_pixels(size: tuple[int, int], settings: Settings) -> None:
    width, height = size
    if width <= 0 or height <= 0:
        raise unsupported("Plik obrazu jest uszkodzony.")
    if width * height > settings.max_image_pixels:
        raise too_large(f"Obraz ma za dużo pikseli (limit {settings.max_image_pixels}).")


def png_size(data: bytes) -> tuple[int, int]:
    """Width and height from the IHDR chunk, which must come right after the signature."""
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise unsupported("Plik PNG jest uszkodzony.")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def jpeg_size(data: bytes) -> tuple[int, int]:
    """Width and height from the first start-of-frame segment, without decoding the image."""
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            break
        marker = data[pos + 1]
        if marker == 0xFF:  # fill byte
            pos += 1
            continue
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # standalone markers without length
            pos += 2
            continue
        (length,) = struct.unpack(">H", data[pos + 2 : pos + 4])
        if marker in JPEG_SOF and pos + 9 <= len(data):
            height, width = struct.unpack(">HH", data[pos + 5 : pos + 9])
            return width, height
        if marker == 0xDA or length < 2:  # start of scan before any frame header
            break
        pos += 2 + length
    raise unsupported("Plik JPEG jest uszkodzony.")


def detect_zip(data: bytes, settings: Settings) -> FileKind | None:
    """Tell ODS, DOCX and XLSX apart by their entries.

    The bomb check sums declared sizes; zipfile never inflates an entry past its declared size,
    so later readers stay within the same bound.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile, ValueError:
        raise unsupported("Archiwum pliku jest uszkodzone.") from None
    with archive:
        entries = archive.infolist()
        if len(entries) > settings.max_zip_entries:
            raise too_large(f"Plik zawiera za dużo elementów (limit {settings.max_zip_entries}).")
        if sum(e.file_size for e in entries) > settings.max_unzipped_mb * MB:
            raise too_large(f"Plik po rozpakowaniu przekracza {settings.max_unzipped_mb} MB.")
        names = {e.filename for e in entries}
        if any(n.rsplit("/", 1)[-1].lower() == "vbaproject.bin" for n in names) or any(
            n.startswith(ODF_MACRO_DIRS) for n in names
        ):
            raise unsupported("Pliki z makrami nie są przyjmowane.")
        if "mimetype" in names:
            mimetype = archive.getinfo("mimetype")
            if mimetype.file_size > 256:
                return None
            try:
                content = archive.read(mimetype).strip()
            except zipfile.BadZipFile, ValueError, OSError:
                raise unsupported("Archiwum pliku jest uszkodzone.") from None
            return FileKind.ODS if content == ODS_MIMETYPE else None
        if "[Content_Types].xml" in names:
            if any(n.startswith("word/") for n in names):
                return FileKind.DOCX
            if any(n.startswith("xl/") for n in names):
                return FileKind.XLSX
    return None


def detect_ole2(data: bytes) -> FileKind | None:
    """Word 97-2003 is an OLE2 container with a WordDocument stream."""
    try:
        with olefile.OleFileIO(io.BytesIO(data)) as ole:
            paths = ole.listdir(streams=True, storages=True)
            has_word_stream = ole.exists("WordDocument")
    # olefile raises many exception types on malformed input; any of them means a broken file.
    except Exception:
        raise unsupported("Plik DOC jest uszkodzony.") from None
    if any(part.lower() in OLE2_MACRO_STORAGES for path in paths for part in path):
        raise unsupported("Pliki z makrami nie są przyjmowane.")
    return FileKind.DOC if has_word_stream else None


async def read_upload(
    content_type: str | None,
    content_length: str | None,
    body: AsyncIterator[bytes],
    settings: Settings,
) -> tuple[str, bytes]:
    """Stream a multipart body into memory and return the name and bytes of the `file` field.

    Nothing touches the disk: parts are parsed as they arrive and the file is cut off the moment
    it passes the size limit.
    """
    limit = settings.max_upload_mb * MB
    body_limit = limit + MULTIPART_OVERHEAD
    too_big = too_large(f"Maksymalny rozmiar pliku to {settings.max_upload_mb} MB.")
    if content_length is not None and content_length.isdigit() and int(content_length) > body_limit:
        raise too_big

    mime, params = parse_options_header(content_type)
    boundary = params.get(b"boundary")
    if mime != b"multipart/form-data" or not boundary:
        raise UploadError(
            415, "Nieobsługiwany format żądania", "Prześlij plik jako multipart/form-data."
        )

    header_name = bytearray()
    header_value = bytearray()
    headers: dict[str, str] = {}
    current: bytearray | None = None
    filename: str | None = None
    data = bytearray()
    found = False

    def on_part_begin() -> None:
        headers.clear()

    def on_header_field(chunk: bytes, start: int, end: int) -> None:
        header_name.extend(chunk[start:end])

    def on_header_value(chunk: bytes, start: int, end: int) -> None:
        header_value.extend(chunk[start:end])

    def on_header_end() -> None:
        headers[header_name.decode("latin-1").lower()] = header_value.decode("latin-1")
        header_name.clear()
        header_value.clear()

    def on_headers_finished() -> None:
        nonlocal current, filename, found
        _, disposition = parse_options_header(headers.get("content-disposition"))
        if disposition.get(b"name") == FILE_FIELD.encode() and not found:
            found = True
            raw = disposition.get(b"filename", b"")
            try:
                filename = raw.decode("utf-8")
            except UnicodeDecodeError:
                filename = raw.decode("latin-1")
            current = data
        else:
            current = None

    def on_part_data(chunk: bytes, start: int, end: int) -> None:
        if current is not None:
            current.extend(chunk[start:end])
            if len(current) > limit:
                raise too_big

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_headers_finished": on_headers_finished,
            "on_part_data": on_part_data,
        },
    )
    received = 0
    try:
        async for chunk in body:
            received += len(chunk)
            if received > body_limit:
                raise too_big
            parser.write(chunk)
        parser.finalize()
    except MultipartParseError:
        raise UploadError(
            400, "Nieprawidłowe żądanie", "Treść multipart jest uszkodzona."
        ) from None
    if not found or filename is None:
        raise UploadError(400, "Brak pliku", f"Żądanie musi zawierać plik w polu {FILE_FIELD}.")
    return filename, bytes(data)
