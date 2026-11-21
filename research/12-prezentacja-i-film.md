# 12. Prezentacja, film i scenariusz demo na żywo

Stan na 2026-11-21, ok. 23:50, commit `a422cc7` na `main`. Materiały do oddania o 9:30: prezentacja PDF (najwyżej 10 slajdów), film (do 3 minut), demo na żywo dla finalistów (`PLAN.md`, „Materiały do oddania”). Konspekt wyjściowy: `research/03-konkurencja-i-wyrozniki.md`, sekcja 6.

Kryteria jury: kompletność 30%, intuicyjność 20%, jakość kodu 20%, potencjał wdrożeniowy z kosztem 20%, oryginalność 10% (`PLAN.md`, „Jak wygrywamy”).

**Zasada dla całego dokumentu:** każda liczba ma obok źródło w repozytorium. Czego nie zmierzyliśmy, oznaczamy `TODO`. Przed eksportem PDF sprawdź, czy liczby się nie zmieniły (sekcja 5, „Źródła liczb”).

## 1. Slajdy (10)

Wspólne dla wszystkich slajdów: kolory i fonty z `DESIGN.md` i `ksiega-znaku-biurokratka.pdf`, logo z `logo-pack/` (nie rysujemy własnego). Jedna myśl na slajd, najwyżej 5 krótkich punktów. Bez godła i logotypów administracji.

### Slajd 1. Biurokratka: z blankietu do e-formularza

- Jedno zdanie: **„Wgrywasz blankiet urzędowy, dostajesz JSON gotowy do importu w Generatorze Formularzy COI.”**
- Podtytuł: HackNation 2026, zadanie COI „Cyfryzacja formularzy”.
- Zespół: Adimac93, Stanisław Synowiec, fidok15 (`PLAN.md`, D17).

Wizual: logo Biurokratki (`logo-pack/`), w tle rozmyty zrzut stanowiska urzędnika.

### Slajd 2. Problem

- Urzędy publikują wnioski jako PDF, DOC, arkusze i skany. Obywatel drukuje, wypełnia ręcznie, skanuje.
- Każdy wzór trzeba dziś ręcznie przeprojektować w Generatorze: strony, sekcje, słowniki, warunki.
- Wynik ma być **przeprojektowanym** formularzem zgodnym ze standardami COI, nie przepisaniem blankietu (`CLAUDE.md`, „Co budujemy”).
- Wejście: 8 formatów (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG), w tym zdjęcia wielostronicowe (`README.md`).

Wizual: z lewej skan blankietu z kratkami i wykropkowaniami (np. formularz 8 z `Docs/`), z prawej ten sam formularz jako e-usługa w podglądzie.

### Slajd 3. Rozwiązanie: kompilator, nie OCR

- Plik → **Document** (tekst z układem) → **IR** (krótka lista pól) → **compiler** → **linter** → **JSON** (`ARCHITECTURE.md`, sekcje 1 i 5).
- **Model pisze tylko IR.** Końcowy JSON składa kod z biblioteki sekcji predefiniowanych COI, a linter sprawdza reguły techniczne i naprawia naruszenia (`ARCHITECTURE.md`, D2).
- Awaria modelu nie psuje wyniku: usługa przechodzi na heurystyki, bez błędu 500 (`ARCHITECTURE.md`, 5.3; `api/src/formcompiler/pipeline.py`).
- Linter: 25 reguł blokujących (`L001`–`L025`) i 11 ostrzeżeń (`L101`–`L111`) (`ARCHITECTURE.md`, 5.7).

Wizual: diagram potoku w jednym rzędzie. Strzałka „model” wchodzi tylko do pola IR, przerywaną linią; pola compiler i linter w kolorze głównym z podpisem „kod deterministyczny”. Pod diagramem trzy źródła wejścia: `pdfplumber` (PDF), Apache Tika (DOC, DOCX, ODS, XLSX), RapidOCR (JPG, PNG).

### Slajd 4. Stanowisko urzędnika: urzędnik jako audytor

- Kolejka plików z licznikiem sekund i paskiem postępu; kilka plików naraz to tryb wsadowy (`web/src/workspace/Queue.tsx`).
- Widok **„Dokument i formularz”**: tekst dokumentu obok podglądu e-formularza (`web/src/workspace/Workspace.tsx`).
- **Pochodzenie pola**: wybór pola w „Pokaż źródło pola” podświetla linie dokumentu, z których powstało, i pokazuje pewność rozpoznania; poniżej 70% komunikat „sprawdź to pole przed eksportem” (`web/src/workspace/SourcePanel.tsx`).
- Zakładki **JSON** (kopiuj, pobierz) i **Raport** (tryb, model, uwagi lintera, propozycje słowników, czas etapów) (`JsonPanel.tsx`, `ReportPanel.tsx`).
- Plik nie jest zapisywany na serwerze; komunikat na ekranie i zasada twarda 3 w `CLAUDE.md`.

Wizual: duży zrzut widoku „Dokument i formularz” z podświetlonymi liniami źródłowymi wybranego pola i napisem „Pewność rozpoznania: …%”. `TODO`: zrzut ekranu z działającego stosu (F7 w `PLAN.md`).

### Slajd 5. Dowody w liczbach

Cztery duże liczby, każda z podpisem źródła na slajdzie:

| Liczba | Co znaczy | Źródło |
|---|---|---|
| **53 / 53** | blankiety z `Docs/` 3–9 we wszystkich formatach: 53 × HTTP 200, 0 błędów lintera | `research/08-macierz-formatow.md` |
| **6 / 6** | wynikowe JSON-y formularzy 3, 4, 6–9 w trybie modelu, 0 błędów lintera, 4,9–53,7 s na formularz | `outputs/README.md` |
| **64% / ok. 90%** | pokrycie pól referencji 1 i 5: ścisłe dopasowanie etykiet / ocena znaczeniowa (ręczna), tryb modelu bez własnego przykładu; tryb reguł: 9% | `research/10-pokrycie-referencji.md` |
| **468 + 106** | testy: `pytest` w `api/` (468 zaliczone, 3 pominięte), Vitest w `web/` (106 w 5 plikach) | uruchomione 2026-11-21 ok. 23:50, sekcja 5 |

Dopisek pod tabelą (mała czcionka): szkielet formularza (4 strony, 3 sekcje predefiniowane, rodzaj adresata) zgodny z referencją we wszystkich 14 przebiegach, także w trybie reguł i z rastra (`research/10`). Próba pokrycia jest mała: 11 pól w dwóch formularzach.

Wizual: cztery kafelki z liczbami, bez wykresów.

### Slajd 6. Model wymienny, tryb reguł zawsze pod ręką

- Model: open-weight **Qwen3.5-9B** (Apache-2.0), na hackathonie przez EdenAI na endpoincie UE (`README.md`, „Model językowy”; D3, D11, D21).
- Klient zna tylko wspólną część API zgodnego z OpenAI: `messages`, `temperature`, `seed`, `max_tokens`, `response_format` z `json_schema` (`CLAUDE.md`, zasada 2).
- Zmiana modelu to **jedna zmienna**: `LLM_BASE_URL` na lokalny `llama-server` z tym samym modelem w GGUF (Q4_K_M, ok. 5,5 GB) (`README.md`). Konfiguracja lokalna nie była testowana w czasie hackathonu (tamże).
- `LLM_ENABLED=false`: tryb reguł, bez połączeń poza własnymi kontenerami (`README.md`).

Wizual: trzy karty obok siebie z fragmentem `.env` każdej: „Tryb reguł” (`LLM_ENABLED=false`), „EdenAI UE” (`LLM_BASE_URL=https://api.eu.edenai.run/v3`), „Lokalny llama-server” (`LLM_BASE_URL=http://host:8080/v1`). Strzałka z podpisem „ten sam kod”.

### Slajd 7. Bezpieczeństwo i licencje

- Plik tylko w pamięci: `/tmp` w `tmpfs`, w logach tylko SHA-256 i rozmiar (`CLAUDE.md`, zasada 3; `compose.yaml`).
- Walidacja uploadu: rozmiar, nazwa, rozszerzenie, **sygnatura treści**; pliki z makrami odrzucane; błędy `application/problem+json` (413, 415) (`ARCHITECTURE.md`, 9; `api/src/formcompiler/upload.py`).
- Kontenery: użytkownik bez uprawnień, system plików tylko do odczytu, `cap_drop: ALL`, jeden opublikowany port na `127.0.0.1`, Tika bez wyjścia do internetu, limit 10 przesłań na minutę na IP (`README.md`, „Uruchomienie”; `web/nginx.conf`).
- Bramka licencyjna: 50 zależności Pythona, 9 npm w aplikacji, 141 npm deweloperskich; wagi OCR i modelu na Apache-2.0 (`research/09-licencje.md`).
- Dwa świadome wyjątki MPL-2.0, przechodnie i niezmienione: `certifi`, `tqdm` (D26, `research/09-licencje.md`).

Wizual: z lewej schemat trzech kontenerów z sieciami (`ARCHITECTURE.md`, sekcja 4), z prawej wynik `python3 devtools/check_licenses.py` w terminalu.

### Slajd 8. Koszt i wdrożenie

- **ok. 0,001 USD za formularz** przez EdenAI; formularz 8: 10,6 tys. tokenów wejścia + 6,3 tys. wyjścia = 0,0012 USD (`README.md`, „Koszt i czas”).
- Tryb reguł: 0,05–2 s na PDF; OCR zdjęcia 16 stron: 15 s na M1 Pro, 21 s na serwerze z 8 rdzeniami (`README.md`, „Koszt i czas”).
- Lokalny `llama-server`: zero kosztu za wywołanie; czasu na sprzęcie COI nie mierzyliśmy (`README.md`). `TODO`, jeśli zdążymy: pomiar na CPU.
- Wdrożenie: `docker compose up -d --build --wait`, trzy kontenery, sprawdzone na czystym Debianie 13 amd64 (`README.md`, „Uruchomienie”).
- Pasuje do AI Hub COI: model podmienia się konfiguracją, nie kodem (`PLAN.md`, „Jak wygrywamy”).

Wizual: tabela trzech wariantów (reguły / EdenAI / lokalny model) z kolumnami: koszt za formularz, czas, wymagania sprzętowe, dane opuszczają infrastrukturę (nie / tak, endpoint UE / nie).

### Slajd 9. Rozszerzenia I–VI

| Rozszerzenie | Co pokazujemy | Źródło |
|---|---|---|
| I. Słowniki i dane inicjalne | słowniki `Kraje`, `TERYT_4G_DOWODOWY`, `TERYT_DOWODOWY`; 54 pola z rejestrów (36 `MLPZ`, 18 `PESEL`) w 6 wynikach | `outputs/*.json`, skrypt w sekcji 5 |
| II. Nowy słownik | propozycje w raporcie: formularz 7 (1), formularz 9 (4), np. „Rodzaj wniosku” | `dictionaries.propose` na `outputs/*.json`, sekcja 5 |
| III. Zależności między polami | 116 warunków `SHOW` w 6 wynikach (np. „Użyczenie” odsłania pole na zgodę osoby odpowiedzialnej w formularzu 4) | `outputs/*.json` |
| IV. Upload i podgląd JSON | stanowisko urzędnika, kolejka, zakładka JSON z pobraniem | `web/src/workspace/` |
| V. Podgląd e-formularza | renderer z warunkami JSONata na żywo, trasa `/podglad` dla dowolnego JSON-a | `web/src/renderer/`, D23 |
| VI. Walidacje | 90 walidatorów w 6 wynikach (84 `REQUIRED`, 3 `ZIP_CODE`, po 1 `PESEL`, `NIP`, `REGON`); wektory wspólne dla `pytest` i Vitest | `outputs/*.json`, `fixtures/validators.json` |

Wizual: siatka 2 × 3 z ikoną i jednym zdaniem na rozszerzenie; tabela trafia do notatek prelegenta.

### Slajd 10. Co dalej z COI

- Próbny import wyników w Generatorze Formularzy u COI (jeszcze nie zrobiony; `PLAN.md`, „Pierwsze kroki”, pkt 2).
- Lokalny `llama-server` na infrastrukturze COI i pomiar czasu na CPU i GPU.
- Lepsze nazewnictwo pól na nowych blankietach: ścisłe pokrycie 64% to dziś główna słabość (`research/10`).
- Pełne słowniki i pętla zwrotna od urzędników (poprawki jako nowe przykłady few-shot).
- Kod otwarty, zależności bez copyleftu: gotowy do przejęcia przez COI.

Wizual: oś czasu w trzech krokach (pilotaż, lokalny model, skala). Na dole link do repozytorium i do demo `formularze.heckyeah.pl` (D24).

## 2. Scenariusz filmu (do 3:00)

Nagranie: stos `docker compose` lokalnie, przeglądarka 1366 px (rzutnik, F6 w `PLAN.md`), tryb modelu z `.env`. Lektor czyta tekst z kolumny „Głos”; ok. 130 słów na minutę. Pliki przygotowane wcześniej w jednym katalogu bez przecinków w nazwach.

| Czas | Na ekranie | Głos |
|---|---|---|
| 0:00–0:15 | Skan blankietu formularza 8 (deklaracja odpadowa) z kratkami i wykropkowaniami; logo Biurokratki. | „Urzędy publikują tysiące wniosków jako PDF-y i skany. Każdy trzeba dziś ręcznie przeprojektować na e-formularz. Biurokratka robi to w kilkadziesiąt sekund.” |
| 0:15–0:35 | Stanowisko pod `http://127.0.0.1:8080`. Przeciągamy PDF formularza 4 („Wniosek o wynajęcie świetlicy.pdf”) i JPG tego samego formularza. Kolejka: „Analizuję plik 1 z 2… Trwa to N s”. | „Wgrywam blankiet w PDF i zdjęcie tego samego wniosku. Pliki trafiają do kolejki i są analizowane po kolei. Plik nie jest zapisywany na serwerze, istnieje tylko w pamięci na czas żądania.” |
| 0:35–1:05 | Widok „Dokument i formularz”. Z lewej tekst dokumentu z numerami linii, z prawej podgląd e-formularza. W „Pokaż źródło pola” wybieramy pole przedmiotu wniosku; linie źródłowe się podświetlają, pod spodem „Pewność rozpoznania: …%”. | „Urzędnik nie musi ufać modelowi na słowo. Wybiera pole, a system pokazuje, z których linii blankietu powstało i jak pewne jest rozpoznanie. Pola poniżej siedemdziesięciu procent są oznaczone do sprawdzenia.” |
| 1:05–1:35 | Podgląd e-formularza, strona „Szczegóły wniosku”: wybór „Użyczenie” w polu typu najmu odsłania pole na zgodę osoby odpowiedzialnej. Potem strona „Dane”: zmiana kraju z „Polska” na inny zamienia listę TERYT na pola tekstowe. „Dalej” bez wymaganych pól pokazuje podsumowanie błędów. | „To nie jest przepisany blankiet, tylko formularz według standardów COI: sekcje predefiniowane, dane z rejestrów, słowniki i warunki. Wybór „użyczenie” odsłania nowe pole. Adres w Polsce korzysta z TERYT. Walidacja działa przy przejściu dalej.” |
| 1:35–1:55 | Zakładka „Raport”: tryb „model językowy (flexai/Qwen3.5-9B@eu)”, 0 błędów lintera, czasy etapów. Zakładka „JSON”: przycisk „Pobierz JSON”, komunikat „Pobrano plik JSON.” | „Raport pokazuje tryb, model i wynik kontroli. Model zwraca tylko krótką reprezentację pól, a końcowy JSON składa kod i sprawdza linter. Plik pobieramy jednym kliknięciem, gotowy do importu.” |
| 1:55–2:05 | Wynik dla JPG: ten sam tytuł i podobna liczba pól. | „Zdjęcie daje ten sam formularz. Sprawdziliśmy pięćdziesiąt trzy pliki we wszystkich ośmiu formatach: każdy przeszedł bez błędu lintera.” |
| 2:05–2:20 | Wgrywamy `zly-plik.pdf` (tekst z rozszerzeniem `.pdf`). W kolejce: „Błąd”, komunikat „Treść pliku nie odpowiada jego rozszerzeniu.” Obok terminal: `curl` zwraca 415 `application/problem+json`. | „Plik, który udaje PDF, zostaje odrzucony. Sprawdzamy sygnaturę treści, nie tylko rozszerzenie. Błędy mają standardowy format problem plus JSON.” |
| 2:20–2:40 | Terminal: w `.env` `LLM_ENABLED=false`, `docker compose up -d --force-recreate --wait api`, `curl /health` zwraca `"llm_enabled":false`. Ponowny upload PDF: Raport pokazuje tryb „reguły”, JSON gotowy w ok. sekundę. | „Bez sieci albo bez modelu usługa działa dalej w trybie reguł. To jedna zmienna. Model to otwarty Qwen na licencji Apache, a lokalny serwer podmieniamy adresem w konfiguracji.” |
| 2:40–3:00 | Slajd końcowy: „0,001 USD za formularz”, „53/53 formatów”, „licencje bez copyleftu”, link do repozytorium i do demo. | „Około jednej dziesiątej centa za formularz, trzy kontenery, licencje bez copyleftu. Biurokratka jest gotowa do pilotażu w COI.” |

Uwagi do nagrania:

- Ujęcie „zdjęcie z telefonu”: próbki JPG z `Docs/` to skany, nie zdjęcia. `TODO`: nagrać prawdziwe zdjęcie telefonem (np. formularz 4 wydrukowany), jeśli powstanie `research/11-odpornosc-ocr.md` z wynikami na takich próbkach; inaczej w głosie mówimy „skan”, nie „zdjęcie z telefonu”.
- Czas ujęcia z PDF w trybie modelu: formularz 4 trwał 5,3 s (`outputs/README.md`). Zdjęcie formularza 4 w trybie reguł: 3,5 s (`research/08`). Licznika nie trzeba przyspieszać.
- Nie pokazujemy klucza `LLM_API_KEY` ani treści `.env` poza linią `LLM_ENABLED`.
- Plik `zly-plik.pdf` tworzymy poleceniem `printf 'to nie jest PDF\n' > zly-plik.pdf`. Rozszerzenie spoza listy (np. `.txt`) odrzuca już przeglądarka (`web/src/api/validate.ts`), więc 415 z serwera pokazuje tylko plik z poprawnym rozszerzeniem i złą treścią.

## 3. Demo na żywo w finale (5 minut)

### Przed wejściem na salę (najpóźniej 15 minut wcześniej)

```sh
cd hacknation2026
cp /bezpieczne/miejsce/.env .env           # klucz EdenAI; bez .env działa tryb reguł
docker compose up -d --build --wait        # web, api, tika: healthy
docker compose ps
curl http://127.0.0.1:8080/health          # {"status":"ok","llm_enabled":true}
```

Otwórz `http://127.0.0.1:8080` (stanowisko) i w drugiej karcie `http://127.0.0.1:8080/podglad`. Rozgrzej usługę jednym plikiem (pierwsze żądanie ładuje OCR i Tikę). Limit nginx to 10 przesłań na minutę na IP, także z `127.0.0.1` (`README.md`, `web/nginx.conf`): nie wrzucaj więcej niż kilku plików naraz.

Przygotowane pliki w jednym katalogu, bez przecinków w nazwach:

| Plik | Po co | Spodziewany czas |
|---|---|---|
| `Wniosek o wynajęcie świetlicy.pdf` (`Docs/4. …`) | główny przypadek, warunek „Użyczenie” w podglądzie | 5,3 s w trybie modelu (`outputs/README.md`) |
| `Wniosek o wynajęcie świetlicy.jpg` (`Docs/4. …`) | raster i OCR | 3,5 s w trybie reguł (`research/08`); w trybie modelu `TODO` |
| `zly-plik.pdf` | przypadek negatywny, 415 | natychmiast |
| nowe pliki jury | główny punkt finału | PDF: sekundy; zdjęcie wielostronicowe: do ok. 21 s OCR (`README.md`) plus model |

### Przebieg (5:00)

| Czas | Co robimy |
|---|---|
| 0:00–0:30 | Jedno zdanie o rozwiązaniu, slajd 3 (potok). |
| 0:30–2:00 | Plik od jury (albo PDF formularza 4). Kolejka, potem „Dokument i formularz”: pochodzenie pola i pewność. |
| 2:00–3:00 | Podgląd e-formularza: warunek, walidacja przy „Dalej”, zakładka Raport, pobranie JSON-a. |
| 3:00–3:30 | `zly-plik.pdf` → „Treść pliku nie odpowiada jego rozszerzeniu.” (415). |
| 3:30–4:15 | Przełączenie na tryb reguł (polecenia niżej) i ponowny upload. |
| 4:15–5:00 | Pytania. |

Przełączenie na tryb reguł:

```sh
perl -pi -e "s/^LLM_ENABLED=.*/LLM_ENABLED=false/" .env   # działa tak samo na macOS i Linuksie
docker compose up -d --force-recreate --wait api
curl http://127.0.0.1:8080/health                         # "llm_enabled":false
```

Powrót: to samo z `LLM_ENABLED=true`.

### Gdy coś pójdzie nie tak

| Sytuacja | Co robimy |
|---|---|
| Brak sieci albo EdenAI nie odpowiada | Usługa sama wraca do reguł przy błędzie modelu (`README.md`, „Model językowy”), ale może czekać do `LLM_TIMEOUT_S` (120 s w `.env.example`). Nie czekamy: przełączamy na `LLM_ENABLED=false` (wyżej). Mówimy: „to jest właśnie tryb awaryjny”. |
| Model zapętla się i odpowiedź trwa długo | Jak wyżej. Znany problem z pętlami powtórzeń (`PLAN.md`, „Znane problemy”; B1 częściowo poprawione w `5b7ae7e`). |
| `docker compose up --build` nie buduje (brak sieci do obrazów bazowych) | Obrazy zbudować wcześniej; na sali `docker compose up -d --wait` bez `--build`. Zapas: `docker load -i` z archiwów `docker save` (B8). `TODO`: ścieżka do plików `.tar` na nośniku. |
| API nie wstaje | Przycisk „Wczytaj dane przykładowe” na stanowisku działa bez usługi (dane z referencji 5, `web/src/api/demo.ts`); `/podglad` renderuje referencyjne JSON-y 1 i 5. Do tego gotowe `outputs/*.json` wczytane w `/podglad`. |
| Laptop zawodzi | Publiczne demo `https://formularze.heckyeah.pl` (D24; potrzebna sieć), potem film. |
| Plik jury się nie czyta (422) | Pokazujemy komunikat „Dokument nieczytelny” jako poprawną obsługę błędu i przechodzimy do pliku z formularza 4. |

### Trzy najbardziej prawdopodobne pytania jury

**1. „Regulamin wymaga licencji bez copyleftu. Skąd MPL-2.0?”**
Dwie zależności przechodnie: `certifi` (sam zbiór certyfikatów CA, ciągnie go `httpx`) i `tqdm` (ciągnie go `rapidocr`). MPL-2.0 to copyleft na poziomie pliku: dotyczy tylko zmienionych plików samej biblioteki, nie naszego kodu, a my ich nie zmieniamy. Bez nich nie ma klienta HTTP ani OCR. Bramka licencyjna przepuszcza tylko te dwa pakiety z ostrzeżeniem i zatrzymuje każdy inny MPL, LGPL i GPL (D26, `research/09-licencje.md`). Reszta: MIT, BSD, Apache-2.0, ISC; fonty na OFL (D25).

**2. „Wołacie EdenAI. To przecież zewnętrzne API.”**
Mentor COI potwierdził, że wolno korzystać z modelu w chmurze przez API, jeśli model jest dostępny w wersji otwartej i da się go postawić na własnej infrastrukturze (`CLAUDE.md`, zasada 2). Qwen3.5-9B ma otwarte wagi na Apache-2.0. Kod nie zawiera nic specyficznego dla EdenAI, zdalny adres wymaga jawnej flagi `LLM_ALLOW_REMOTE=true`, a bez modelu usługa działa w trybie reguł bez żadnej sieci. Pokazaliśmy to przed chwilą.

**3. „Jak to postawić bez EdenAI, u nas?”**
`llama-server` z llama.cpp (MIT) z tym samym modelem w GGUF Q4_K_M (ok. 5,5 GB), na CPU albo karcie z 16 GB, z wyłączonym trybem rozumowania. W `.env` zmieniamy `LLM_BASE_URL` na `http://host:8080/v1` i `LLM_MODEL`; adresy prywatne nie wymagają `LLM_ALLOW_REMOTE`. Kod się nie zmienia (`README.md`, „Docelowo: lokalny llama-server”). Uczciwie: tej konfiguracji nie testowaliśmy w czasie hackathonu, bo laptop demonstracyjny ma 16 GB RAM.

Pytania zapasowe:

- *„Dlaczego model nie generuje całego JSON-a?”* Ok. 15 tys. tokenów wyjścia, myli identyfikatory i odwołania JSONata; u nas model pisze krótki IR, a poprawność gwarantuje kod (`ARCHITECTURE.md`, sekcja 2, podejście A).
- *„Na ile to trafne?”* Szkielet zgodny z referencją w 14 z 14 przebiegów; pola: 64% ścisłego dopasowania etykiet, ok. 90% znaczeniowo, mała próba 11 pól (`research/10`).
- *„Wynik się powtarza?”* `temperature` 0, stałe ziarno i UUID v5 z `techName`, ale endpoint EdenAI nie trzyma ziarna, więc tryb modelu bywa niepowtarzalny; tryb reguł jest powtarzalny (`research/10`; `PLAN.md`, „Znane problemy”).

## 4. Otwarte TODO

1. Zrzuty ekranu do slajdów 1, 4 i 7 z działającego stosu (F7 w `PLAN.md`).
2. `research/11-odpornosc-ocr.md` jeszcze nie istnieje. Gdy powstanie: dopisać liczby odporności OCR na slajd 5 lub 8 i zdecydować o ujęciu „zdjęcie z telefonu” w filmie.
3. Czas formularza 4 z JPG w trybie modelu: niezmierzony (w `research/08` tylko tryb reguł).
4. Ścieżka do archiwów `docker save` na nośniku (B8).
5. Czas lokalnego `llama-server`: niezmierzony (`README.md`); na slajdzie 8 bez liczby.
6. Jeśli do 07:00 wejdą zmiany frontendu z `PLAN.md` (F2: lista pól do sprawdzenia, F3: klik w linię zaznacza pole), opisać je na slajdzie 4 i w filmie (0:35–1:05). Stan opisany tu: wybór pola z listy rozwijanej i podświetlenie linii.
7. Przed eksportem PDF ponownie uruchomić polecenia z sekcji 5; liczby testów rosną z każdym scaleniem.

## 5. Źródła liczb

| Liczba | Wartość | Źródło lub polecenie |
|---|---|---|
| Macierz formatów | 53 pliki, 53 × HTTP 200, 0 błędów lintera; najwolniejszy 20,9 s (JPG formularza 9, 16 stron); tryb reguł, 8 rdzeni amd64 | `research/08-macierz-formatow.md` (2026-11-21 22:22 UTC). `PLAN.md` podaje 54 pliki; obowiązuje raport 08. |
| Wyniki w `outputs/` | 6 formularzy, tryb `llm`, `flexai/Qwen3.5-9B@eu`, 0 błędów lintera; pola 23 / 25 / 70 / 31 / 109 / 83; czas 4936 / 5270 / 11834 / 7480 / 43309 / 53748 ms (formularze 3, 4, 6, 7, 8, 9) | `outputs/README.md` |
| Pokrycie referencji | model `loo` 64% (7/11), model `full` 73–82%, reguły 9% (1/11); ręcznie ok. 10/11 w trybie modelu; szkielet zgodny w 14/14 przebiegów | `research/10-pokrycie-referencji.md` |
| Licencje | 50 zależności Pythona, 9 npm w aplikacji, 141 npm deweloperskich; wyjątki MPL-2.0: `certifi`, `tqdm` | `research/09-licencje.md` |
| Koszt | ok. 0,001 USD za formularz; formularz 8: 10,6 tys. + 6,3 tys. tokenów = 0,0012 USD | `README.md`, „Koszt i czas” |
| Czasy reguł i OCR | PDF 0,05–2 s; OCR 16 stron: 15 s M1 Pro, 21 s serwer | `README.md`, „Koszt i czas” |
| Reguły lintera | `L001`–`L025` (błędy), `L101`–`L111` (ostrzeżenia) | `ARCHITECTURE.md`, 5.7 |
| Testy API | 468 zaliczone, 3 pominięte, 24,5 s | `cd api && uv run pytest -p no:warnings -o addopts="" -q` (2026-11-21 ok. 23:50, commit `a422cc7`; `addopts = "-q"` w `pyproject.toml` ukrywa podsumowanie przy `-q`) |
| Testy web | 106 testów w 5 plikach, wszystkie zaliczone | `cd web && npm ci && npm test` (to samo uruchomienie) |
| Rozszerzenia I, III, VI | 54 pola `EXTERNAL_SYSTEM` (36 `MLPZ`, 18 `PESEL`); 116 warunków `SHOW`; 90 walidatorów (84 `REQUIRED`, 3 `ZIP_CODE`, po 1 `PESEL`, `NIP`, `REGON`); słowniki `Kraje`, `TERYT_4G_DOWODOWY`, `TERYT_DOWODOWY` | skrypt niżej na `outputs/*.json` |
| Rozszerzenie II | propozycje słowników: formularz 7: 1, formularz 9: 4, pozostałe: 0 | `dictionaries.propose` na `outputs/*.json`, skrypt niżej |

Skrypt do liczb rozszerzeń (z katalogu `api/`):

```sh
uv run python - <<'EOF'
import collections, glob, json
from formcompiler import dictionaries, schema

show = ext = 0
val = collections.Counter()
src = collections.Counter()
for path in sorted(glob.glob("../outputs/*.json")):
    data = json.load(open(path))
    stack = [q["field"] for tab in data["tabs"] for q in tab["questions"]]
    while stack:
        f = stack.pop()
        show += sum(1 for s in f.get("states", []) if s.get("type") == "SHOW")
        val.update(f.get("validation", []))
        if f.get("defaultValueType") == "EXTERNAL_SYSTEM":
            src[f["defaultValue"].split(".")[0]] += 1
        stack += [q["field"] for q in f.get("repeatingSectionGrid", [])]
    props = dictionaries.propose(schema.Form.model_validate(data))
    print(path.split("/")[-1][:2], [p.name for p in props])
print("SHOW", show, "validation", sum(val.values()), dict(val), "external", dict(src))
EOF
```
