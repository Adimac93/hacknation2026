# 05. EdenAI, nowe ustalenia i decyzje do podjęcia

Stan na 2026-11-21, 14:30. Dokument zbiera ustalenia, których nie ma w raportach 02–04, oraz decyzje potrzebne przed pierwszym kamieniem milowym (15:30).

## 0. Rozstrzygnięcia (2026-11-21, ok. 15:10)

| Nr | Rozstrzygnięcie |
|---|---|
| D1 | Python 3.14 (Rust rozważony i odrzucony: spoza listy preferowanej przez COI, niedojrzała JSONata, PDF na niskopoziomowym pdfium) |
| D11 | EdenAI jest jedynym źródłem modelu na hackathonie. Dodatkowo model czołowy w `devtools/` do złotych IR i jako sufit jakości |
| D12 | Few-shot tylko z referencji 1 i 5; formularze 3–9 wyłącznie do oceny |
| D13 | Demo na M1 Pro 16 GB |
| D14 | `docker compose up` bez usługi modelu; domyślnie tryb reguł |
| D15 | OCR: Tesseract 5 z `pol` |
| D16 | Frontend: upload, drzewo JSON, podgląd e-formularza z JSONata, źródło pola jako podświetlenie linii |
| D17 | Jedna osoba + agenci AI |
| D18 | Rozszerzenia bez względu na wielkość liter; `.jpe` przyjmowane |
| D19 | Przyjęta rekomendacja A (tylko `wobbegong-ci`); do zmiany na życzenie |
| D20 | Model: `Ministral-3-8B-Instruct-2512`, zapas `Qwen3.5-9B`; porównanie przez API na formularzach 1 i 5 |
| D21 | Modelu nie uruchamiamy lokalnie w czasie hackathonu, także na obronie. Na obronie EdenAI |

**Przyjęte ryzyko (D21 + obrona przez EdenAI).** Treść zadania (pkt 5) zakazuje zależności od zewnętrznych API i SaaS w rozwiązaniu. Model jest open-weight, więc zakaz „modeli dostępnych wyłącznie przez API” nie jest naruszony, ale samo wołanie EdenAI w działającej usłudze może zostać uznane za zewnętrzne API. Łagodzenie: pytanie do mentorów w pierwszej godzinie; kod bez niczego specyficznego dla EdenAI; tryb reguł włączany jedną zmienną (`LLM_ENABLED=false`); README pokazuje lokalny `llama-server` z tym samym modelem jako konfigurację docelową.

## 1. Nowe ustalenia

| # | Ustalenie | Skutek |
|---|---|---|
| U1 | Treść zadania (pkt 5) wprost dopuszcza modele dostępne tylko przez API **do pisania, testowania i projektowania kodu**. Zakaz dotyczy wyłącznie działającego rozwiązania. Pkt 7 wymienia „tokeny do wykorzystania w pracy nad rozwiązaniem (dla pierwszych 20 zespołów)”. Kredyt EdenAI to najpewniej właśnie te tokeny. | EdenAI wolno używać w narzędziach deweloperskich. Nie wolno go użyć w `api/`, w obrazie Dockera ani w ścieżce żądania. |
| U2 | Laptop, na którym pracujemy, to **Apple M1 Pro, 16 GB**, a nie M4, jak zakładają `CLAUDE.md` i `ARCHITECTURE.md`. M1 Pro ma przepustowość pamięci ok. 200 GB/s, a bazowy M4 ok. 120 GB/s. | Generowanie tokenów na M1 Pro powinno być ok. 1,5 raza szybsze niż na M4 (szacunek z przepustowości, do sprawdzenia `llama-bench`). Trzeba ustalić, który laptop jest maszyną demo (decyzja D13). |
| U3 | Wszystkie PDF-y z `Docs/` mają warstwę tekstową (od 1 do 16 stron, formularz 9 ma ok. 37 tys. znaków). Pliki PNG i JPG to czyste rendery tych PDF-ów w 200 DPI. | Dla próbek mamy darmową prawdę wzorcową OCR: tekst z PDF. Błąd znakowy (CER) OCR liczymy lokalnie, bez EdenAI. Próbki nie przypominają jednak prawdziwych skanów ani zdjęć. |
| U4 | Formularz 7 ma rozszerzenie `.JPE`, a kilka plików ma rozszerzenia wielkimi literami (`.PDF`, `.PNG`, `.DOC`, `.ODS`). Treść zadania wymienia tylko `.jpg` i `.jpeg`. | Walidacja rozszerzenia musi ignorować wielkość liter. Przyjęcie `.jpe` wymaga decyzji (D18). |
| U5 | Raport `research/01` (OCR i parsowanie) nie istnieje, więc decyzja D5 jest otwarta. | Decyzja D15 poniżej. |
| U6 | Docker Desktop nie działa na tym laptopie, a `llama-server` i Ollama nie są zainstalowane. Wolne miejsce na dysku: ok. 104 GB. | Instalacja `llama.cpp` (`brew install llama.cpp`) i pobranie wag to pierwsze zadania w tle. |

## 1a. Serwer Proxmox (PVE)

Dostęp: `ssh pve` (Proxmox VE 8.4, host 172.16.0.2). Zasoby: AMD Threadripper 1920X (12 rdzeni, 24 wątki, AVX2, bez AVX-512), 62 GB RAM, Radeon RX 580 8 GB, ok. 785 GB wolnego na `local-lvm`. Ma dostęp do internetu.

Zasady użycia ustalone z właścicielem:

- tylko **nowe** kontenery LXC; istniejących (100–116) nie ruszamy,
- **żadnych modeli AI na PVE**: ani LLM, ani VLM. PVE nigdy nie jest `LLM_BASE_URL` w demo,
- docelowa aplikacja hostuje model lokalnie, czyli w compose obok usługi albo natywnie na laptopie demo (profil Metal). Architektura już to zakłada; PVE niczego tu nie zmienia.

Utworzony kontener:

| VMID | Nazwa | Adres | Zasoby | Zawartość | Cel |
|---|---|---|---|---|---|
| 104 | `wobbegong-ci` | 172.16.0.62 (DHCP), `ssh root@172.16.0.62` | 8 rdzeni, 16 GB RAM, 64 GB dysku | Debian 13, Docker 26.1, Compose 2.26, buildx, git; unprivileged z `nesting` i `keyctl` | czysta maszyna **amd64** do testu `docker compose up --build` |

Laptopy zespołu to arm64, a maszyna jury najpewniej amd64. LXC zamyka ryzyko z `PLAN.md` („Docker nie buduje się na obcej maszynie”) bez czekania do 07:00: test na amd64 można puszczać po każdym większym commicie.

Skutek dla compose: usługa `llm` musi dać się wyłączyć (profil compose `llm` albo `LLM_ENABLED=false`), bo na PVE stos uruchamiamy zawsze bez modelu. To przy okazji sprawdza tryb reguł, czyli ścieżkę awaryjną.

## 2. Co oferuje EdenAI (sprawdzone 2026-11-21)

- Bramka zgodna z OpenAI: `https://api.edenai.run/v3/chat/completions` (endpoint UE: `https://api.eu.edenai.run/v3`), nagłówek `Authorization: Bearer …`, modele w formacie `provider/model`, np. `anthropic/claude-sonnet-latest`, `openai/gpt-5.5`, `vertex/gemini-flash-latest`. Lista modeli: `GET /v3/models`.
- Structured output: `response_format` z `json_schema` i `strict` dla OpenAI, Anthropic i Google.
- OCR: synchroniczny i asynchroniczny (wielostronicowy PDF) od Amazon, Google, Microsoft i Mistral, ok. 1–1,5 USD za 1000 stron. Ekstrakcja tabel: 10–65 USD za 1000 stron. Obsługi języka polskiego nie potwierdziłem.
- Cennik: ceny dostawców bez marży, 5,5% opłaty przy zakupie kredytów.
- Dane: według dokumentacji EdenAI domyślnie nie przechowuje treści żądań i nie trenuje na nich. Polityki poszczególnych dostawców są osobno (nie czytałem).

Źródła: <https://www.edenai.co/pricing>, <https://www.edenai.co/docs/v3/llms/chat-completions.md>, <https://www.edenai.co/docs/v3/llms/structured-output.md>, <https://www.edenai.co/docs/v3/expert-models/features/ocr/ocr.md>, <https://www.edenai.co/docs/v3/data-governance/data-retention.md>.

**Budżet nie jest ograniczeniem.** Jedno wywołanie modelu czołowego na jeden formularz (ok. 15 tys. tokenów wejścia, 5 tys. wyjścia) to ok. 0,10–0,20 USD. 9 formularzy × 3 modele × 5 iteracji promptu mieści się w ok. 30 USD. Ograniczeniem jest czas ludzi na przegląd wyników.

## 2a. Development bez modeli self-hostowanych (decyzja zespołu, 14:50)

Ustalenie: w trakcie developmentu **nie uruchamiamy żadnych modeli self-hostowanych** (ani na laptopach, ani na PVE). Model wołamy przez EdenAI. Docelowa aplikacja nadal hostuje model lokalnie.

Skutek: wynik z API musi przewidywać zachowanie modelu lokalnego. Dlatego w developmencie używamy **tych samych wag open-weight**, które pojadą w obrazie, a nie modelu czołowego. EdenAI zwraca w `GET /v3/models` pola `open_weights` i `hugging_face_id`, więc zgodność wag da się sprawdzić automatycznie.

**Bielika i PLLuM nie ma w EdenAI** (sprawdzone na liście 1298 modeli). Modele open-weight z EdenAI, które po kwantyzacji Q4 zmieszczą się na laptopie z 16 GB:

| Model (HF) | Parametry | Licencja (HF) | Q4_K_M, szac. | EdenAI, endpoint UE | Cena USD za 1 mln tokenów (wej./wyj.) | Uwagi |
|---|---|---|---|---|---|---|
| `mistralai/Ministral-3-8B-Instruct-2512` | 8,9 mld | Apache-2.0 | ok. 5,5 GB | `mistral/ministral-8b-2512@eu`, ZDR | 0,165 / 0,165 | europejski dostawca; `seed` i `response_format` na liście parametrów; wejście tekst i obraz |
| `mistralai/Ministral-3-14B-Instruct-2512` | 13,9 mld | Apache-2.0 | ok. 8,5 GB | `mistral/ministral-14b-2512@eu`, ZDR | 0,22 / 0,22 | najlepsza jakość z tej listy, ale ciasno na 16 GB obok Dockera |
| `Qwen/Qwen3.5-9B` | 9,7 mld | Apache-2.0 | ok. 6 GB | `flexai/Qwen3.5-9B@eu`, ZDR | 0,10 / 0,15 | lista parametrów w EdenAI pusta, `seed` niepotwierdzony; tryb rozumowania trzeba wyłączyć |
| `google/gemma-4-26B-A4B-it` | 25,8 mld (MoE) | Apache-2.0 | ok. 15 GB | `flexai/gemma-4-26B-A4B-it@eu` | 0,067 / 0,29 | **nie mieści się** w 16 GB |

ZDR oznacza zero data retention według metadanych EdenAI. Rozmiary Q4 to szacunek z liczby parametrów. Oficjalnych plików GGUF dla tych modeli jeszcze nie sprawdziłem. Oba Ministrale i Qwen przyjmują też obraz, więc ten sam model może później obsłużyć skany jako ścieżka awaryjna (opcja D z `ARCHITECTURE.md`) bez drugiego modelu w pamięci.

Koszt developmentu przy tych cenach jest pomijalny: 1000 pełnych przebiegów formularza (ok. 20 tys. tokenów) to ok. 3–4 USD.

Zasady techniczne:

- `LLM_ALLOW_REMOTE=true` tylko w lokalnym `.env`; domyślnie `false`, a obraz i `compose*.yaml` zawsze wskazują lokalny `llama-server`,
- klient LLM używa tylko części API wspólnej dla EdenAI i `llama-server`: `messages`, `temperature`, `seed`, `max_tokens`, `response_format` z `json_schema`; bez `tools` i parametrów specyficznych dla dostawcy,
- wymuszanie schematu działa inaczej u dostawcy API niż w `llama-server` (gramatyka), więc walidacja Pydantic po stronie klienta zostaje obowiązkowa,
- test w `wobbegong-ci` na PVE może korzystać z EdenAI albo działać w trybie reguł; modelu nie uruchamiamy tam nigdy.

## 3. Decyzje do podjęcia

Kolejność według pilności. Pierwsze cztery blokują pracę do 15:30.

### D11. Rola EdenAI

**Częściowo rozstrzygnięta (14:50):** EdenAI jest jedynym źródłem modelu w developmencie (sekcja 2a). Otwarte zostaje tylko, czy oprócz modelu docelowego używamy też modelu czołowego do złotych IR i jako sufitu jakości (punkty 1–2 poniżej).

| Opcja | Plusy | Minusy |
|---|---|---|
| **A. Tylko narzędzie deweloperskie: wyrocznia do ewaluacji i projektowania** (rekomendacja) | zgodne z pkt 5; daje wzorce dla 7 formularzy bez referencji; szybko odróżnia „zły prompt” od „za słabego modelu” | trzeba pilnować granicy między `devtools/` a `api/` |
| B. Nie używać | zero ryzyka wizerunkowego | ewaluacja tylko na 2 referencjach; wolniejsze strojenie promptów |
| C. Opcjonalny „tryb chmurowy” w usłudze | lepsza jakość | **narusza wymóg twardy nr 2**, dyskwalifikacja. Odrzucone. |

Zastosowania w opcji A, od najcenniejszego:

1. **Złote IR dla formularzy 3, 4, 6, 7, 8, 9.** Model czołowy przez EdenAI (`json_schema` z naszym modelem IR) proponuje IR, człowiek poprawia (ok. 15–20 min na formularz). Harness ocenia wtedy 8 formularzy zamiast 2.
2. **Sufit jakości dla promptów.** Ten sam prompt kroków A–C na modelu czołowym i na Bieliku. Jeśli model czołowy też się myli, poprawiamy prompt lub IR, a nie zmieniamy modelu.
3. **Dane statyczne projektowane z pomocą modelu**, przeglądane przez człowieka i commitowane jako zwykłe dane: mapa „urzędowa etykieta → prosty język”, słowa kluczowe → walidatory i atrybuty rejestrów, propozycja nowego słownika (rozszerzenie II).
4. OCR prawdziwych skanów (Textract lub Azure) jako prawda wzorcowa, tylko jeśli zdobędziemy skany lub zdjęcia telefonem. Dla próbek z `Docs/` to zbędne (U3).

Zasady niezależnie od opcji:

- kod wywołujący EdenAI leży w `devtools/`, poza `api/`, i nie trafia do żadnego obrazu Dockera,
- `outputs/` generuje wyłącznie nasza usługa (`CLAUDE.md`),
- wysyłamy tylko publiczne blankiety z `Docs/`, przez endpoint UE; klucz tylko w `.env`,
- w README jedno zdanie: „EdenAI służyło wyłącznie do ewaluacji w czasie tworzenia, zgodnie z pkt 5 treści zadania”,
- limit wydatków ustawiony w panelu EdenAI, np. 60 EUR, 40 EUR rezerwy.

Pytanie dodatkowe: czy `devtools/` zostaje w repozytorium (przejrzystość, powtarzalna ewaluacja), czy tylko lokalnie (juror nie znajdzie słowa „edenai” w kodzie)? Rekomendacja: zostaje, z opisem w README. Ukrywanie wygląda gorzej niż jawne użycie dozwolone regulaminem.

### D12. Które formularze wolno użyć do strojenia promptów

| Opcja | Plusy | Minusy |
|---|---|---|
| **A. Few-shot tylko z referencji 1 i 5; formularze 3–9 wyłącznie do oceny** (rekomendacja) | uczciwe liczby na slajdzie; prawdziwy obraz zachowania na nowych plikach z obrony | słabsze `outputs/` niż przy strojeniu pod nie |
| B. Złote IR formularzy 3–9 także jako przykłady few-shot | lepsze `outputs/` | model kopiuje przykłady; na obronie na nowych plikach wynik będzie gorszy niż w `outputs/`; liczby z harnessu tracą wartość |

Do tego warto zebrać 5–10 dodatkowych blankietów z BIP innych gmin (najlepiej skany i pliki DOC) jako zbiór „jak na obronie”. Bez etykiet albo z etykietami z D11.1.

### D13. Maszyna demo i budżet czasu odpowiedzi

Potrzebne dwie liczby, z których wynika wybór modelu:

- **który laptop jest maszyną demo** (ten M1 Pro czy M4 kolegi lub koleżanki z zespołu),
- **budżet czasu**: proponuję do 60 s dla formularza 1–2-stronicowego i do 5 min dla formularza 9.

Bez modeli self-hostowanych w developmencie (sekcja 2a) nie zmierzymy czasu przed próbą generalną. Czas szacujemy z rozmiaru: generowanie tokenów na Apple Silicon ogranicza przepustowość pamięci, więc model Q4 o rozmiarze ok. 5,5 GB daje na M1 Pro rząd 25–30 tok/s, a na bazowym M4 rząd 15–20 tok/s (szacunek, nie pomiar). Dlatego przy budżecie z tej decyzji bezpieczny jest model 8–9 mld parametrów, a 14 mld to ryzyko. Poprawić „M4” w `CLAUDE.md` i `ARCHITECTURE.md`, jeśli demo będzie na M1 Pro.

### D20. Model docelowy (zastępuje D3)

| Opcja | Plusy | Minusy |
|---|---|---|
| **A. Ministral-3-8B-2512, z Qwen3.5-9B jako drugim kandydatem; zwycięzca po porównaniu przez API na formularzach 1 i 5 (ok. 30 min, poniżej 1 USD)** (rekomendacja) | to, co mierzymy w developmencie, to dokładnie te wagi, które pojadą w obrazie; mieści się w 16 GB z zapasem; europejski dostawca z endpointem UE | rezygnujemy z narracji „polski model Bielik” |
| B. Ministral-3-14B-2512 | lepsza jakość | ok. 8,5 GB; czas na laptopie niepewny, a zmierzymy go dopiero na próbie generalnej |
| C. Bielik 11B v3.1 mimo braku w EdenAI | polski model, mocny argument dla COI (AI Hub) | w developmencie testujemy inny model niż ten w demo; o różnicy dowiemy się dopiero na próbie generalnej |

Bielik i PLLuM zostają jako opisany w README profil „do podmiany” (`LLM_MODEL`), bez deklaracji jakości, bo ich nie testowaliśmy.

### D21. Kiedy pierwszy przebieg z modelem lokalnym

Demo i obrona to zawsze model lokalny, więc musi się on uruchomić przynajmniej raz przed obroną.

| Opcja | Plusy | Minusy |
|---|---|---|
| **A. Jeden test dymny o północy (formularze 3 i 9, pomiar czasu), potem próba generalna o 07:00 i ponowne wygenerowanie `outputs/` lokalnie** (rekomendacja) | problem z czasem lub pamięcią wychodzi z 7-godzinnym zapasem; `outputs/` pochodzą z konfiguracji, którą oddajemy | 30 min pracy z lokalnym modelem przed zamrożeniem |
| B. Tylko próba generalna o 07:00 | ściśle trzyma zasadę „bez self-hostingu w developmencie” | jeśli model okaże się za wolny, zostają 2,5 h na zmianę modelu |
| C. `outputs/` zostają z EdenAI | zero pracy lokalnej | `outputs/` nie pochodzą z oddawanej usługi; łamie zasadę z `CLAUDE.md` |

### D14. Domyślny profil `docker compose up` na obcej maszynie (CPU)

Jury może zbudować projekt u siebie, bez Metal i bez GPU. Model 11B w kontenerze na CPU przetwarza prompt formularza 9 przez wiele minut.

| Opcja | Skutek |
|---|---|
| A. Bielik 11B także na CPU | najlepsza jakość, odpowiedź często po przekroczeniu budżetu, więc i tak wynik z reguł |
| **B. Bielik-Minitron-7B na CPU, Bielik 11B w profilu Metal i GPU** (rekomendacja) | rozsądny czas na CPU, jeden model w rodzinie, mniej pamięci |
| C. Domyślnie `LLM_ENABLED=false`, model włączany flagą | zawsze szybko, ale pierwsze wrażenie bez AI |

We wszystkich opcjach budżet czasu na żądanie i przejście na tryb reguł zostają bez zmian.

Pomiar czasu profilu CPU robimy na laptopie (Docker z limitem CPU i pamięci), nie na PVE, bo tam nie uruchamiamy modeli. Wynik z arm64 jest tylko przybliżeniem serwera x86 urzędu i tak go opisujemy w README.

### D15. OCR rastrów (zamyka D5)

| Opcja | Licencja | Plusy | Minusy |
|---|---|---|---|
| **A. Tesseract 5 z `pol` przez `pytesseract`** (rekomendacja) | Apache-2.0 (Tesseract, pytesseract), BSD (Leptonica) | sprawdzona polszczyzna, pakiet `apt` w `python:3.14-slim`, brak wag do wypiekania | słabszy na zdjęciach pod kątem; wymaga prostowania |
| B. `rapidocr` + `onnxruntime` (modele PP-OCRv5) | Apache-2.0 | dobre wykrywanie ramek tekstu, szybki | jakość polskich znaków niepotwierdzona; wagi trzeba wypiec w obrazie |
| C. VLM (Gemma 4 12B z `mmproj`) | Apache-2.0 | rozumie układ i pola wyboru | drugi duży model nie mieści się w 16 GB obok Bielika; wolny |

Kryterium rozstrzygające: CER na 8 próbkach PNG względem tekstu z PDF (U3) plus 3–4 degradacje (obrót, rozmycie, JPEG). Pomiar ok. 30 min. Jeśli Tesseract ma CER powyżej 3%, sprawdzamy opcję B.

### D16. Zakres frontendu

| Opcja | Nakład | Punkty |
|---|---|---|
| **A. Upload + drzewo JSON + podgląd e-formularza z JSONata; pochodzenie pól jako podświetlenie linii tekstu, bez ramek na PDF** (rekomendacja) | ok. 9–11 h | rozszerzenia IV i V, intuicyjność |
| B. A + pełny ekran weryfikacji z ramkami na renderze PDF | ok. 15–18 h | więcej za oryginalność, ryzyko dla terminu |
| C. Tylko upload i drzewo JSON | ok. 3 h | tylko rozszerzenie IV |

### D17. Skład zespołu i przydział torów

`PLAN.md` ma warianty na 2, 3 i 4 osoby. Potrzebne: liczba osób i kto bierze który tor (A kompilator, B ingest, C rozumienie, D produkt). Tor C najlepiej dać osobie, która obsłuży też `devtools/` z EdenAI, bo złote IR i harness to jedno zadanie.

### D18. Rozszerzenie `.jpe` i wielkość liter

Rekomendacja: rozszerzenia porównujemy bez względu na wielkość liter i przyjmujemy `.jpe` jako JPEG, bo organizator sam dostarczył taki plik. Zawartość zawsze sprawdzamy po sygnaturze, więc ryzyko jest zerowe. Zapisać w README jako świadomą decyzję.

### D19. Co jeszcze uruchamiać na PVE

Kontener `wobbegong-ci` już jest (sekcja 1a). Do decyzji, co dalej:

| Opcja | Plusy | Minusy |
|---|---|---|
| **A. Tylko `wobbegong-ci`: test budowania amd64, przebieg harnessu w trybie reguł, przygotowanie `docker save` dla amd64 na nośnik** (rekomendacja) | zamyka ryzyko „nie buduje się u jury”; odciąża laptop z 16 GB przy długich buildach | brak |
| B. A + osobny LXC z Tiką jako wspólną usługą deweloperską dla zespołu | laptop nie trzyma JVM w trakcie pracy, więcej RAM na model | adres sieciowy w konfiguracji deweloperskiej; w demo Tika i tak musi działać lokalnie w compose |
| C. A + self-hosted runner GitHub Actions w LXC | CI z testem amd64 przy każdym pushu | ok. 1 h konfiguracji; zwykłe runnery GitHub (też amd64) wystarczą do testów i lintów |

## 4. Pytania do mentorów (dopisać do listy w `ARCHITECTURE.md`, sekcja 14)

- Czy kredyt EdenAI to „tokeny do wykorzystania w pracy nad rozwiązaniem” z pkt 7 i czy ewaluacja wyników modelem z API mieści się w „testowaniu kodu”?
- Czy rozszerzenie `.jpe` ma być obsługiwane?
- Czy pliki na obronie będą prawdziwymi skanami lub zdjęciami, czy renderami jak w `Docs/`?

## 5. Zadania w tle do uruchomienia od razu

1. ~~`brew install llama.cpp` i pobranie wag~~: odwołane, bez modeli self-hostowanych w developmencie (sekcja 2a). Pobranie GGUF wybranego modelu przesuwa się na test dymny (D21).
2. Uruchomienie Docker Desktop i ustawienie limitu pamięci VM (np. 6 GB), żeby zostało miejsce na model natywny.
3. Klucz EdenAI do `.env` (`.env` jest już w `.gitignore`), limit wydatków w panelu.
4. ~~LXC amd64 z Dockerem na PVE~~: gotowe, `wobbegong-ci` (VMID 104, 172.16.0.62).
