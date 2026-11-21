# 09. Licencje zależności i wag

Raport generuje bramka licencyjna: `python3 devtools/check_licenses.py --write`. Nie poprawiaj go ręcznie.

Zasada (`CLAUDE.md`, zasada twarda 1): MIT, BSD, Apache-2.0, ISC, 0BSD, PSF; SIL OFL-1.1 tylko dla fontów Archivo i IBM Plex Mono (D25). Bramka kończy się błędem, gdy pakiet ma inną licencję i nie ma go na liście wyjątków w `devtools/check_licenses.py`. Wyjątek wiąże się z dokładnym tekstem licencji z metadanych, więc zmiana licencji w nowej wersji pakietu znowu zatrzymuje bramkę.

Zakres: zależności uruchomieniowe `api/` (`uv export --no-dev`, licencje odczytuje `pip-licenses`, sam na MIT, zależność deweloperska) oraz wszystkie pakiety z `web/package-lock.json`, także deweloperskie. Wyrażenie `OR` przechodzi, gdy dozwolona jest jedna z alternatyw, `AND` tylko wtedy, gdy dozwolone są wszystkie części.

## Do potwierdzenia z mentorem: słaby copyleft (MPL-2.0)

Dwie zależności przechodnie mają licencję MPL-2.0. MPL-2.0 to copyleft na poziomie pliku: obowiązki dotyczą tylko zmienionych plików samej biblioteki, nie naszego kodu. Używamy ich bez zmian, jako osobnych plików. Bramka je przepuszcza z ostrzeżeniem; każdy inny pakiet na MPL, LGPL lub GPL zatrzymuje bramkę.

| Pakiet | Wersja | Licencja | Dlaczego nie da się go usunąć |
|---|---|---|---|
| `certifi` | 2026.11.20 | MPL-2.0 | Twarda zależność `httpx` i `httpcore` (import przy ładowaniu modułu) oraz `requests` przez `rapidocr`. Zawiera tylko pakiet certyfikatów CA Mozilli (plik danych). Bez `httpx` nie ma klienta modelu ani Tiki, bez `rapidocr` nie ma OCR. |
| `tqdm` | 4.70.1 | MPL-2.0 AND MIT | Twarda zależność `rapidocr` (paski postępu przy pobieraniu modeli). Bez `rapidocr` nie ma OCR rastrów. |

## Wyjątki permisywne

Licencje spoza listy, sprawdzone ręcznie; wszystkie są permisywne.

| Pakiet | Wersja | Licencja w metadanych | Ustalenie |
|---|---|---|---|
| `cffi` | 2.1.1 | MIT-0 | MIT bez wymogu zachowania noty; licencja permisywna. |
| `numpy` | 2.5.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Rdzeń BSD-3-Clause; dołączone fragmenty na 0BSD, MIT, Zlib i CC0-1.0, bez copyleftu. |
| `pillow` | 13.0.0 | MIT-CMU | Licencja PIL (rodzina HPND), permisywna. |
| `pypdfium2` | 5.15.2 | BSD-3-Clause, Apache-2.0, dependency licenses | PDFium na BSD-3-Clause; w binarce FreeType na FTL (wybór z FTL lub GPL-2.0), libjpeg-turbo, libpng, libtiff, zlib, lcms2, OpenJPEG, HarfBuzz, ICU, abseil: licencje permisywne (`BUILD_LICENSES/` w pakiecie). Licencje musl i libgcc dotyczą tylko kół musllinux, nie obrazu na glibc. |

## Python: zależności uruchomieniowe `api/` (50)

| Pakiet | Wersja | Licencja w metadanych | Ocena |
|---|---|---|---|
| `annotated-doc` | 0.0.7 | MIT | dozwolona |
| `annotated-types` | 0.8.0 | MIT | dozwolona |
| `anyio` | 4.16.0 | MIT | dozwolona |
| `certifi` | 2026.11.20 | Mozilla Public License 2.0 (MPL 2.0) | **wyjątek: słaby copyleft, do potwierdzenia** |
| `cffi` | 2.1.1 | MIT-0 | wyjątek: permisywna |
| `charset-normalizer` | 3.5.2 | MIT | dozwolona |
| `click` | 8.5.1 | BSD-3-Clause | dozwolona |
| `colorlog` | 6.12.0 | MIT License | dozwolona |
| `cryptography` | 50.0.2 | Apache-2.0 OR BSD-3-Clause | dozwolona |
| `fastapi` | 0.165.0 | MIT | dozwolona |
| `flatbuffers` | 25.12.19 | Apache Software License | dozwolona |
| `h11` | 0.16.0 | MIT License | dozwolona |
| `httpcore` | 1.0.9 | BSD-3-Clause | dozwolona |
| `httptools` | 0.9.0 | MIT | dozwolona |
| `httpx` | 0.28.1 | BSD License | dozwolona |
| `idna` | 3.20 | BSD-3-Clause | dozwolona |
| `numpy` | 2.5.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | wyjątek: permisywna |
| `olefile` | 0.47 | BSD License | dozwolona |
| `omegaconf` | 2.4.0 | BSD License | dozwolona |
| `onnxruntime` | 1.32.0 | MIT License | dozwolona |
| `opencv-python-headless` | 5.1.0.95 | Apache Software License | dozwolona |
| `opentelemetry-api` | 1.45.2 | Apache-2.0 | dozwolona |
| `packaging` | 26.3 | Apache-2.0 OR BSD-2-Clause | dozwolona |
| `pdfminer.six` | 20260107 | MIT | dozwolona |
| `pdfplumber` | 0.11.11 | MIT License | dozwolona |
| `pillow` | 13.0.0 | MIT-CMU | wyjątek: permisywna |
| `protobuf` | 7.36.2 | 3-Clause BSD License | dozwolona |
| `pyclipper` | 1.4.0 | MIT License | dozwolona |
| `pycparser` | 3.12 | BSD-3-Clause | dozwolona |
| `pydantic` | 2.14.4 | MIT | dozwolona |
| `pydantic-settings` | 2.16.3 | MIT | dozwolona |
| `pydantic_core` | 2.50.5 | MIT | dozwolona |
| `PyJWT` | 2.15.1 | MIT | dozwolona |
| `pypdfium2` | 5.15.2 | BSD-3-Clause, Apache-2.0, dependency licenses | wyjątek: permisywna |
| `python-dotenv` | 1.2.4 | BSD-3-Clause | dozwolona |
| `python-multipart` | 0.0.34 | Apache-2.0 | dozwolona |
| `PyYAML` | 6.0.4 | MIT License | dozwolona |
| `rapidocr` | 3.10.0 | Apache-2.0 | dozwolona |
| `requests` | 2.34.2 | Apache Software License | dozwolona |
| `shapely` | 2.2.0 | BSD-3-Clause | dozwolona |
| `six` | 1.17.0 | MIT License | dozwolona |
| `starlette` | 1.10.0 | BSD-3-Clause | dozwolona |
| `tqdm` | 4.70.1 | MPL-2.0 AND MIT | **wyjątek: słaby copyleft, do potwierdzenia** |
| `typing-inspection` | 0.4.5 | MIT | dozwolona |
| `typing_extensions` | 4.16.0 | PSF-2.0 | dozwolona |
| `urllib3` | 2.8.0 | MIT | dozwolona |
| `uvicorn` | 0.54.0 | BSD-3-Clause | dozwolona |
| `uvloop` | 0.23.0 | Apache Software License; MIT License | dozwolona |
| `watchfiles` | 1.3.0 | MIT License | dozwolona |
| `websockets` | 17.4 | BSD-3-Clause | dozwolona |

Pominięte, bo nie instalują się na tej platformie (znacznik środowiska): `colorama`.

## npm: zależności `web/` w pakiecie aplikacji (9)

| Pakiet | Wersja | Licencja | Ocena |
|---|---|---|---|
| `@fontsource/archivo` | 5.3.0 | OFL-1.1 | font (D25) |
| `@fontsource/ibm-plex-mono` | 5.3.0 | OFL-1.1 | font (D25) |
| `@types/react` | 19.3.0 | MIT | dozwolona |
| `csstype` | 3.2.4 | MIT | dozwolona |
| `jsonata` | 2.2.2 | MIT | dozwolona |
| `lucide-react` | 1.77.0 | ISC | dozwolona |
| `react` | 19.3.1 | MIT | dozwolona |
| `react-dom` | 19.3.1 | MIT | dozwolona |
| `scheduler` | 0.28.0 | MIT | dozwolona |

## npm: narzędzia deweloperskie `web/` (141, poza obrazem)

| Licencja | Pakietów |
|---|---|
| Apache-2.0 | 23 |
| BSD-2-Clause | 1 |
| BSD-3-Clause | 1 |
| ISC | 1 |
| MIT | 104 |
| MIT OR Apache-2.0 | 11 |

## Wagi modeli

Wagi nie są pakietami, licencje sprawdzone ręcznie (`research/01`, `research/06`).

| Wagi | Licencja | Użycie |
|---|---|---|
| RapidOCR PP-OCRv6 small (detekcja, rozpoznawanie) | Apache-2.0 | OCR rastrów, w obrazie |
| Tesseract 5, dane `pol` (tessdata) | Apache-2.0 | zapasowy OCR, w obrazie |
| Qwen3.5-9B | Apache-2.0 | model językowy, przez `LLM_BASE_URL`, poza obrazem |

Programy uruchamiane jako osobne procesy: Apache Tika Server (Apache-2.0), Tesseract 5 (Apache-2.0), nginx (BSD-2-Clause); docelowy lokalny serwer modelu `llama-server` z llama.cpp (MIT). Bramka nie obejmuje obrazów bazowych Dockera (system, środowisko Java dla Tiki).
