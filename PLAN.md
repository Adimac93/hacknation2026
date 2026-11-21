# Plan realizacji

Stan na 2026-11-21, godz. 14:30. Hackathon trwa 24 godziny, więc plan zakłada ok. 19 godzin do oddania. **Godzinę oddania trzeba potwierdzić u organizatora**; poniższe godziny przyjmują niedzielę 10:00.

Architektura: [`ARCHITECTURE.md`](ARCHITECTURE.md). Uzasadnienia: [`research/`](research/).

## Jak wygrywamy

Kryteria: kompletność 30%, intuicyjność 20%, jakość kodu 20%, potencjał wdrożeniowy z kosztem 20%, oryginalność 10%. Finaliści uruchamiają rozwiązanie na żywo na nowych plikach.

| Co pokazujemy | Kryterium | Dlaczego to działa |
|---|---|---|
| JSON, który zawsze przechodzi reguły techniczne (linter z auto-naprawą) | kompletność, wdrożenie | plik importuje się bez poprawek |
| Wynik zbudowany z sekcji predefiniowanych COI, z warunkami, słownikami i danymi z rejestrów | kompletność (rozszerzenia I, III) | wygląda jak praca analityka COI |
| Liczby: pokrycie względem dwóch referencji, spójność 8 formatów, czasy | jakość, wdrożenie | dowód zamiast deklaracji |
| Ekran „dokument obok formularza” z pochodzeniem pola i podglądem na żywo | intuicyjność, oryginalność | urzędnik jako audytor, zgodnie z podejściem COI do AI |
| Model open-weight (Apache-2.0) wymienny przez `LLM_BASE_URL`, tryb reguł bez sieci, raport licencji, koszt na formularz | wdrożenie | pasuje do AI Hub COI: model podmienia się konfiguracją |
| Tryb awaryjny bez modelu | wdrożenie | demo na żywo nie może się wyłożyć |

## Zakres

**Obowiązkowe:** REST API dla ośmiu formatów, walidacja pliku, JWT, konfiguracja, Docker, README, dokumentacja architektury, wynikowe JSON-y dla formularzy 3, 4, 6, 7, 8, 9.

**Rozszerzenia, w kolejności opłacalności:**

1. Słowniki i dane inicjalne (I) oraz zależności między polami (III): wychodzą z biblioteki sekcji.
2. Walidacje pól (VI): walidatory w JSON-ie i w podglądzie.
3. Frontend: upload i podgląd JSON-a (IV).
4. Podgląd e-formularza z JSONata na żywo (V).
5. Nowy słownik (II).
6. Tryb wsadowy i pochodzenie pól.

**Poza zakresem:** model wizyjny dla zdjęć, strony alternatywne w `flow`, logowanie użytkowników, baza danych, eksport do CRWDE.

## Tory pracy

Cztery tory niezależne po ustaleniu dwóch kontraktów: modelu `Document` (wyjście ingest) i modelu IR (wejście kompilatora). Oba kontrakty spisujemy w pierwszej godzinie.

| Tor | Zakres | Pliki |
|---|---|---|
| A. Kompilator | modele JSON-a wyjściowego, biblioteka sekcji, kompilator, linter, dekompilator referencji, test odwracalności | `schema.py`, `ir.py`, `sections.py`, `compiler.py`, `lint.py` |
| B. Ingest | walidacja uploadu, PDF, cięcie obrazów i OCR, adapter Tika, linearyzacja | `upload.py`, `ingest/`, `tika/` |
| C. Rozumienie | `llama-server`, pomiar modeli, heurystyki, trzy prompty, harness ewaluacji | `heuristics.py`, `llm.py`, `tests/eval/` |
| D. Produkt | szkielet API, JWT, compose, frontend, README, prezentacja, film | `main.py`, `auth.py`, `config.py`, `web/`, `compose.yaml` |

Przy trzech osobach tor D dzielą między siebie A (API, compose) i C (frontend po północy). Przy dwóch osobach: jedna bierze A + D, druga B + C, a pochodzenie pól i tryb wsadowy wypadają.

**Decyzja D17: trzy osoby + agenci AI** (Adimac93, Stanisław Synowiec, fidok15):

| Osoba | Tor |
|---|---|
| Adimac93 | A (kompilator, linter, sekcje predefiniowane) i C (model, EdenAI, ewaluacja) |
| Stanisław Synowiec | D: frontend `web/` |
| fidok15 | research OCR (`research/01`); tor B od 18:55 prowadzą agenci Adimac93: czytniki PDF i Tika (`ingest/pdf.py`, `office.py`), OCR obrazów (`ingest/raster.py`) |

Pochodzenie pól z ramkami na PDF i tryb wsadowy wypadają (D16).

### Tor D: stan przekazania (Stanisław)

Gotowe na `main` (98 testów Vitest, `biome` i `npm run build` bez błędów, 148 pakietów npm na MIT, Apache-2.0, BSD, ISC):

- renderer e-formularza (`web/src/renderer/`): kroki z `flow.links`, sekcje w siatce, 11 typów pól i komunikat dla nieznanego typu, `REPEATING_SECTION`, warunki `SHOW` i `READ_ONLY` przez `jsonata`, walidacja przy „Dalej” z podsumowaniem błędów, strona `FINISH` jako podsumowanie,
- trasa `/podglad`: wczytanie pliku JSON, przeciągnij i upuść, przykłady 1 i 5 (`web/public/examples/`),
- walidatory z wektorami w `fixtures/validators.json` (wspólne z backendem),
- celowo bez `@vitejs/plugin-react` (zależność `caniuse-lite` jest na CC-BY-4.0); JSX kompiluje esbuild.

Do zrobienia, w kolejności:

1. Stanowisko urzędnika na `/` (teraz zaślepka): upload do `POST /api/v1/forms?details=true`, drzewo JSON (`vanilla-jsoneditor`), raport lintera, pobranie pliku, panel tekstu dokumentu z podświetleniem linii źródłowych pola (D16). Kontrakt odpowiedzi `report` ustalimy z torem A, gdy powstanie `main.py`.
2. Uzgodnić `DESIGN.md` (Biurokratka) z D22: propozycja: stanowisko w stylu Biurokratki, podgląd e-formularza w wyglądzie e-usługi COI. Fonty Archivo i IBM Plex Mono są na SIL OFL-1.1; dopuszczone w D25 i `CLAUDE.md` (tylko fonty, teksty licencji w `web/licenses/`). Zostaje decyzja o wyglądzie podglądu e-formularza.
3. ~~Kontener `web` (nginx-unprivileged, proxy `/api`) do `compose.yaml` i demo D24.~~ Gotowe 22:00, sprawdzone na czystym amd64 (`wobbegong-ci`).
4. Pominięte świadomie: wysyłka formularza, pełne słowniki (są przykładowe zestawy), potwierdzenie przy „Przerwij wypełnianie”.

## Kamienie milowe

Plan zmieniony o 17:45: kamień z 17:00 się spóźnił, więc szkielet od pliku do JSON-a przesuwa się na 21:00. Kolejność: najpierw tryb reguł, potem model.

| Godzina | Cel | Kto | Dowód |
|---|---|---|---|
| 21:00 | **Od pliku do JSON-a bez modelu.** Upload z walidacją, `POST /api/v1/forms` (problem+json, `/health`, JWT opcjonalny), ingest PDF, heurystyki, biblioteka sekcji predefiniowanych, linter z auto-naprawą, `compose.yaml` z `api` i `tika`. | worker 1: upload + API; worker 2: linter + Docker; fidok15: `ingest/pdf.py`; Adimac93: `sections.py`, `heuristics.py`, `pipeline.py`; Stanisław: stanowisko na danych przykładowych z kontraktu 8.1 | `curl` z PDF formularza 3 zwraca JSON z sekcjami predefiniowanymi, linter bez błędów |
| 01:00 | **Model.** Porównanie D20, `llm.py` z trzema krokami i przejściem na reguły, złote IR formularzy 3–9 (D11), harness z metrykami. Ingest DOC, DOCX, ODS, XLSX (Tika) i rastrów (RapidOCR). Stanowisko podpięte do API. | Adimac93: model i harness; fidok15: Tika i OCR; Stanisław: frontend | tabela metryk, osiem formatów przechodzi ingest |
| 05:00 | Formularze 6–9, komplet `outputs/`, deploy demo (D24), limity, bramka licencyjna, propozycja słownika. | wszyscy | komplet `outputs/`, link demo działa |
| 07:00 | **Zamrożenie funkcji.** Tylko poprawki. Ostateczne `outputs/` z usługi (EdenAI, D21). Próbki zdegradowane, czasy, test na czystej maszynie amd64 (`wobbegong-ci`). | wszyscy | tabela czasów, `docker save` na nośniku |
| 08:30 | README, prezentacja (10 slajdów, PDF), film (do 3 min). | wszyscy | pliki w repo |
| 09:30 | Oddanie (godzinę potwierdzić u organizatora). | | potwierdzenie zgłoszenia |

Zasada: jeśli kamień spóźnia się ponad godzinę, tniemy zakres z dołu listy rozszerzeń, nie przesuwamy zamrożenia.

## Pierwsze kroki (pierwsza godzina)

1. Zadać mentorom pytania z sekcji 14 w `ARCHITECTURE.md`. Najpilniejsze: format `validation`, klucz `repeatingSectionGrid`, zawartość strony `FINISH`, nazwy słowników, zgodność lokalnego serwera modelu z regulaminem, godzina oddania.
2. Poprosić mentora o próbny import jednego JSON-a do Generatora, gdy tylko powstanie.
3. Bez modeli self-hostowanych w developmencie (D11). Klucz EdenAI do `.env`, `LLM_ALLOW_REMOTE=true`, endpoint `https://api.eu.edenai.run/v3`. Porównać kandydatów na model docelowy przez API na formularzach referencyjnych (D20).
4. Modelu nie uruchamiamy lokalnie w czasie hackathonu (D21). Lokalne hostowanie opisujemy w README jako konfigurację docelową.
5. Założyć `api/` przez `uv init`, dodać `ruff`, `mypy`, `pytest`.

## Ryzyka

| Ryzyko | Zabezpieczenie |
|---|---|
| Model za wolny na żywo | krótki IR, budżet czasu na żądanie, tryb reguł |
| Jury uzna wołanie EdenAI na obronie za zewnętrzne API | pytanie do mentorów w pierwszej godzinie; tryb reguł (`LLM_ENABLED=false`) gotowy do przełączenia jedną zmienną; model open-weight i kod bez zależności od EdenAI |
| Brak sieci na sali obrony | tryb reguł; hotspot jako zapas |
| Nowy plik na obronie to skan albo zdjęcie | OCR przetestowany na próbkach zdegradowanych; prostowanie obrazu; tryb reguł działa także na tekście z OCR |
| JSON nie importuje się w Generatorze | linter, test odwracalności, wczesny próbny import u mentora |
| Naruszenie licencji | lista zakazów w `CLAUDE.md`, bramka `pip-licenses` w CI, ręczna kontrola licencji wag |
| Docker nie buduje się na obcej maszynie | obrazy dla `amd64` i `arm64`, przypięte digesty, `docker save` na nośniku, test na czystej maszynie przed 07:00 |
| Brak pamięci na 16 GB | limit pamięci Docker Desktop, mniejszy model, Tika z limitem JVM |
| Jury chce demo zamiast slajdów | scenariusz ćwiczony na obcych plikach, w tym przypadek negatywny (zły plik), film jako zapas |
| Niejasności w materiałach | pytania do mentorów w pierwszej godzinie; do czasu odpowiedzi trzymamy się referencyjnych JSON-ów |

## Materiały do oddania

- tytuł i szczegółowy opis projektu,
- prezentacja PDF, najwyżej 10 slajdów (konspekt w `research/03-konkurencja-i-wyrozniki.md`, sekcja 6),
- wynikowe pliki JSON w `outputs/`,
- film do 3 minut w otwartym repozytorium (scenariusz tamże),
- repozytorium kodu z `README.md` i `ARCHITECTURE.md`.

## Wtyczki i narzędzia pomocnicze

Narzędzia do pisania kodu nie są częścią rozwiązania, więc zakaz zewnętrznych API ich nie dotyczy.

- `frontend-design` i `react-no-slop`: podgląd formularza i ekran weryfikacji.
- `superpowers:test-driven-development`: kompilator i linter.
- `playwright`: test dymny frontendu i nagranie ujęć do filmu.
- `ecc:python-review` i `ecc:security-review`: przegląd przed zamrożeniem.
- Warto doinstalować Context7 (aktualna dokumentacja FastAPI, pdfplumber, llama.cpp), bo część bibliotek ma wydania nowsze niż wiedza modelu.
