# Plan realizacji

Stan na 2026-11-21, godz. 14:30. Hackathon trwa 24 godziny, więc plan zakłada ok. 19 godzin do oddania. **Godzina oddania potwierdzona: niedziela 22.11.2026, 9:30.** Poniższe kamienie milowe liczą się wstecz od niej.

Architektura: [`ARCHITECTURE.md`](ARCHITECTURE.md). Uzasadnienia: [`research/`](research/).

## Stan o 22:45 i plan do oddania

Zostało niecałe 11 godzin. Zamrożenie funkcji o 07:00 bez zmian, oddanie o 9:30.

**Gotowe i sprawdzone** (`main`, demo `formularze.heckyeah.pl` w tej samej wersji):

- REST API dla ośmiu formatów: macierz 54 plików (formularze 3–9 w każdym formacie) daje 54 × HTTP 200 i 0 błędów lintera, tytuł spójny między formatami; stos w kontenerach na czystym amd64,
- OCR rastrów: strony równolegle; zdjęcie formularza 9 (16 stron) w 15 s na M1 Pro, w 21 s na serwerze,
- stanowisko urzędnika na `/` i podgląd na `/podglad`, kontener `web` z limitem 10 POST na minutę na IP,
- `outputs/` dla formularzy 3, 4, 6–9 z trybu reguł (generator: `devtools/generate_outputs.py`),
- tryb modelu: Qwen3.5-9B przez EdenAI, ok. 0,001 USD i 7–45 s na formularz.

**Znane problemy:**

- model wpada w pętlę powtórzeń (to samo pole w kółko, formularze 3 i 9). EdenAI nie trzyma ziarna, więc wynik zmienia się między przebiegami. Usługa wraca wtedy do reguł, ale traci do 60 s,
- `report.dictionary_proposals` jest zawsze puste (rozszerzenie II nie działa po stronie backendu),
- nazwy plików w `outputs/` zależą od tytułu, więc tryb modelu i tryb reguł dają różne nazwy,
- brak bramki licencyjnej `pip-licenses` i README bez opisu lokalnego hostowania modelu.

### Stan o 08:45 (przed oddaniem)

Na `main`: wszystko z fal 1–2, W7 (bez duplikatów sekcji), W9 (`research/12`), ostateczne `outputs/` w trybie modelu, opis zgłoszenia (`research/14-opis-zgloszenia.md`). Prezentacja: artefakt Slides (10 slajdów, eksport do PDF). W nocy agenci W6, W8, W10, W11 trafili na limit użycia; ich niedokończone zmiany zostają w worktree i nie wchodzą po zamrożeniu. Obrazy amd64: `/root/images/biurokratka-amd64.tar.gz` na LXC 104.

Do oddania o 9:30: PDF prezentacji, film (nagranie: ludzie), formularz zgłoszenia z tekstem z `research/14`.

### Stan o 01:15

Zrobione i na `main`: B1 (budżet tokenów, odzysk z pętli, prompt), B2, B3, B4 (`research/08`: 53/53 plików, HTTP 200, 0 błędów lintera), B5 (`research/10`: model 64–82%, reguły 9%), B6 (bramka licencji, D26), B7 (ostateczne `outputs/` w trybie modelu, bez pól podpisu). Demo na najnowszym kodzie.

Fala 3 (agenci, do 05:00):

| # | Zadanie | Pliki |
|---|---|---|
| W6 | Etykiety pól w trybie reguł (dziś 9% pokrycia; to tryb zgodny z regulaminem i zapas na obronę) | `heuristics.py` |
| W7 | Wynik modelu bez duplikatów sekcji predefiniowanych (np. „Dane identyfikacyjne” obok „Twoje dane” w formularzu 8) | `llm.py` |
| W8 | Odporność OCR na zdegradowane skany i zdjęcia (obrót, rozmycie, kompresja, jedna strona) | `ingest/raster.py`, `research/11` |
| W9 | Treść prezentacji (10 slajdów), scenariusz filmu, scenariusz demo na żywo | `research/12` |

Potem (koordynator): ponowne `outputs/` po W7, test czystego klonu repozytorium na amd64, `docker save`, sprzątanie worktree. Merge co godzinę.

### Backend i model (Adimac93 + agenci), do 07:00

| # | Zadanie | Dlaczego | Gotowe, gdy |
|---|---|---|---|
| B1 | Pętle modelu: budżet `max_tokens` zależny od liczby pól z heurystyk, wykrycie powtórzonego klucza i natychmiastowy powrót do reguł | demo na żywo nie może czekać 60 s | formularze 3–9 w trybie modelu bez ucięcia w 3 przebiegach z rzędu |
| B2 | Stałe nazwy plików w `outputs/` (numer + nazwa z katalogu `Docs/`) | powtarzalne oddanie | nazwy niezależne od trybu |
| B3 | Propozycje słowników (`dictionary_proposals`): pola wyboru z co najmniej 3 opcjami spoza słowników COI | rozszerzenie II, frontend już to pokazuje | test + propozycja na formularzu 6 lub 8 |
| B4 | Macierz formatów jako skrypt w `devtools/` i tabela w `research/` | liczby na slajd („spójność 8 formatów”) | tabela czasów i pól w repo |
| B5 | Pokrycie pól względem referencji 1 i 5 (dekompilacja, porównanie etykiet) | liczby na slajd („pokrycie”) | metryka w tabeli |
| B6 | Bramka `pip-licenses` + raport licencji npm, README: lokalny `llama-server`, koszt na formularz, tabela czasów | jakość kodu, potencjał wdrożeniowy | polecenie w README, raport w repo |
| B7 | Ostateczne `outputs/` w trybie modelu (D21), przy pętli zostaje wynik z reguł | wymagane do oddania | o 07:00 |
| B8 | `docker save` obrazów na nośnik, porządek w worktree | zapas na obronę | pliki `.tar` poza repo |

### Frontend (Stanisław), do 07:00

| # | Zadanie | Dlaczego |
|---|---|---|
| F1 | Tryb wsadowy: obsłużyć 429 z `Retry-After` (kolejka czeka i ponawia), komunikat dla 504 | nginx przepuszcza 10 plików na minutę; wsad 20 plików teraz się wyłoży |
| F2 | Lista pól do sprawdzenia: pola z `confidence` < 0,7 w raporcie, klik przenosi do pola i podświetla źródło | „urzędnik jako audytor”, najmocniejszy wyróżnik |
| F3 | Klik w linię dokumentu zaznacza pole, które z niej powstało (odwrotność obecnego podświetlenia) | intuicyjność |
| F4 | Czas oczekiwania: komunikat, że zdjęcia i tryb modelu trwają 15–60 s | demo na żywo |
| F5 | Test dymny Playwright na stosie `docker compose` (upload PDF, PNG, zły plik) | przypadek negatywny na obronie |
| F6 | Decyzja o wyglądzie podglądu e-formularza (pkt 2 niżej) i kontrola WCAG (klawiatura, kontrast, rzutnik 1366 px) | intuicyjność 20% |
| F7 | Od 07:00: nagranie filmu do 3 minut i zrzuty ekranu do prezentacji | materiały do oddania |

Bez nowych zależności npm bez sprawdzenia licencji (ostatnio doszły `lucide-react` na ISC i fonty na OFL, D25).

### 07:00–09:30: wszyscy

Zamrożenie funkcji. Ostateczne `outputs/`, próba scenariusza demo na obcych plikach (w tym zły plik i tryb `LLM_ENABLED=false`), prezentacja (10 slajdów, PDF, konspekt w `research/03`), film, README, oddanie przed 9:30.

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

1. ~~Stanowisko urzędnika na `/`~~ Gotowe 22:00 (`feat/web-workspace`). Pierwotny zakres: upload do `POST /api/v1/forms?details=true`, drzewo JSON (`vanilla-jsoneditor`), raport lintera, pobranie pliku, panel tekstu dokumentu z podświetleniem linii źródłowych pola (D16). Kontrakt odpowiedzi `report` ustalimy z torem A, gdy powstanie `main.py`.
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
| 09:30 | Oddanie (godzina potwierdzona przez organizatora). | | potwierdzenie zgłoszenia |

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
| Jury uzna wołanie EdenAI na obronie za zewnętrzne API | **rozstrzygnięte przez mentora:** dozwolone, jeśli model jest otwarty i da się go postawić u siebie; pilnujemy, by `LLM_MODEL` wskazywał tylko modele open-weight, a README opisywał lokalne hostowanie; tryb reguł (`LLM_ENABLED=false`) gotowy do przełączenia jedną zmienną; model open-weight i kod bez zależności od EdenAI |
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
