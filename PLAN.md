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

**Decyzja D17: jedna osoba + agenci AI.** Tory to zadania dla agentów (np. workery Orca w osobnych worktree), osoba koordynuje i przegląda. Kolejność: A → B → C → D. Pochodzenie pól z ramkami na PDF i tryb wsadowy wypadają (D16).

## Kamienie milowe

| Godzina | Cel | Dowód |
|---|---|---|
| 15:30 | Kontrakty `Document` i IR spisane. Pytania zadane mentorom. Klucz EdenAI w `.env`, kandydaci na model docelowy porównani przez API (D20). | commit z modelami Pydantic, wynik porównania w `research/` |
| 17:00 | **Szkielet od końca do końca bez modelu:** PDF → heurystyki → kompilator → poprawny JSON z sekcjami predefiniowanymi. `docker compose up` działa. | `curl` z plikiem 3 zwraca JSON, linter bez błędów |
| 20:00 | Test odwracalności przechodzi dla obu referencji. Wszystkie osiem formatów przechodzi ingest. Krok A modelu działa na formularzach 3 i 4. Frontend: upload i drzewo JSON. | testy zielone, tabela formatów |
| 20:00+ | Pierwszy deploy demo na `formularze.heckyeah.pl` (D24), gdy `compose.yaml` działa; potem po każdym większym commicie. | link działa z telefonu |
| 00:00 | Kroki B i C, warunki `SHOW`, słowniki, dane inicjalne, walidatory. Harness ewaluacji daje liczby. Formularze 6 i 7. | pierwsza tabela metryk |
| 04:00 | Formularze 8 i 9. Podgląd e-formularza z JSONata. Propozycja słownika. JWT, limity, bramka licencyjna. | komplet `outputs/` |
| 07:00 | **Zamrożenie funkcji.** Tylko poprawki. Ostateczne wygenerowanie `outputs/` usługą (EdenAI, D21). Próbki zdegradowane, czasy, test na czystej maszynie amd64 (`wobbegong-ci` na PVE). | tabela czasów, `docker save` na nośniku |
| 08:30 | README, prezentacja (10 slajdów, PDF), film (do 3 min). | pliki w repo |
| 09:30 | Oddanie. Pół godziny zapasu. | potwierdzenie zgłoszenia |

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
