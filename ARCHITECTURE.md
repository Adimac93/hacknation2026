# Architektura: Kompilator Formularzy

Stan: projekt przed implementacją (2026-11-21). Nazwa robocza, pakiet Pythona `formcompiler`.
Źródła decyzji: raporty w [`research/`](research/), materiały organizatora w `Docs/`.

## 1. Teza

Zadanie nie polega na przepisaniu blankietu. Wynik ma wyglądać jak formularz zaprojektowany przez analityka COI: strony tematyczne, sekcje predefiniowane („Twoje dane”, „Adres”, „Podmiot wniosku”), słowniki, dane z rejestrów, warunki widoczności.

Dlatego budujemy **kompilator, a nie OCR**:

1. Parser wyciąga z pliku tekst z układem.
2. Reguły i lokalny model LLM **rozumieją** blankiet i zwracają krótką reprezentację pośrednią (IR).
3. Kod deterministyczny **składa** końcowy JSON z biblioteki sekcji predefiniowanych.
4. Linter sprawdza wszystkie reguły techniczne i naprawia naruszenia.

Model nigdy nie pisze końcowego JSON-a. Dzięki temu plik zawsze przechodzi reguły techniczne, a czas odpowiedzi mieści się w minutach na laptopie bez karty graficznej.

## 2. Rozważone podejścia

| Podejście | Zalety | Wady | Decyzja |
|---|---|---|---|
| A. Model generuje cały JSON jednym wywołaniem | najmniej kodu | ok. 15 tys. tokenów wyjścia, czyli ponad 16 min na M4; model myli identyfikatory i odwołania w JSONata | odrzucone |
| B. Same reguły i szablony, bez modelu | szybkie, powtarzalne, zawsze poprawne | słabe na nietypowych blankietach, nie upraszcza języka | zostaje jako tryb awaryjny |
| C. Reguły + IR z modelu + kompilator + linter | poprawność z kodu, rozumienie z modelu, awaria modelu nie psuje wyniku | więcej modułów | **wybrane** |
| D. Model wizyjny czyta obrazy stron | radzi sobie ze zdjęciami | drugi duży model nie mieści się w 16 GB obok LLM, wolne | poza MVP, opcja konfiguracyjna |

## 3. Wymagania twarde i sposób ich spełnienia

| Wymaganie organizatora | Realizacja |
|---|---|
| Python 3.14+ lub Java 21+ | API w Pythonie 3.14; sidecar Apache Tika na Javie 25 tylko do plików biurowych |
| Tylko open source bez copyleft | lista dozwolonych zależności w `CLAUDE.md`, bramka licencyjna w CI |
| Brak zewnętrznych API, SaaS, MCP; brak modeli dostępnych tylko przez API | model open-weight uruchamiany lokalnie; sieć `backend` w compose ma `internal: true` |
| REST API przyjmujące jeden plik | `POST /api/v1/forms` |
| Formaty PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG | patrz sekcja 5.1 |
| Weryfikacja MIME, nazwy i rozmiaru pliku | patrz sekcja 9 |
| Plik tylko w RAM lub w przestrzeni tymczasowej żądania | brak bazy i brak zapisu na dysk; `/tmp` to `tmpfs` |
| Docker: oficjalne obrazy, lekkie dystrybucje, przypięte wersje, non-root, minimum portów, sekrety w runtime | patrz sekcja 10 |
| Konfiguracja: rozmiar pliku, JWT, parametry integracyjne | zmienne środowiskowe, sekcja 8.3 |
| README: budowanie, uruchomienie, konfiguracja, REST API | `README.md` uzupełniany razem z kodem |

## 4. Widok ogólny

```mermaid
flowchart LR
  U[Urzędnik] -->|przeglądarka| WEB[web: nginx + SPA React]
  WEB -->|/api| API[api: FastAPI, Python 3.14]
  API -->|DOC DOCX ODS XLSX| TIKA[tika: Apache Tika Server]
  API -->|OpenAI-compatible, LLM_BASE_URL| LLM[llm: llama-server + GGUF]
  subgraph backend [sieć backend, internal: true]
    API
    TIKA
    LLM
  end
```

Publikowany jest tylko port `web` (8080). Kontenery `api`, `tika` i `llm` nie mają wyjścia do internetu.

## 5. Potok przetwarzania

```mermaid
flowchart TD
  F[plik] --> V[1. walidacja uploadu]
  V --> I[2. ingest: tekst + układ]
  I --> H[3. heurystyki: kandydaci na pola]
  H --> L[4. LLM: IR w 3 krokach]
  H -.->|model niedostępny lub przekroczony czas| C
  L --> C[5. kompilator: IR do JSON]
  C --> N[6. linter + auto-naprawa]
  N --> R[odpowiedź: JSON formularza]
```

### 5.1 Ingest

Każdy format trafia do jednego modelu `Document`: lista stron, na każdej linie tekstu z identyfikatorem (`L17`), współrzędnymi i znacznikami układu. Identyfikatory linii służą później do pokazania w interfejsie, skąd wzięło się pole.

| Wejście | Narzędzie | Uwagi |
|---|---|---|
| PDF z warstwą tekstową | `pdfplumber` (tekst, linie, prostokąty), `pypdfium2` (render strony) | pola wyboru to często grafika wektorowa albo glif Wingdings; wykrywamy je z prostokątów i nazwy fontu, bo sam tekst ich nie zawiera |
| PDF bez warstwy tekstowej, JPG, JPEG, PNG | cięcie na strony, prostowanie, potem RapidOCR (`rapidocr` + `onnxruntime`, modele PP-OCRv6 small) z `use_cls=false` | zmierzone na M4: CER 1,2–4,2%, 1,0–1,8 s na stronę; z domyślnym klasyfikatorem orientacji CER rośnie do 16% |
| DOC, DOCX, ODS, XLSX | Apache Tika Server 3.3.2, wynik XHTML | jeden adapter dla czterech formatów; tabele zachowane |

Zasada: **warstwa natywna zawsze, OCR tylko dla rastra.** Parser natywny działa w milisekundach, nie myli znaków i zachowuje kratki, wykropkowania i tabele. OCR gubi wszystkie wykropkowania i 62–100% kratek, więc dla rastrów heurystyki opierają się na samym tekście (etykieta z dwukropkiem, lista krótkich pozycji), a resztę rozstrzyga model.

Pułapki zmierzone na próbkach:

- Tika zamienia kratki zrobione jako punktory listy (`numbering.xml`) na znak `·`. Krótka lista punktowana jest więc kandydatem na opcje wyboru.
- W PDF kratki to glify fontów symbolicznych (Wingdings U+F0F0, U+F071, U+2751, U+25A1) albo prostokąty wektorowe. Wykrywamy je po nazwie fontu i geometrii.
- Żaden z dziewięciu przykładowych PDF nie ma pól AcroForm.

Bardzo wysokie obrazy (próbki mają do 1654×37 424 px, wysokość to wielokrotność 2339 px, czyli A4 przy 200 DPI) tniemy na strony przed OCR. Bez cięcia RapidOCR daje CER 99,9%, a Tesseract odrzuca plik. Gdy wysokość nie jest wielokrotnością strony, tniemy w najszerszym poziomym pasie bez tuszu w zakresie ±15% wysokości strony, a gdy takiego pasa nie ma (zdjęcie), tniemy z zakładką i usuwamy zduplikowane linie.

Po ingest dokument jest linearyzowany do tekstu z prostymi znacznikami: `[ ]` pole wyboru, `____` miejsce do wpisania, `|` komórki tabeli, `#` nagłówek, `--- strona N ---`.

### 5.2 Heurystyki (tryb „reguły najpierw”)

Deterministyczne wykrywanie kandydatów na pola. Działa bez modelu i jest jednocześnie ścieżką awaryjną.

- etykieta przed kropkami lub podpis pod linią (`/ PESEL /`) → pole tekstowe,
- lista pól wyboru → `RADIO` (wykluczające się) albo `CHECKBOX`; powyżej 5 opcji `SELECT`, powyżej 15 z wyszukiwarką,
- słowa kluczowe → walidatory i typy: PESEL, NIP, REGON, e-mail, kod pocztowy, ePUAP, e-Doręczenia, seria i numer dowodu, „data” → `DATEPICKER`, „załącznik”, „dołącz” → `FILE_UPLOADER`,
- kilka pustych linii pod pytaniem → `TEXTAREA`,
- „oświadczam”, „wyrażam zgodę” → `CONSENT_SECTION`,
- „podpis”, „miejscowość, dnia”, „pieczęć”, „wypełnia organ” → pomijane (formularz elektroniczny tego nie zbiera),
- pouczenia i informacje → `TEXT_BLOCK` albo opis sekcji,
- dane osobowe i adresowe wnioskodawcy → oznaczone jako pokryte przez sekcje predefiniowane.

### 5.3 LLM: trzy krótkie wywołania

Wejście modelu to zlinearyzowany tekst i lista kandydatów z heurystyk. Wyjście to IR, po jednej krótkiej pozycji na pole.

| Krok | Zadanie modelu | Wyjście |
|---|---|---|
| A. Inwentarz | potwierdzić lub poprawić kandydatów, nadać etykiety prostym językiem, typ, wymagalność, walidatory, opcje; ustalić tytuł, adresata i kto może złożyć wniosek | płaska lista pól |
| B. Struktura | przypisać pola do sekcji predefiniowanych albo nowych sekcji tematycznych, ułożyć strony, wskazać sekcje powtarzalne | drzewo strony → sekcje → klucze pól |
| C. Zależności | wskazać warunki widoczności między polami i sekcjami, zaproponować słowniki | lista trójek warunków, lista słowników |

Zasady:

- schematy odpowiedzi są płaskie, z enumami, bez `$ref`; wymuszamy je przez `response_format: json_schema` w `llama-server`,
- `temperature` 0, stałe ziarno, jawny `max_tokens` i limit czasu na krok,
- statyczny początek promptu (instrukcje, standardy COI, przykłady) jest identyczny między wywołaniami, żeby zadziałał cache promptu,
- długie formularze dzielimy na bloki stron w kroku A,
- przykłady few-shot powstają z dwóch referencyjnych JSON-ów zdekompilowanych do IR,
- błąd, limit czasu albo niepoprawna odpowiedź w dowolnym kroku: jedno ponowienie, potem wynik z heurystyk. Odpowiedź API zawsze jest poprawnym formularzem.

### 5.4 Reprezentacja pośrednia (IR)

```text
FormIR
  title            tytuł zaczynający się od Wniosek / Zgłoszenie / Deklaracja / Oświadczenie
  addressee        nazwa urzędu lub organu + rodzaj (URZAD | ORGAN)
  applicant        persons: bool, entities: bool, proxy: bool
  pages[]          title, sections[]
SectionIR
  ref              identyfikator szablonu z biblioteki albo brak (sekcja własna)
  title, description, repeating: bool, show_if: Cond?
  fields[]
FieldIR
  key              slug, z niego powstaje techName
  label, description, type (11 typów komponentów)
  required, validators[], options[], dictionary?, initial? (np. MLPZ.email)
  show_if: Cond?, read_only_if: Cond?
  src[]            identyfikatory linii źródłowych
  confidence       0..1
Cond
  all | any        lista warunków prostych
  prosty warunek   field: key, op: IN | NOT_IN, value
```

IR jest modelem Pydantic. Ten sam model waliduje odpowiedź LLM i jest wejściem kompilatora.

### 5.5 Biblioteka sekcji predefiniowanych

Szablony odtwarzają sekcje ze „Standardów i dobrych praktyk” oraz z dwóch referencyjnych JSON-ów: adresat (urząd albo organ), „Podmiot wniosku”, „Twoje dane”, adres (zamieszkania, zameldowania, siedziby, korespondencyjny), „Dane innej osoby” z adresem, „Dane podmiotu” z adresem siedziby, potwierdzenie reprezentanta, „Pełnomocnictwo”, „Opłata skarbowa” w dwóch wersjach, „Dane do kontaktu”, zgody i oświadczenia, podsumowanie, podgląd.

Każdy szablon niesie gotowe pola, walidatory, słowniki (`Kraje`, TERYT), dane inicjalne (`MLPZ.*`, `PESEL.*`) i warunki `SHOW`. Flagi `applicant` z IR decydują, które sekcje i opcje się pojawią. To daje większość z ok. 30 warunków `SHOW` z referencji bez udziału modelu.

Układ stron jest stały:

1. „Dane”: adresat, podmiot wniosku, dane i adresy stron, pełnomocnictwo, opłata skarbowa.
2. Jedna lub więcej stron przedmiotu wniosku (ustala model).
3. „Kontakt i zgody”: dane do kontaktu, załączniki ogólne, oświadczenia.
4. Strona końcowa (`FINISH`): podsumowanie i podgląd, bez pól wejściowych.

### 5.6 Kompilator: kontrakt wyjścia

Ustalenia z referencyjnych JSON-ów (to one są wzorcem importu, nie plik schematu):

| Element | Reguła |
|---|---|
| Korzeń | `title`, `tabs[]`, `flow.links[]` |
| Strona | `id` (UUID), `title`, `type` (`MAIN` albo `FINISH`), `questions[]` |
| Sekcja | wpis w `questions`: `x: 0`, `cols: 3`, `y` narastająco, `rows` = liczba pól + 1; `field.type` = `SECTION` albo `REPEATING_SECTION` |
| Pola sekcji | w `field.repeatingSectionGrid[]` (w referencjach tak, w pliku schematu literówka `repetingSectionGrid`); `x: 0`, `cols: 3`, `rows: 1`, `y` = kolejność |
| Każde pole | `id`, `type`, `techName`, `title`, `description`, `options`, `validation`, `readOnly`, `repeatingSectionGrid`, `states`, `questionOrder`, `tooltipMessage` |
| `techName` | slug ASCII z podkreślnikami, unikalny w całym formularzu |
| `description` | HTML: `<html><head></head><body><p>…</p></body></html>` |
| Opcje | `id` = `name` = tekst opcji, `techName` = slug |
| `SELECT` | dodatkowo `dictionaryName`, `multiLevelTree`, `searchEnabled`, `defaultValue` jako lista |
| Dane inicjalne | `defaultValue: "MLPZ.name"`, `defaultValueType: "EXTERNAL_SYSTEM"`; dane z rejestru PESEL zawsze `readOnly: true` |
| Sekcja zgód | `consentSectionConfig.consents[]` z `description` (HTML) i `required`, oraz `files[]` |
| Warunek | `states: [{type: "SHOW", query}]`, zapytanie według szablonu poniżej |
| Przepływ | `flow.links[]`: `id`, `source`, `target`; łańcuch przez wszystkie strony po kolei |
| Identyfikatory | UUID wersji 5 liczony z `techName`, więc ten sam plik daje ten sam JSON |

Szablon JSONata, składany wyłącznie przez kod:

```text
("<wartość>" in tabs['<tytuł strony>' in title].questions['<techName sekcji>' in field.techName].field.repeatingSectionGrid['<techName pola>' in field.techName].field.__userAnswer)
```

Negacja to `$not(...)`, łączenie przez `and` i `or`. Tytuły stron muszą być unikalne, bo warunek odwołuje się do strony przez tytuł.

Walidatory zapisujemy jako listę nazw, np. `["REQUIRED", "PESEL"]`. W referencjach `validation` jest wszędzie puste, więc format wymaga potwierdzenia u mentorów (sekcja 14).

### 5.7 Linter i auto-naprawa

Reguły pochodzą z „Reguł technicznych konfiguracji formularzy”. Każda ma kod, komunikat i, gdzie to możliwe, naprawę.

- tytuł niepusty, najwyżej 255 znaków,
- co najmniej dwie strony; dokładnie jedna `FINISH` i jest ostatnia; pozostałe `MAIN`,
- każda strona ma co najmniej jedno pole,
- każde pole leży w sekcji albo sekcji powtarzalnej; brak sekcji w sekcji,
- strona `FINISH` nie zawiera pól wejściowych,
- typ komponentu z listy 11 dozwolonych; walidator z listy 9 dozwolonych i pasujący do typu pola,
- słownik tylko w `SELECT`, `RADIO`, `CHECKBOX`; przy słowniku pusta lista opcji,
- pole zasilane z rejestru jest `readOnly` i ma jedno źródło z listy atrybutów (`PESEL`, `PESEL_ADDRESS`, `MLPZ`),
- unikalne `id` i `techName`,
- każde zapytanie JSONata się parsuje i wskazuje istniejącą stronę, sekcję i pole oraz istniejącą wartość opcji,
- `flow.links` łączy wszystkie strony w jedną ścieżkę do `FINISH`,
- zgodność ze schematem JSON organizatora.

Druga grupa to ostrzeżenia jakościowe ze standardów COI (nie blokują): etykiety prostym językiem (słowa powyżej 4 sylab, formy bezosobowe, „dokonać”, „posiadać”, imiesłowy na „-ąc”), zgody tylko w sekcji zgód, lista powyżej 15 opcji ma wyszukiwarkę.

## 6. Model LLM i runtime

| Element | Wybór | Zapas |
|---|---|---|
| Model | `Bielik-11B-v3.1-Instruct`, GGUF Q4_K_M, 6,72 GB, Apache-2.0, kontekst 32K | `Bielik-Minitron-7B-v3.0-Instruct` (szybszy), `gemma-4-12b-it` (multimodalny, Apache-2.0) |
| Serwer | `llama-server` (llama.cpp, MIT), endpoint zgodny z OpenAI | Ollama |
| Klient | `httpx` + modele Pydantic | — |

Model jest wymienny przez `LLM_BASE_URL` i `LLM_MODEL`. PLLuM-12B-instruct-2512 (Apache-2.0) da się podpiąć jako profil.

Profile uruchomienia:

- **domyślny**: wszystko w kontenerach, CPU, bez sieci zewnętrznej. Działa wszędzie, jest wolny (szacunkowo 3–5 tok/s na M4).
- **demo na Macu** (`compose.metal.yaml`): `llm` działa natywnie na hoście z Metal, `LLM_BASE_URL=http://host.docker.internal:8080/v1`. Docker na macOS nie udostępnia kontenerom GPU.
- **produkcja**: ten sam kontener w wariancie CUDA albo vLLM na serwerze z kartą 16 GB.

Wszystkie liczby tok/s w raportach to szacunki. Pierwszy krok implementacji to pomiar `llama-bench` na docelowym laptopie i wybór modelu na podstawie wyniku.

## 7. Słowniki, dane inicjalne, nowe słowniki

- Dopasowanie pól do słowników (`Kraje`, TERYT, numery kierunkowe) i do atrybutów rejestrów robi kod na podstawie sekcji predefiniowanej i słów kluczowych; model może tylko wskazać kandydata z enuma.
- Nowy słownik proponujemy, gdy lista ma wiele opcji albo powtarza się między formularzami (np. dyscypliny sportowe, rodzaj nieruchomości). Propozycja zawiera nazwę, strukturę, pozycje i listę pól, które by go używały.
- Propozycja trafia do raportu, a w JSON-ie formularza pole zachowuje opcje wpisane wprost. Dzięki temu plik importuje się także bez nowego słownika.

## 8. API

### 8.1 Endpointy

| Metoda i ścieżka | Opis |
|---|---|
| `POST /api/v1/forms` | `multipart/form-data`, pole `file`. Odpowiedź 200: czysty JSON konfiguracji formularza, gotowy do importu |
| `POST /api/v1/forms?details=true` | odpowiedź `{form, report}`; `report` zawiera pochodzenie pól (linie i ramki), pewność, wynik lintera, propozycje słowników, czasy etapów, nazwę modelu i tryb (LLM albo reguły) |
| `GET /health` | stan usługi i dostępność modelu, bez tokenu |
| `GET /docs` | OpenAPI |

Przetwarzanie jest synchroniczne i bezstanowe. Tryb wsadowy realizuje frontend, wysyłając pliki po kolei.

### 8.2 Błędy

Format `application/problem+json`. Kody: 400 zła nazwa pliku, 401 brak lub zły token, 413 za duży plik, 415 nieobsługiwany typ albo treść niezgodna z rozszerzeniem, 422 dokument nieczytelny, 504 przekroczony limit czasu.

### 8.3 Konfiguracja (zmienne środowiskowe)

| Zmienna | Znaczenie |
|---|---|
| `MAX_UPLOAD_MB` | maksymalny rozmiar pliku |
| `MAX_PAGES` | limit stron dokumentu |
| `AUTH_ENABLED`, `JWT_ALGORITHMS`, `JWT_SECRET` lub `JWT_SECRET_FILE`, `JWT_PUBLIC_KEY`, `JWT_JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE` | uwierzytelnianie JWT |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT_S` | serwer modelu |
| `LLM_ENABLED` | `false` wymusza tryb reguł |
| `TIKA_URL` | adres sidecara Tika |
| `REQUEST_TIMEOUT_S` | budżet czasu na żądanie |

## 9. Walidacja uploadu i bezpieczeństwo

Kolejność: rozmiar (nagłówek, potem licznik bajtów) → nazwa (NFC, do 250 znaków, bez `; : > < / \ | ' * % $`) → rozszerzenie z białej listy → zgodność treści z rozszerzeniem.

Zgodność treści: sygnatury PDF, PNG, JPEG; kontenery ZIP rozróżniamy po zawartości (`mimetype` dla ODS, `[Content_Types].xml` dla DOCX i XLSX); OLE2 po strumieniu `WordDocument` (DOC). Odrzucamy pliki z makrami.

Rozszerzenia `.doc` i `.docx` traktujemy jako jedną rodzinę „dokument Word”, tak jak grupuje je treść zadania („DOC (.doc .docx)”). Powód: dwie próbki organizatora (`5. …/*.DOC`, `7. …/*.DOC`) mają rozszerzenie `.DOC`, a w środku OOXML. Plik `.doc` z treścią DOCX przyjmujemy, plik `.doc` z treścią arkusza albo PDF odrzucamy. Format do przetwarzania wybieramy zawsze po sygnaturze, nigdy po rozszerzeniu. Limity chronią przed bombami dekompresyjnymi (liczba wpisów ZIP, rozmiar po rozpakowaniu, liczba pikseli obrazu, liczba stron).

Nazwa pliku nigdy nie staje się ścieżką. W logach jest tylko skrót SHA-256 i rozmiar, bez treści dokumentu. Aplikacja odrzuca `LLM_BASE_URL` spoza pętli zwrotnej i sieci prywatnych, chyba że ustawiono jawną flagę.

## 10. Docker

| Usługa | Obraz bazowy | Uwagi |
|---|---|---|
| `web` | `nginxinc/nginx-unprivileged`, wariant alpine-slim | jedyny publikowany port (8080); SPA i proxy `/api` |
| `api` | `python:3.14-slim-trixie` | `onnxruntime` nie ma kół dla musl, więc tu nie Alpine; uzasadnienie w README |
| `llm` | `ghcr.io/ggml-org/llama.cpp`, wariant `server`, przypięty digest | `user:` ustawiony w compose, model w wolumenie tylko do odczytu |
| `tika` | `eclipse-temurin` 25 JRE na Alpine + przypięty `tika-server` z sumą SHA-256 | własny krótki Dockerfile, non-root, limit pamięci JVM |

Wspólne: budowanie wieloetapowe, przypięte wersje (bez `latest`), dedykowany użytkownik, `read_only: true`, `tmpfs` na `/tmp`, `cap_drop: [ALL]`, `no-new-privileges`, limity pamięci, healthcheck. Wagi OCR są wypiekane w obrazie `api`. Wagi LLM pobiera raz `make models` do nazwanego wolumenu.

## 11. Frontend

React 19 + Vite + TypeScript. Jeden ekran z trzema panelami:

1. **Dokument źródłowy** (`pdfjs-dist` albo obraz) z ramką podświetlającą źródło wybranego pola.
2. **Podgląd e-formularza**: renderer konfiguracji z siatką CSS `grid-area: {y+1} / {x+1} / span {rows} / span {cols}`, warunki `SHOW` i `READ_ONLY` liczone na żywo biblioteką `jsonata`, walidatory (PESEL, NIP, REGON, kod pocztowy, e-mail) jako czyste funkcje.
3. **JSON i raport**: drzewo JSON, wynik lintera, lista pól „do sprawdzenia” (niska pewność), propozycje słowników, przycisk pobrania.

Do tego kolejka wielu plików (tryb wsadowy) i widok postępu etapów. Wygląd wzorowany na wizualizacjach z materiałów zadania, własny arkusz CSS, bez godła i logotypów. Minimum WCAG 2.1 AA: etykiety powiązane z polami, `fieldset` i `legend`, widoczny fokus, obsługa z klawiatury, kontrast 4,5:1.

## 12. Ewaluacja

- **Test odwracalności**: `build(decompile(ref))` daje referencyjny JSON z dokładnością do identyfikatorów. To test kompilatora i źródło przykładów few-shot.
- **Metryki względem dwóch referencji**: pokrycie pól, zgodność typów, zgodność sekcji i stron, liczba i trafność warunków `SHOW`, zgodność słowników i danych inicjalnych.
- **Spójność między formatami**: ten sam formularz w ośmiu formatach powinien dać ten sam JSON.
- **Odporność**: próbki zdegradowane (obrót, rozmycie, kompresja JPEG, cień) jako namiastka skanów i zdjęć.
- **Czas**: pomiar każdego etapu dla wszystkich dziewięciu formularzy.

Wyniki trafiają na slajd i do README.

## 13. Decyzje

| Nr | Decyzja | Powód |
|---|---|---|
| D1 | Python 3.14, FastAPI, Pydantic 2, `uv` | preferencja organizatora, ekosystem parserów i OCR, jeden model danych dla IR, walidacji i OpenAPI |
| D2 | Model nie pisze końcowego JSON-a | czas generacji i spójność odwołań |
| D3 | Bielik 11B v3.1 jako model domyślny | Apache-2.0, polski model, najlepsze dostępne wyniki dla polszczyzny w tej klasie rozmiaru, mieści się w 16 GB |
| D4 | `llama-server` za `LLM_BASE_URL` | obraz 291 MB wobec 2,87 GB dla Ollamy, wymuszanie schematu, wymienny model |
| D5 | OCR rastrów: RapidOCR 3.10 + ONNX Runtime, modele PP-OCRv6 small, `use_cls=false`. Zapas: Tesseract 5 `pol` | Apache-2.0 i MIT, bez PyTorch, działa na Pythonie 3.14; w pomiarze 2–10 razy mniejszy CER niż Tesseract na czystych stronach. PaddleOCR odpada, bo `paddlepaddle` nie ma kół dla 3.14. Tesseract lepiej trzyma diakrytyki na słabych skanach, dlatego zostaje jako zapas |
| D6 | Tika dla DOC, DOCX, ODS, XLSX | Apache-2.0, jedyna utrzymywana droga dla binarnego DOC bez copyleft, jeden adapter na cztery formaty. Jeśli harness pokaże straty na DOCX lub arkuszach, przechodzimy na `python-docx` i `python-calamine`, a Tika zostaje tylko dla DOC |
| D7 | `pdfplumber` + `pypdfium2` dla PDF | MIT i Apache/BSD; PyMuPDF jest na AGPL |
| D8 | API synchroniczne i bezstanowe | wymóg przetwarzania tylko w pamięci, mniej kodu |
| D9 | Propozycje słowników i pochodzenie pól poza JSON-em formularza | czysty plik do importu |
| D10 | `api` na obrazie slim, nie Alpine | brak kół musl dla `onnxruntime` |

## 14. Otwarte pytania do mentorów COI

1. Format `validation`: lista nazw (`["REQUIRED", "PESEL"]`)? W referencjach jest pusta.
2. Klucz `repeatingSectionGrid` (referencje) czy `repetingSectionGrid` (schemat)?
3. Strona `FINISH`: `SECTION` z `TEXT_BLOCK` jak w referencjach, czy `INFO_SECTION` jak w regułach?
4. Dokładne wartości `dictionaryName` (`Kraje`, `TERYT_4G_DOWODOWY`, `TERYT_DOWODOWY`, numery kierunkowe) i znaczenie `multiLevelTree`.
5. Jak zapisać w JSON-ie propozycję nowego słownika?
6. Czy `flow.links` obsługuje strony alternatywne (przejście warunkowe)? Schemat ma tylko `source` i `target`.
7. Przykład `REPEATING_SECTION`, `CHECKBOX`, `DATEPICKER`, `INFO_SECTION` w JSON-ie.
8. Kryteria oceny wymieniają „Punkt V (Walidacje pól)”, a w treści zadania walidacje to punkt VI. Co liczy się do progów?
9. Czy mentor może zaimportować nasz JSON do Generatora Formularzy i powiedzieć, co nie przeszło?
10. Czy serwer modelu jako osobny kontener z lokalnym endpointem jest zgodny z zakazem zewnętrznych API? Czy na obronie model może działać natywnie na hoście (Metal)?
11. Czy `python:3.14-slim` zamiast Alpine jest akceptowalny dla usługi z bibliotekami ML? Czy sidecar Tika na Javie jest w porządku?
12. Sprzęt i limit czasu na obronie; czy nowe pliki będą skanami lub zdjęciami?
13. Próbki `5. …/*.DOC` i `7. …/*.DOC` mają w środku format DOCX. Czy walidacja ma taki plik przyjąć (traktujemy `.doc` i `.docx` jako jedną rodzinę), czy odrzucić?
14. Godzina i sposób oddania projektu.
