# 04 — Stos aplikacyjny, licencje, Docker i frontend podglądu formularza

Stan na 2026-11-21. Wersje i licencje sprawdzone przez PyPI JSON API, npm registry, Maven Central (`maven-metadata.xml`), Docker Hub API, GHCR oraz pliki `LICENSE` w repozytoriach. „Zweryfikowane dla 3.14” oznacza: istnieje wheel `cp314` albo wheel czysto pythonowy z pasującym `requires_python`. Nic nie zostało uruchomione testowo.

## 1. Rekomendacja

- **Główna:** Python **3.14.10** + FastAPI 0.165 + Pydantic 2.14 + uvicorn, zależności przez `uv` z `uv.lock`. OCR przez `onnxruntime` (bez PyTorch), LLM w osobnym kontenerze `llama.cpp server`.
- **Zapasowa:** Java 25 LTS + Spring Boot 4.2.0 + Apache Tika 4.2 / POI 6.0 / PDFBox 3.0.8 + `com.dashjoin:jsonata`. Tylko gdy zespół jest wyłącznie javowy.
- **Nie 3.15 i nie free-threaded:** `onnxruntime` 1.32.0 nie ma wheela `cp315`, a `cp314t` ma tylko dla Linuksa. 3.14 spełnia wymóg „3.14 lub nowszy”.
- **Docker:** `api` na `python:3.14.10-slim-trixie` (wheele ML nie mają wariantu musl), `web` na `nginxinc/nginx-unprivileged:1.30.6-alpine-slim`, `llm` na `ghcr.io/ggml-org/llama.cpp:server-v0.5.0@sha256:…`. Publikowany tylko port 8080.
- **Frontend:** React 19.3 + Vite 8.3 + TypeScript 7.0, `jsonata` 2.2.2, `pdfjs-dist` 6.5, `vanilla-jsoneditor` 3.13. Zapasowo: HTMX 2.0 + szablony serwerowe, bez renderera e-formularza.
- **Licencje:** bramka w CI (`pip-licenses --fail-on`, `license-checker-rseidelsohn --onlyAllow`, `trivy --scanners license`). Pułapki do ominięcia: PyMuPDF, Ultralytics, `unidecode`, `odfpy`, poppler, wagi Surya, MinerU, `orjson` (MPL-2.0).

## 2. Python 3.14 czy Java 21+

### Python — status pakietów (PyPI, 2026-11-21)

| Pakiet | Wersja | Licencja | Python 3.14 | linux/arm64 (Docker na M4) | Alpine (musl) | Werdykt |
|---|---|---|---|---|---|---|
| fastapi | 0.165.0 | MIT | tak (pure, ≥3.11) | tak | tak | używać |
| starlette | 1.10.0 | BSD-3-Clause | tak (pure) | tak | tak | pośrednio |
| pydantic / pydantic-core | 2.14.4 / 2.50.5 | MIT | tak (cp314, cp314t) | tak | tak | używać |
| pydantic-settings | 2.16.3 | MIT | tak (pure) | tak | tak | używać |
| uvicorn | 0.54.0 | BSD-3-Clause | tak (pure) | tak | tak | używać |
| granian | 2.8.9 | BSD-3-Clause | tak (cp314, cp314t) | tak | tak | alternatywa |
| python-multipart | 0.0.34 | Apache-2.0 | tak (pure) | tak | tak | używać |
| httpx | 0.28.1 (2024-12) | BSD-3-Clause | tak (pure) | tak | tak | używać; brak wydań od 2 lat |
| PyJWT | 2.15.1 | MIT | tak (pure) | tak | tak | używać |
| joserfc / Authlib | 1.8.0 / 1.9.10 | BSD-3-Clause | tak (pure) | tak | tak | zbędne |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | tak (abi3) | tak | tak | dla RS256 |
| onnxruntime | 1.32.0 | MIT | tak (cp314) | tak (manylinux_2_28) | **nie** | używać |
| torch | 2.15.0 | BSD-3-Clause i inne permisywne | tak (cp314, cp314t) | tak | **nie** | unikać (rozmiar) |
| numpy | 2.5.5 | BSD-3-Clause | tak | tak | tak | używać |
| Pillow | 13.0.0 | MIT-CMU | tak | tak | tak | używać |
| opencv-python-headless | 5.1.0.95 | Apache-2.0 | tak (abi3) | tak | **nie** | tylko wariant headless |
| docling | 2.151.1 | MIT | tak; `docling-parse` 7.27 ma cp314 | tak | **nie** | opcjonalnie; ciągnie torch |
| paddlepaddle | 3.3.1 | Apache-2.0 | **nie** (cp39–cp313) | **nie** (tylko x86_64) | nie | odrzucić |
| paddleocr | 3.7.0 | Apache-2.0 | wymaga paddlepaddle | nie | nie | odrzucić |
| rapidocr | 3.10.0 | Apache-2.0 | tak (pure) + onnxruntime | tak | nie (opencv, pyclipper) | używać |
| rapidocr-onnxruntime | 1.4.4 | Apache-2.0 | **nie** (`<3.13`) | — | — | stary pakiet, nie używać |
| pytesseract | 0.3.13 (2024) | Apache-2.0 | pure; nie testowano | tak | tak (apk `tesseract-ocr` 5.5.2 + `-data-pol`) | zapasowy OCR |
| pypdfium2 | 5.15.2 | Apache-2.0 OR BSD-3-Clause | tak (py3-none) | tak | tak | używać |
| pdfplumber | 0.11.11 | MIT | tak (pure) | tak | tak | używać |
| python-docx | 1.2.0 (2025-06) | MIT | pure; nie testowano | tak | tak | używać |
| openpyxl | 3.1.5 (2024-06) | MIT | pure; nie testowano | tak | tak | używać |
| python-calamine | 0.9.1 | MIT | tak (cp314, cp314t) | tak | tak | używać do ODS |
| odfpy | 1.4.1 (2020) | Apache-2.0 OR GPL-2.0+ | tylko sdist | — | — | odrzucić |
| jsonata-python | 0.7.2 | Apache-2.0 | tak (pure, ≥3.10) | tak | tak | używać |
| jsonschema | 4.26.0 | MIT | tak (pure) | tak | tak | opcjonalnie |
| structlog | 26.1.0 | MIT OR Apache-2.0 | tak (pure) | tak | tak | opcjonalnie |
| pytest / ruff / mypy | 9.2.0 / 0.17.6 / 2.4.1 | MIT | tak | tak | tak | używać |
| pyright / ty | 1.1.414 / 0.0.107 | MIT | tak | tak | tak | `ty` nadal 0.0.x — pominąć |
| uv | 0.13.9 | MIT OR Apache-2.0 | tak | tak | tak | używać |

Wnioski:

- **PaddlePaddle odpada podwójnie:** brak wheeli `cp314` i brak wheeli Linux aarch64. Modele PP-OCR da się uruchomić przez `rapidocr` + `onnxruntime`.
- **Free-threaded (3.14t):** PEP 779 daje status „wspierany”, ale Docker Hub nie ma tagów `python:3.14t`, a `onnxruntime` (tylko Linux), `docling-parse`, `opencv` i `orjson` nie mają kompletu wheeli `cp314t`. Zysk byłby znikomy: ciężką pracę wykonuje kod natywny i osobny proces `llama-server`.
- **Python 3.15** już istnieje (wheele `cp315` mają m.in. torch, numpy, pydantic-core), ale `onnxruntime` 1.32.0 go nie obsługuje.

### Java — status (Maven Central, 2026-11-21)

| Biblioteka | Wersja | Licencja | Uwagi |
|---|---|---|---|
| Spring Boot | 4.2.0 (2026-11-19) | Apache-2.0 | 3.5 straciło wsparcie OSS 2026-06-30 — nie wybierać |
| Spring AI | 2.1.0 (2026-11-19) | Apache-2.0 | wymaga Boot 4.x |
| LangChain4j | 1.24.0 | Apache-2.0 | |
| Apache Tika | 4.2.0 (linia 3.3.x nadal utrzymywana) | Apache-2.0 | najlepsza detekcja typu pliku |
| Apache POI | 6.0.0 | Apache-2.0 | DOC, DOCX, XLSX |
| PDFBox | 3.0.8 | Apache-2.0 | |
| Tess4J | 5.21.0 | Apache-2.0 | wymaga natywnego Tesseract w obrazie |
| JSONata4Java (IBM) | 3.0.0 | Apache-2.0 | |
| dashjoin jsonata-java | 0.9.11 | Apache-2.0 | port referencyjny, bez zależności |
| onnxruntime (Java) | 1.32.0 | MIT | |

Baza: `eclipse-temurin:25-jre-alpine-3.24` (78 MB skompresowane).

### Werdykt

Python. Powody:

1. **Ekosystem ML/OCR:** `rapidocr`, `onnxruntime`, `pypdfium2`, `pdfplumber`, `docling` mają gotowe wheele `cp314` dla x86_64 i aarch64. W Javie OCR i analizę układu trzeba składać ręcznie.
2. **Preferencja organizatorów** obejmuje Pythona 3.14+ wprost.
3. **Tempo:** jeden model Pydantic jest schematem wyjścia, walidatorem odpowiedzi LLM (`json_schema` w `llama-server`) i dokumentacją OpenAPI.
4. **Jakość kodu:** `ruff` + `mypy --strict` + `pytest` dają czytelny sygnał przy małym nakładzie.

Java wygrywa tylko w dwóch punktach: Tika + POI obsługują DOC bez dodatkowego kontenera, a JRE działa natywnie na Alpine.

## 3. Audyt licencji

### Rekomendowane zależności

| Zależność | SPDX | Copyleft | Uwaga |
|---|---|---|---|
| fastapi, pydantic, pydantic-settings, PyJWT, pdfplumber, pdfminer.six, python-docx, openpyxl, python-calamine, puremagic, pytest, ruff, mypy | MIT | nie | |
| starlette, uvicorn, httpx, numpy, lxml | BSD-3-Clause | nie | numpy zawiera też 0BSD, MIT, Zlib |
| python-multipart, rapidocr, jsonata-python, opencv-python-headless | Apache-2.0 | nie | |
| cryptography | Apache-2.0 OR BSD-3-Clause | nie | |
| onnxruntime | MIT | nie | |
| Pillow | MIT-CMU | nie | |
| pypdfium2 (+ PDFium) | Apache-2.0 OR BSD-3-Clause | nie | PDFium: BSD-3-Clause |
| olefile | BSD-2-Clause | nie | detekcja OLE2 |
| defusedxml | PSF-2.0 | nie | ostatnie wydanie 2021 |
| uv | MIT OR Apache-2.0 | nie | |
| react, react-dom, vite, jsonata (npm), react-hook-form, zod | MIT | nie | |
| typescript, pdfjs-dist, react-aria-components | Apache-2.0 | nie | |
| vanilla-jsoneditor | ISC | nie | |
| @biomejs/biome | MIT OR Apache-2.0 | nie | lint + format + reguły a11y |
| llama.cpp (obraz `server`) | MIT | nie | baza Ubuntu 26.04 |
| nginx (obraz unprivileged) | BSD-2-Clause; Dockerfile Apache-2.0 | nie | |
| Apache Tika (kontener pomocniczy dla DOC) | Apache-2.0 | nie | obraz `apache/tika`, nie „Docker Official Image” |
| Tesseract + `traineddata` (zapas) | Apache-2.0 | nie | |

### Pułapki

| Pakiet | Stan faktyczny | Decyzja |
|---|---|---|
| PyMuPDF 2.1 | AGPL-3.0 lub licencja komercyjna Artifex | zakaz; `pypdfium2` + `pdfplumber` |
| Surya 0.24 / Marker 2.2 | kod od 2026-07 na Apache-2.0, **wagi** na zmodyfikowanej AI Pubs OpenRAIL-M z progami przychodu | zakaz (wagi nie są wolne) |
| MinerU 4.2.3 | `LicenseRef-MinerU-Open-Source-License`: Apache-2.0 plus dodatkowe warunki; starsze wersje AGPL-3.0 | zakaz (licencja niestandardowa) |
| Ultralytics 8.4 | AGPL-3.0 | zakaz |
| poppler, `pdf2image` | `pdf2image` jest MIT, ale wywołuje poppler (GPL) | zakaz |
| antiword, catdoc | GPL | zakaz; DOC przez Tika (POI HWPF) |
| LibreOffice | MPL-2.0 / LGPL-3.0+ | ryzykowne; tylko jako ostateczność, osobny proces |
| python-magic + libmagic | MIT + BSD-2-Clause | dozwolone, ale wymaga biblioteki systemowej i nie rozróżnia podtypów OOXML |
| unidecode | GPL-2.0-or-later | zakaz; `anyascii` (ISC) |
| text-unidecode | Artistic-1.0 OR GPL | ryzykowne; `anyascii` |
| chardet 7.7 | 0BSD po przepisaniu z pomocą AI; relicencjonowanie z LGPL jest sporne | unikać; `charset-normalizer` (MIT) |
| psycopg 3.3 | LGPL-3.0-only | niepotrzebne (brak bazy) |
| odfpy 1.4.1 | Apache-2.0 OR GPL-2.0+, tylko sdist, 2020 | unikać; `python-calamine` |
| orjson 3.13 | `MPL-2.0 AND (Apache-2.0 OR MIT)` | **nowa pułapka**; nie dodawać |
| axe-core 4.14 | MPL-2.0 | tylko narzędzie deweloperskie; wystarczy Biome |
| Qt | LGPL-3.0 / GPL / komercyjna | `opencv-python` (nie-headless) dołącza Qt — brać tylko `-headless` |
| easyocr | Apache-2.0, ale ciągnie torch | zbędne |
| glibc w obrazie `slim` | LGPL-2.1 (linkowanie dynamiczne) | warstwa systemu; odnotować w README |

Każdy oficjalny obraz bazowy zawiera komponenty GPL na poziomie systemu (busybox w Alpine, coreutils i bash w Debianie). Zakaz organizatorów dotyczy bibliotek rozwiązania, więc bramka obejmuje zależności aplikacji, a warstwę systemu raportuje SBOM.

### Bramka licencyjna w CI

```sh
# Python: lista + twarda blokada
uv run pip-licenses --from=mixed --partial-match \
  --fail-on="GPL;AGPL;LGPL;MPL;EUPL;SSPL" \
  --format=markdown --output-file=THIRD_PARTY_LICENSES.md
# npm
npx license-checker-rseidelsohn --production \
  --onlyAllow "MIT;ISC;Apache-2.0;BSD-2-Clause;BSD-3-Clause;0BSD"
# SBOM + obraz (pakiety systemowe, podatności)
uv export --frozen --format cyclonedx1.5 -o sbom.cdx.json
trivy image --scanners vuln,license --severity HIGH,CRITICAL --exit-code 1 formdigitizer-api:ci
```

- `--partial-match` z wzorcem `GPL` łapie też licencje podwójne typu `Apache-2.0 OR GPL`; wyjątki dopisywać jawnie przez `--ignore-packages` z komentarzem.
- Akcje GitHub przypinać pełnym SHA. W marcu 2026 przejęto niemal wszystkie tagi `aquasecurity/trivy-action` (GHSA-69fq-xp46-6x23); najprościej uruchamiać Trivy z obrazu przypiętego digestem.
- `reuse` i `licensecheck` są zbędne przy tej skali.

## 4. Walidacja uploadu

Kolejność kontroli, każda z własnym kodem błędu (`application/problem+json`):

1. **Rozmiar** (`MAX_UPLOAD_MB`, domyślnie 20): odrzucenie po `Content-Length`, potem liczenie bajtów podczas odczytu (nagłówek może kłamać) → 413. `client_max_body_size` w nginx ustawić na tę samą wartość.
2. **Nazwa pliku:** normalizacja NFC, długość ≤ 250 znaków, wyrażenie `[;:><\/\\|'*%$\x00-\x1f]` → 400. Nazwa nigdy nie trafia do ścieżki na dysku.
3. **Rozszerzenie:** biała lista `pdf, doc, docx, ods, xlsx, jpg, jpeg, png`, bez rozróżniania wielkości liter.
4. **Zawartość kontra rozszerzenie** → 415 przy niezgodności:

| Sygnatura | Dalsza kontrola | Wynik |
|---|---|---|
| `%PDF-` w pierwszych 1024 bajtach | — | PDF |
| `89 50 4E 47 0D 0A 1A 0A` | — | PNG |
| `FF D8 FF` | — | JPEG |
| `50 4B 03 04` (ZIP) | wpis `mimetype` = `application/vnd.oasis.opendocument.spreadsheet` | ODS |
| ZIP | `[Content_Types].xml` z typem `…wordprocessingml.document.main+xml` | DOCX |
| ZIP | `[Content_Types].xml` z typem `…spreadsheetml.sheet.main+xml` | XLSX |
| `D0 CF 11 E0 A1 B1 1A E1` (OLE2) | `olefile`: strumień `WordDocument` | DOC |
| OLE2 | strumień `Workbook` / `Book` | XLS → odrzucić |

5. **Makra:** typ `macroEnabled` w `[Content_Types].xml`, wpis `vbaProject.bin` albo magazyn OLE `Macros` → odrzucić. Kod nigdy nie wykonuje zawartości dokumentu.
6. **Bomby dekompresyjne:**
   - ZIP: przed rozpakowaniem limit liczby wpisów (np. 2000), sumy `ZipInfo.file_size` (np. 200 MB) i współczynnika kompresji (np. 100); brak archiwów zagnieżdżonych.
   - XML: `defusedxml` albo `lxml` z `resolve_entities=False, no_network=True, huge_tree=False`.
   - Obrazy: jawny `Image.MAX_IMAGE_PIXELS` z konfiguracji. Próbki mają do 1654×37 424 px (61,9 MP); domyślny próg Pillow to 89,5 MP. Wysokości próbek są wielokrotnością 2339 px (A4 przy 200 DPI) — ciąć na strony przed OCR.
   - PDF: limit stron (`MAX_PAGES`), limit DPI renderowania, limit czasu na żądanie.
7. **Tylko RAM / temp:** plik jako `bytes` / `BytesIO`. Starlette przenosi części większe niż 1 MB do `SpooledTemporaryFile`, więc `TMPDIR=/tmp` musi być `tmpfs`. Sprzątanie w `finally`. W logach tylko SHA-256 i rozmiar.

Biblioteki: własna funkcja detekcji (około 40 linii, `zipfile` ze stdlib) + `olefile` (BSD-2-Clause) + `puremagic` 2.3.0 (MIT, czysty Python) jako druga opinia. `filetype` 1.2.0 jest porzucony (2022). `python-magic` wymaga `libmagic` w obrazie. Tika wykrywa typy najlepiej, ale kosztuje kontener JVM około 185 MB — uzasadniona tylko, gdy i tak obsługuje pliki DOC.

## 5. Parametry JWT

Biblioteka: `PyJWT[crypto]` 2.15.1. Konfiguracja wyłącznie przez zmienne środowiskowe (`pydantic-settings`):

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `AUTH_ENABLED` | `true` | `false` wyłącza weryfikację (demo); start loguje ostrzeżenie |
| `JWT_ALGORITHMS` | `RS256` | lista dozwolonych; nigdy `none`; bez mieszania HS i RS |
| `JWT_SECRET` / `JWT_SECRET_FILE` | — | HS256, co najmniej 32 bajty; wariant `_FILE` dla Docker secrets |
| `JWT_PUBLIC_KEY` | — | PEM dla RS256 / ES256, działa bez sieci |
| `JWT_JWKS_URL` | — | wewnętrzny IdP (np. Keycloak), `PyJWKClient` z cache |
| `JWT_ISSUER` | — | weryfikacja `iss` |
| `JWT_AUDIENCE` | — | weryfikacja `aud` |
| `JWT_LEEWAY_SECONDS` | `30` | tolerancja zegara |

Zasady: wymagane `exp`; przy `AUTH_ENABLED=true` bez klucza aplikacja nie startuje; `/health` bez tokenu; błędy jako 401 z `WWW-Authenticate: Bearer`. README zawiera jednolinijkowe polecenie generujące token testowy HS256.

## 6. Docker

### Alpine a wheele ML

Brak wheeli `musllinux` dla: `onnxruntime`, `torch`, `opencv-python-headless`, `docling-parse`, `pyclipper`. Wheele musl mają: `pydantic-core`, `numpy`, `Pillow`, `lxml`, `pypdfium2`, `python-calamine`, `cryptography`.

Alpine 3.24 ma systemowego Pythona 3.14.10 oraz pakiety `py3-onnxruntime` 1.24.4 i `py3-opencv` 4.12 (x86_64 i aarch64). Obraz ML w całości na Alpine jest więc możliwy, ale na starszym `onnxruntime`, z kompilacją `pyclipper` i bez `uv.lock` — za duże ryzyko na 24–48 h.

**Decyzja:** `api` na `python:3.14.10-slim-trixie` (43 MB wobec 18 MB dla Alpine; różnica znika przy wagach modeli), Alpine wszędzie tam, gdzie się da (`web`). README podaje to uzasadnienie wprost.

### Układ `compose.yaml`

| Usługa | Obraz | Rozmiar (skompresowany, arm64) | Porty | Uwagi |
|---|---|---|---|---|
| `web` | `nginxinc/nginx-unprivileged:1.30.6-alpine-slim` | 8 MB + statyki | `8080:8080` | UID 101; serwuje SPA i proxy `/api` |
| `api` | build z `python:3.14.10-slim-trixie` | szacunek 250–350 MB bez torch | brak publikacji | UID 10001 |
| `llm` | `ghcr.io/ggml-org/llama.cpp:server-v0.5.0@sha256:…` | 291 MB + wagi GGUF 2–5 GB w wolumenie | brak publikacji | `user: "10001"`, `--offline`, `-m /models/…` |
| `tika` (profil `legacy-doc`) | `apache/tika:4.2.0` | około 185 MB | brak publikacji | tylko dla DOC |

Odrzucone: `ollama/ollama:0.40.17` — 2,87 GB skompresowane, dziesięć razy więcej niż `llama.cpp server`.

Wspólne utwardzenie każdej usługi:

```yaml
read_only: true
tmpfs: ["/tmp:size=512m,noexec,nosuid"]
cap_drop: [ALL]
security_opt: ["no-new-privileges:true"]
pids_limit: 256
mem_limit: 2g        # llm: 8g, web: 64m
healthcheck: {test: ["CMD", "python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health')"], interval: 15s}
```

- **Sieć:** `backend` z `internal: true`. Kontenery `api` i `llm` nie mają wyjścia do internetu, co jest sprawdzalnym dowodem braku zewnętrznych API.
- **Multi-stage:** etap `builder` (`pip install uv==0.13.9`, `uv sync --frozen --no-dev`) → etap `runtime` kopiuje tylko `.venv` i kod; `USER 10001`; brak kompilatorów w obrazie końcowym. Frontend: `node:24-alpine3.24` buduje, nginx serwuje.
- **Wersje:** tagi pełne plus digest dla obrazów spoza Docker Hub. Schemat tagów llama.cpp jest w ruchu (wydanie `v1.0.0` na GitHubie, w GHCR `server-v0.5.0`), więc digest jest obowiązkowy.
- **Sekrety:** tylko w czasie uruchomienia (`env_file`, `JWT_SECRET_FILE`); `.env.example` w repo, `.env` w `.gitignore`.

### Wagi modeli w trybie offline

- **Modele OCR (ONNX, kilkadziesiąt MB):** pobierane w etapie `builder` z sumą SHA-256 i wypiekane w obrazie `api`. `rapidocr` domyślnie pobiera modele przy pierwszym użyciu — przy sieci `internal` to by się nie udało.
- **LLM (GGUF):** nazwany wolumen `models`, wypełniany raz przez `make models` (pobranie z przypiętą rewizją i SHA-256). Wypiekanie w obrazie dałoby wielogigabajtowy obraz i problem redystrybucji wag.
- **Demo na M4:** Docker Desktop nie przekazuje Metal do kontenerów, więc `llm` w kontenerze działa tylko na CPU. Plik `compose.metal.yaml` przełącza `LLM_BASE_URL` na natywny `llama-server` na hoście (`host.docker.internal`). Pamięć maszyny Docker Desktop podnieść do 10–12 GB.

## 7. Frontend

**Główny stos:** React 19.3.1 + Vite 8.3.8 + TypeScript 7.0.2 (MIT / MIT / Apache-2.0). **Zapasowy:** HTMX 2.0.11 (0BSD) + szablony po stronie FastAPI — upload i podgląd JSON bez renderera.

| Potrzeba | Wybór | Licencja | Uwaga |
|---|---|---|---|
| Warunki SHOW / READ_ONLY | `jsonata` 2.2.2 | MIT | `evaluate()` jest asynchroniczne; wyrażenia kompilować raz, przeliczać stany w handlerze zmiany wartości |
| Podgląd PDF + ramki | `pdfjs-dist` 6.5.438 | Apache-2.0 | render z lokalnego obiektu `File` — serwer niczego nie przechowuje; ramki jako pozycjonowane `div` nad `canvas` |
| Podgląd obrazów | `URL.createObjectURL` + `<img>` | — | wysokie obrazy ciąć na strony po 2339 px |
| JSON | `vanilla-jsoneditor` 3.13.1 | ISC | drzewo, tekst, wyszukiwanie; Monaco 0.57 (MIT) jest za ciężkie |
| Stan formularza | `useReducer` + mapa `id → wartość` | — | `react-hook-form` 7.92 (MIT) opcjonalnie |
| Walidatory | czyste funkcje TS (PESEL, NIP, REGON) | — | te same sumy kontrolne co w backendzie |
| Kontrolki | elementy natywne: `<input type="date">`, `<select>`, `<fieldset>` | — | `react-aria-components` 1.22 (Apache-2.0) tylko w razie potrzeby |
| Lint, format, a11y | `@biomejs/biome` 2.6.8 | MIT OR Apache-2.0 | zastępuje ESLint + Prettier |

**Siatka:** kontener `display: grid`; poniżej 640 px jedna kolumna (`grid-area: auto`). Pole:

```tsx
<div style={{ gridArea: `${y + 1} / ${x + 1} / span ${rows} / span ${cols}` }} />
```

**System projektowy gov.pl:**

- „Przewodnik Gov UI” (`aplikacje.gov.pl/app/govpl-front-styleguide`, właściciel merytoryczny KPRM, deklarowana zgodność z WCAG 2.1) istnieje, ale nie znalazłem pakietu npm ani licencji kodu.
- Kod design systemu mObywatela opublikowano 2025-12-29 na licencji MIT, lecz dostęp wymaga potwierdzenia tożsamości i dotyczy aplikacji mobilnej.
- `mdesign-react` (MIT) jest nieoficjalny.
- **Decyzja:** własny arkusz CSS z tokenami wzorowanymi na Przewodniku Gov UI, bez godła i logotypów. `govuk-frontend` 6.6.0 (MIT) jako wzorzec dostępnych komponentów.

**WCAG 2.1 AA — minimum:** `lang="pl"`; `label` powiązany z polem; `fieldset` + `legend` dla RADIO i CHECKBOX; błędy przez `aria-describedby` i `aria-invalid` oraz podsumowanie błędów z fokusem; widoczny fokus; kontrast 4,5:1; pełna obsługa z klawiatury. Pola ukryte przez SHOW usuwać z DOM. READ_ONLY jako `readOnly`, nie `disabled`.

## 8. Sygnały jakości kodu widoczne w 5 minut

- [ ] **Struktura:** `src/<pakiet>/{api,parsing,llm,schema,validation}`, `tests/`, `frontend/`, `compose.yaml`, `pyproject.toml`, `uv.lock`, `LICENSE`, `.env.example`.
- [ ] **Jedno źródło prawdy:** modele Pydantic konfiguracji e-formularza → JSON Schema → ograniczenie odpowiedzi LLM → OpenAPI.
- [ ] **Typowanie:** `mypy --strict` bez wyjątków poza granicami bibliotek.
- [ ] **Testy:** walidatory (PESEL, NIP, REGON), walidacja uploadu (tabela przypadków: zmienione rozszerzenie, makro, bomba ZIP, zła nazwa), jeden test „złoty” na próbce z zaślepionym LLM, test kontraktu API przez `TestClient`.
- [ ] **CI (jeden workflow):** `ruff check`, `ruff format --check`, `mypy`, `pytest`, bramka licencyjna, `docker build`, `trivy`. Akcje przypięte SHA.
- [ ] **pre-commit:** `ruff`, `ruff-format`, `detect-private-key`, `check-yaml`.
- [ ] **OpenAPI:** `/docs` z modelami odpowiedzi, przykładami i modelem błędu `problem+json`.
- [ ] **README:** opis i diagram, budowanie Dockera, uruchomienie, tabela zmiennych konfiguracyjnych, REST API z przykładami `curl`, licencje zależności i modeli, ograniczenia.
- [ ] **Higiena:** brak sekretów w repo, wersje przypięte, logi bez treści dokumentów.

Pominąć: warstwy DDD, kontenery DI, manifesty Kubernetes, podział na mikroserwisy, pogoń za 100% pokrycia.

## Źródła

- PyPI JSON API, np. https://pypi.org/pypi/onnxruntime/json, https://pypi.org/pypi/paddlepaddle/json, https://pypi.org/pypi/fastapi/json, https://pypi.org/pypi/orjson/json, https://pypi.org/pypi/odfpy/json, https://pypi.org/pypi/unidecode/json, https://pypi.org/pypi/pymupdf/json, https://pypi.org/pypi/mineru/json (analogicznie dla pozostałych pakietów z tabel)
- npm registry: https://registry.npmjs.org/jsonata/latest, https://registry.npmjs.org/pdfjs-dist/latest, https://registry.npmjs.org/vanilla-jsoneditor/latest, https://registry.npmjs.org/axe-core/latest (analogicznie dla pozostałych)
- Maven Central: https://repo1.maven.org/maven2/org/springframework/boot/spring-boot/maven-metadata.xml, https://repo1.maven.org/maven2/org/apache/tika/tika-core/maven-metadata.xml, https://repo1.maven.org/maven2/com/dashjoin/jsonata/maven-metadata.xml
- Spring Boot 3.5 — koniec wsparcia OSS: https://spring.io/blog/2026/06/25/spring-boot-3-5-16-available-now/
- Docker Hub: https://hub.docker.com/_/python, https://hub.docker.com/r/nginxinc/nginx-unprivileged, https://hub.docker.com/r/ollama/ollama, https://hub.docker.com/r/apache/tika, https://hub.docker.com/_/eclipse-temurin
- llama.cpp Docker: https://raw.githubusercontent.com/ggml-org/llama.cpp/HEAD/docs/docker.md, https://github.com/ggml-org/llama.cpp/releases
- Alpine: https://pkgs.alpinelinux.org/packages?name=py3-onnxruntime&branch=v3.24, https://pkgs.alpinelinux.org/packages?name=python3&branch=v3.24
- Free-threaded: https://dev-discuss.pytorch.org/t/dropping-python-3-13t-free-threaded-support-in-nightlies-and-in-the-future-pytorch-2-13-release/3386
- Surya / Marker: https://raw.githubusercontent.com/datalab-to/surya/HEAD/MODEL_LICENSE, https://github.com/datalab-to/marker/releases, https://particula.tech/blog/docling-vs-mineru-vs-marker-pdf-parser
- MinerU: https://raw.githubusercontent.com/opendatalab/MinerU/HEAD/LICENSE.md
- chardet: https://lwn.net/Articles/1061534/, https://simonwillison.net/2026/mar/5/chardet, https://heathermeeker.com/tag/lgpl/
- odfpy: https://sources.debian.org/src/python-odf/1.4.2-4/debian/copyright
- libmagic: https://raw.githubusercontent.com/file/file/HEAD/COPYING; python-magic: https://raw.githubusercontent.com/ahupp/python-magic/master/README.md
- pip-licenses: https://github.com/raimon49/pip-licenses; Trivy — licencje: https://github.com/aquasecurity/trivy/blob/main/docs/guide/scanner/license.md
- Incydent Trivy: https://github.com/aquasecurity/trivy/security/advisories/GHSA-69fq-xp46-6x23
- uv SBOM: https://docs.astral.sh/uv/concepts/projects/export/
- Starlette (limity formularza): https://raw.githubusercontent.com/Kludex/starlette/HEAD/starlette/requests.py
- Pillow `MAX_IMAGE_PIXELS`: https://raw.githubusercontent.com/python-pillow/Pillow/HEAD/src/PIL/Image.py
- Docker i Metal: https://www.docker.com/blog/docker-model-runner-vllm-metal-macos/, https://docs.docker.com/ai/model-runner/
- Gov UI: https://aplikacje.gov.pl/app/govpl-front-styleguide/
- mObywatel: https://www.mobywatel.gov.pl/kod-zrodlowy-mobywatel-mobilny, https://www.telepolis.pl/tech/aplikacje/ministerstwo-cyfryzacji-opublikowalo-kod-zrodlowy-mobywatela, https://github.com/slominskiwiktor/mdesign-react
- JSONata: https://github.com/jsonata-js/jsonata

## Czego nie udało się zweryfikować

- **Działania na Pythonie 3.14:** sprawdzone są wyłącznie metadane i wheele. `python-docx`, `openpyxl`, `pytesseract`, `olefile`, `defusedxml` to stare wydania czysto pythonowe — potrzebny test dymny w kontenerze.
- **Rozmiaru obrazu `api`:** 250–350 MB to szacunek, nie pomiar. Rozmiary pozostałych obrazów to rozmiary skompresowane z rejestrów.
- **Tagów llama.cpp:** GitHub wskazuje wydanie `v1.0.0`, GHCR ma `server-v0.5.0`, a tagi `server-bNNNN` dla najnowszych buildów zwracają 404. Obraz `apache/tika:4.2.0` (bez `-full`) nie był widoczny wprost na liście tagów — rozmiar pochodzi z tagu `latest`.
- **Użytkownika w obrazie llama.cpp:** nie potwierdziłem, czy domyślnie działa jako non-root; stąd jawne `user:` w compose.
- **Licencji i pakietu Przewodnika Gov UI:** strona jest aplikacją SPA bez widocznej informacji o licencji. Oficjalnej strony z kodem mObywatela nie otworzyłem (wymaga logowania); licencja MIT pochodzi z relacji prasowych.
- **Progów w licencji wag Surya** (5 mln USD): tylko źródło wtórne. Tekst `MODEL_LICENSE` potwierdza jedynie typ licencji.
- **Licencji wag modeli** docling, PP-OCR i wybranego LLM — poza zakresem tego raportu; bramka licencyjna powinna je objąć ręcznie.
- **Licencji części repozytoriów przez GitHub API** (limit zapytań): użyłem plików `LICENSE` i metadanych rejestrów. Licencje Spring, POI, PDFBox i LangChain4j (Apache-2.0) oraz nginx (BSD-2-Clause) podaję z wiedzy ogólnej, bez dzisiejszego potwierdzenia.
- **Nowej składni limitów uploadu w Starlette 1.x** poza `max_files`, `max_fields`, `max_part_size` (1 MB) widocznymi w kodzie.
