 # Raport zgodności z wymaganiami zadania COI

Stan: 2026-11-22, krótko po 09:30, `main` po merge `37f3b6e`. Sprawdzone: kod w repozytorium, działający stos `docker compose` (web, api, tika), testy na żywo przez `localhost:8080`. Legenda: ✅ jest i sprawdzone, 🟡 jest, ale z zastrzeżeniem, ❌ brak, ❔ nie dało się sprawdzić.

## 1. Podsumowanie według wagi kryteriów

| Kryterium (waga) | Ocena | Najważniejsze |
|---|---|---|
| Kompletność (30%): minimum + 5 rozszerzeń | ✅ minimum, ✅ rozszerzenia I–V | Wszystkie zrealizowane. Słabe punkty: zgodność z referencjami (patrz 3) i niestabilność modelu na dużych plikach. |
| Intuicyjność (20%) | ✅ | Kolejka, podgląd obok źródła, raport, wskazówki czasu oczekiwania, polskie komunikaty błędów, WCAG (Lighthouse a11y 100, własna sonda bez naruszeń). |
| Oryginalność (10%) | ✅ | Podświetlanie dwukierunkowe pole ↔ linia dokumentu, lista pól o niskiej pewności, tryb reguł jako zapas, raport lintera. |
| Jakość kodu (20%) | ✅ | 205 testów frontendu, testy API i zgodności ze schematem, biome/tsc/mypy, bramka licencji. Nie uruchomiłem testów API (brak `uv` na tym komputerze). |
| Potencjał wdrożeniowy / koszt (20%) | 🟡 | Docker, tryb reguł bez kosztu, wymienny model. Brakuje: liczb kosztu na formularz w README (jest sekcja „Koszt i czas”, nie weryfikowałem wartości), stabilności modelu. |

## 2. Minimalny zakres (3.2) i wymagania techniczne (5)

| Wymaganie | Stan | Dowód |
|---|---|---|
| REST API przyjmujące pojedynczy plik | ✅ | `POST /api/v1/forms`, `?details=true` zwraca `{form, report}` |
| Formaty: PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG | ✅ | wszystkie 8 formatów przechodzą (macierz e2e 56/58, `research/08`: 53/53 HTTP 200); API przyjmuje też `.jpe` i front już też |
| JSON zgodny ze strukturą aplikacji | ✅ | `test_conformance.py` waliduje wyniki i referencje oficjalnym schematem; `research/13` |
| Wynik spełnia wymagania projektowania (strony tematyczne, FINISH itd.) | ✅ | linter L001–L031 bez błędów na wszystkich 6 wynikach |
| Walidacja typu pliku + zgodność MIME z rozszerzeniem | ✅ | na żywo: `x.exe` → 415, PNG z treścią PDF → 415 „Treść pliku nie odpowiada rozszerzeniu” |
| Nazwa pliku ≤ 250 znaków | ✅ | 251 znaków → 400 |
| Zakazane znaki `; : > < / \ \| ' * % $` | ✅ | `'` → 400 z listą znaków (`;` testowany przez curl nieprecyzyjnie, bo curl dzieli nazwę na `;`; pokryte testami API) |
| Rozmiar konfigurowalny parametrem | ✅ | `MAX_UPLOAD_MB`, plik 21 MB → 413 |
| Pliki tylko w pamięci/tmpfs | ✅ | kontenery `read_only` z `/tmp` w tmpfs (README, `compose.yaml`) |
| Docker: oficjalne obrazy, wersje przypięte, bez `latest` | ✅ | `python:3.14.10-slim-trixie`, `node:26.13.1-trixie-slim`, `nginx-unprivileged:1.30.6-alpine3.24-slim`, `eclipse-temurin:25.0.5.1_2-jre-alpine-3.24`, tika 3.3.2 |
| Proces na dedykowanym użytkowniku | ✅ | `USER app:app`, `USER nginx`, `USER tika:tika` |
| Tylko niezbędne porty | ✅ | tylko `127.0.0.1:8080`; api i tika bez publikacji |
| Sekrety w runtime | ✅ | `.env` / zmienne środowiskowe, `JWT_SECRET_FILE` |
| Konfiguracja: rozmiar, JWT, parametry integracyjne | ✅ | `.env.example`: `MAX_UPLOAD_MB`, `AUTH_ENABLED`, `JWT_*`, `LLM_*`, `TIKA_URL` |
| JWT | 🟡 | zaimplementowany i wyłączony domyślnie (`AUTH_ENABLED=false`); na żywo sprawdziłem tylko tryb wyłączony, ścieżkę 401 pokrywają testy |
| Python 3.14+ | ✅ | obraz 3.14.10 |
| Licencje bez copyleft | 🟡 | zasady i `devtools/check_licenses.py` są; nie uruchomiłem (brak `uv`). Wyjątek: przechodnie `certifi` i `tqdm` na MPL-2.0 (D26) oraz fonty OFL (D25), opisane w dokumentach |
| Brak zewnętrznych API/SaaS, brak modeli tylko przez API | 🟡 | tryb reguł działa bez sieci. Tryb modelu woła endpoint zgodny z OpenAI (EdenAI) z modelem open-weight; potwierdzone przez mentora (CLAUDE.md). Zastrzeżenie: patrz 4, punkt 1 |
| README.md: budowanie obrazu, uruchomienie, konfiguracja, opis REST API | 🟡 | uruchomienie i konfiguracja są. Brakuje osobnej instrukcji „zbuduj obraz” (jest `docker compose up --build`), a opis REST API to dwa polecenia `curl` i jedno zdanie o błędach: bez tabeli statusów, bez opisu JWT i bez pól raportu |
| Dokumentacja architektury | ✅ | `ARCHITECTURE.md`, `PLAN.md`, `research/` |

## 3. Opcjonalne rozszerzenia (3.3)

| Punkt | Stan | Komentarz |
|---|---|---|
| I. Słowniki i dane inicjalne powiązane z polami | ✅ | pola wyboru z słownikami COI, dane z rejestrów (`EXTERNAL_SYSTEM`); front pokazuje je w e-formularzu |
| II. Propozycja nowego słownika | ✅ | `dictionary_proposals` w raporcie; front pokazuje w zakładce „Raport”. Liczba propozycji zależy od formularza (często „Brak propozycji”) |
| III. Zależności między polami, sekcjami, stronami | ✅ | stany JSONata (SHOW/READ_ONLY), przepływ stron; renderer wykonuje je na żywo; testy korpusu przechodzą wszystkie wyniki |
| IV. Frontend do wgrywania i przeglądania JSON | ✅ | stanowisko urzędnika: kolejka, drzewo/tekst JSON, kopiuj/pobierz |
| V. Aplikacja do wizualizacji JSON | ✅ | `/podglad` i podgląd e-formularza w wyniku |
| VI. Walidacje, batch, makiety | ✅ | PESEL/NIP/REGON/e-mail/kod pocztowy w rendererze, przetwarzanie wsadowe z ponawianiem po 429 |

Uwaga: tabela kryteriów oceny w zadaniu nazywa punkt V „Walidacje pól”, a w opisie rozszerzeń walidacje to punkt VI. Mamy oba.

## 4. Czego nie mamy lub co jest słabe (ważne przed oceną)

1. **Lokalny `.env` (poza repozytorium) wskazuje `mistral/ministral-8b-2512@eu`, a całe repozytorium (README, `.env.example`, `config.py`, `outputs/README.md`, slajdy, ARCHITECTURE) mówi o Qwen3.5-9B.** Dokumenty i wygenerowane `outputs/` są spójne ze sobą (Qwen), ale stos uruchomiony na tym komputerze używa Ministrala, więc wszystkie moje testy na żywo szły na Ministralu. Przed obroną ustalić, który model jest na demo (Ministral-3-8B ma licencję Apache-2.0 według `research/05`; ARCHITECTURE D3 odrzucał go po porównaniu).
2. **Zgodność z referencjami nie jest pełna.** Folder 1: 38 pól wobec 53 (brakuje 20 pól wzoru, głównie blok „inna osoba”). Folder 5: 57 wobec 55, ale 6 kart zamiast 4 i część pól inaczej nazwana. Typy i walidacje wspólnych pól zgadzają się (0 różnic w typie).
3. **Powtarzalność wyniku.** Wymaganie „powtarzalny wynik” jest w CLAUDE.md. Agent e2e zaobserwował różne wyniki tego samego pliku w kolejnych przebiegach (tryb modelu). Nie ma gwarancji determinizmu.
4. **Stabilność modelu na dużych plikach (folder 8).** Krok modelu czasem pada i usługa wraca do reguł; wtedy wynik jest mniejszy (około 50 pól wobec około 100). To zgodne z założeniem „awaria modelu nie daje 500”, ale jakość spada.
5. **`outputs/` nie jest odświeżony po ostatnich zmianach Adama** (ostatni commit `ecaf4cb`, przed poprawkami etykiet, lintera i tytułów). Pliki do oddania mogą nie odpowiadać aktualnemu kodowi.
6. **Pełna macierz e2e nie została powtórzona po ostatnim merge.** Ostatni pełny przebieg: 56/58 (dwa błędy z `pesel_nip_regon`, od tego czasu naprawione w API, co potwierdził pojedynczy test folderu 8). W ostatnim przebiegu ukończyły się tylko 2 z 7 PDF-ów (zatrzymałem test, który wisiał na folderze 5), więc nowy pełny wynik nie istnieje.

## 5. Wymagania formalne (4)

| Element | Stan |
|---|---|
| Opis i tytuł projektu | ✅ `submission/OPIS-ZGLOSZENIA.md` i `research/14`; linki do repozytorium, filmu i demo oraz zespół uzupełnione 2026-11-22 |
| Prezentacja PDF, max 10 slajdów | ✅ `submission/slides/Biurokratka-prezentacja.pdf`, 10 stron, z prawdziwymi zrzutami (brakuje `ekran-podglad` i `terminal-docker`). Równolegle istnieje wersja Adama (`research/12`): trzeba wybrać jedną |
| Wynikowe pliki JSON | 🟡 `outputs/` ma formularze 3, 4, 6, 7, 8, 9; patrz punkt 4.5 (odświeżenie) |
| Film do 3 minut w otwartym repozytorium (link) | 🟡 film robi Adam (85 s), link https://formularze.heckyeah.pl/film.mp4 wpisany w opis i slajd 10; nie sprawdzałem, czy plik już działa |
| Repozytorium kodu | 🟡 kod jest; link publiczny do wpisania w zgłoszeniu |
| Zrzuty ekranu (dodatkowo) | ✅ 6 zrzutów w `submission/slides/img/` |
| Demo online (dodatkowo) | 🟡 https://formularze.heckyeah.pl (według `research/14`); nie sprawdzałem |

## 6. Rekomendowana kolejność poprawek

1. Sprawdzić, że film (Adam) i demo faktycznie działają pod wpisanymi linkami.
2. Ustalić model na demo (Qwen czy Ministral); repozytorium jest spójne z Qwenem.
3. Przegenerować `outputs/` na aktualnym kodzie (poleceniem z README) i sprawdzić je schematem.
4. Wybrać jedną prezentację (moja z `submission/` lub Adama) i dokończyć dwa brakujące zrzuty.

## 7. Czego nie sprawdziłem

- Testów API (`pytest`, `mypy`, `ruff`) i bramki licencji: brak `uv` na tym komputerze.
- JWT na żywo przy `AUTH_ENABLED=true`.
- Zgodności licencji wag modelu Ministral 8B.
- Kosztu na formularz podanego w README (liczby nie weryfikowane).
- Czystego klonu repozytorium na amd64 i `docker save` (zadanie B8 Adama).
- Pełnego przejścia e-formularza przez UI na wszystkich formatach po ostatnim merge.
