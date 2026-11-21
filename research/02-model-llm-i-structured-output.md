# 02 — Lokalny model LLM/VLM, runtime i structured output

Stan na 2026-11-21. Wersje i licencje sprawdzone bezpośrednio w API Hugging Face, PyPI, Maven Central i w repozytoriach GitHub (szczegóły w „Źródła"). Liczby tokens/s są **szacunkami**, nie pomiarami.

## Rekomendacja

1. **Model domyślny: `Bielik-11B-v3.1-Instruct` (GGUF Q4_K_M, 6,72 GB, Apache-2.0, kontekst 32K, tool calling).** Polski model SpeakLeash + ACK Cyfronet AGH, wydany 2026-11-10, oficjalne GGUF/MLX/Ollama. Profil „szybki" z tej samej rodziny: `Bielik-Minitron-7B-v3.0-Instruct` (Q4_K_M 4,50 GB).
2. **Fallback: `google/gemma-4-12b-it` (Apache-2.0, Q4_K_M 7,12 GB + mmproj 0,18 GB, 256K, multimodalny).** Jeden model obsługuje też skany i zdjęcia.
3. **PLLuM-12B-instruct-2512 (Apache-2.0)** jako profil konfiguracyjny „model ministerialny", nie jako domyślny: brak oficjalnego GGUF, brak wyników na Open PL LLM Leaderboard, brak deklarowanego tool calling.
4. **Runtime: `llama-server` (llama.cpp, MIT) jako osobny kontener z endpointem OpenAI-compatible; adres w `LLM_BASE_URL`.** Na demo-Macu endpoint wskazuje natywny `llama-server` z Metal (albo Docker Model Runner). Fallback runtime: Ollama (MIT).
5. **Structured output: pipeline wieloetapowy z kompaktową reprezentacją pośrednią (IR); finalny JSON buduje kod deterministyczny.** Generowanie całego JSON-a jednym strzałem odpada z powodu czasu (ok. 15 tys. tokenów wyjścia).
6. **Tekst przed obrazem.** Model dostaje tekst + geometrię z parsera. VLM tylko jako ścieżka awaryjna dla skanów.
7. **Biblioteki: `openai` SDK (lub `httpx`) + Pydantic v2.** Outlines wykluczone: `requires_python <3.14`.

## 1. Modele

Rozmiary GGUF z API Hugging Face. Kolumna „M4 16 GB" to szacunek z przepustowości pamięci (pomiar referencyjny: Llama 3.1 8B Q4_K_M ≈ 21–23 tok/s na M4 16 GB).

| Model (wersja) | Licencja; open non-copyleft? | Kontekst | Dowody jakości PL | JSON / tools | Wizja | Q4_K_M / Q5_K_M | M4 16 GB (szac.) | Werdykt |
|---|---|---|---|---|---|---|---|---|
| **Bielik-11B-v3.1-Instruct** (2026-11-10) | Apache-2.0 ✔ | 32K | v3.0: 65,93 Open PL LLM Leaderboard; PLCC 71,83% (1. wśród open); CPTUB „language understanding" 3,91. Dla v3.1 brak opublikowanych liczb | Tool calling w szablonie GGUF; BFCL raportowane dla v3.0 | ✘ | 6,72 / 7,91 GB | mieści się; ~13–15 tok/s | **Domyślny** |
| Bielik-Minitron-7B-v3.0-Instruct | Apache-2.0 ✔ | nie zweryfikowano | 94,7% wyniku 11B na Open PL; CPTUB 3,83 | BFCL: 94,5% (multiple AST) | ✘ | 4,50 / 5,29 GB | ~20 tok/s | Profil „szybki" |
| Bielik-4.5B-v3.0-Instruct (2025) | Apache-2.0 ✔ | 8K (wg bielik.ai) | starsza generacja | — | ✘ | brak Q4 w oficjalnym repo (Q8 5,06 GB; MLX-4bit 3,16 GB) | szybki | Nie |
| **PLLuM-12B-instruct-2512** (Mistral Nemo) | Apache-2.0 ✔ | karta nie podaje | **Nie ma go** na Open PL LLM Leaderboard (trenowany na częściach treningowych zadań); Polish Medical 36,51 (wariant chat) | Karta nie deklaruje tool calling; gramatyka działa niezależnie | ✘ | 7,48 / 8,73 GB (tylko GGUF społeczności) | ~12–13 tok/s | Profil opcjonalny |
| PLLuM-4B-*-2512 | Tag `apache-2.0`, ale baza to `gemma-3-4b-pt` (Gemma Terms of Use) ⚠ | — | — | — | — | — | — | Unikać: niejasność licencyjna |
| Llama-PLLuM-8B / 70B | Llama 3.1 Community License ✘ | — | — | — | — | — | — | Wykluczone |
| PLLuM-*-nc-* | CC-BY-NC-4.0 ✘ | — | — | — | — | — | — | Wykluczone |
| **Gemma 4 12B-it** | Apache-2.0 ✔ (zmiana względem Gemma Terms w Gemma 3) | 256K | Brak wyników PL dla Gemma 4. Pośrednio: Gemma 3 12B 62,20 Open PL; Gemma 3 27B wygrywa z Bielikiem 11B v3.0 w jednym zestawieniu (3,81 vs 3,73) | Natywny function calling (karta modelu); 140+ języków | ✔ obraz + audio | 7,12 / 8,41 GB + mmproj 0,18 | ~14 tok/s; zgłoszona regresja Metal (issue #21655) | **Fallback** |
| Gemma 4 E4B-it | Apache-2.0 ✔ | 128K | brak | jw. | ✔ | 4,98 / 5,48 GB + mmproj 0,99 | ~25–30 tok/s | Opcja „bardzo szybka" |
| Gemma 4 26B-A4B | Apache-2.0 ✔ | 256K | brak | jw. | ✔ | 16,95 GB | nie mieści się | Produkcja (GPU 24 GB) |
| Qwen3.5-9B | Apache-2.0 ✔ | 262K | Brak dla 3.5. Qwen3-8B 55,78; Qwen3-14B 62,24 | Tool calling w karcie; model „thinking" (karta zaleca kontekst ≥ 128K) | ✔ | 5,68 / 6,58 GB + mmproj 0,92 | ~17 tok/s | Alternatywa |
| Qwen3.6-27B / Qwen3.8-27B | Apache-2.0 ✔ | 262K | brak | — | ✔ | ~16,6 GB (4-bit) | nie mieści się | Produkcja |
| Ministral-3-14B-Instruct-2512 | Apache-2.0 ✔ | 256K | brak | Natywny function calling i JSON (karta modelu) | ✔ | 8,24 / 9,62 GB + mmproj 0,88 | ciasno | Nie |
| Mistral Small 3.2 (24B) / Small 4 (119B MoE) | Apache-2.0 ✔ | — | — | — | — | za duże | nie | Nie |
| Phi-4 (14B), Phi-4-mini | MIT ✔ | — | CPTUB 3,30 (poniżej Bielika-Minitron 3,83) | — | ✘ | — | — | Nie |
| Granite 4.1-8b / 4.0-h-small | Apache-2.0 ✔ | — | brak dowodów PL | — | ✘ | — | — | Nie |
| gpt-oss-20b | Apache-2.0 ✔ | — | brak dowodów PL | model „thinking" (tokeny rozumowania zjadają limit) | ✘ | 11,62 GB | bardzo ciasno obok Dockera | Nie |
| DeepSeek V4.x | MIT ✔ | — | — | — | — | duże modele | nie | Nie |
| Llama 4 Scout / Maverick | Llama 4 Community License ✘ (gated) | — | — | — | ✔ | za duże | nie | Wykluczone |

Uwagi:
- Główne repo `speakleash/Bielik-11B-v3.1-Instruct` jest **gated** (logowanie i zgoda). Repo `-GGUF` nie jest gated, więc pobieranie nie wymaga tokenu.
- Od kwietnia 2025 Meta nie opublikowała na HF nowszej Llamy.
- Budżet pamięci na Macu 16 GB: macOS ~4 GB, VM Docker Desktop 3–4 GB, model 6,7 GB, KV cache 1–1,5 GB przy 16K. Jest ciasno. Ustawić limit pamięci VM Dockera ≤ 3 GB i kontekst 12–16K albo użyć Minitron-7B.

## 2. Wątek polskiej suwerenności

Bielik 11B v3.1 jest technicznie wystarczający na model domyślny i ma lepsze pokrycie dowodami niż PLLuM:
- najwyższe wyniki wśród otwartych modeli tej wielkości w polskich benchmarkach (v3.0),
- 32K kontekstu i tool calling,
- oficjalne artefakty: GGUF (Q4–Q8), MLX 4/8-bit, AWQ, FP8, NVFP4, obraz Ollama,
- trenowany na Athena/Helios (PLGrid) i w Gaia AI Factory (EuroHPC).

PLLuM (rodzina 2512, grudzień 2025) ma słabszą pozycję techniczną: baza Mistral Nemo z 2024 r., tylko społecznościowe GGUF (mradermacher), brak wyników na Open PL. Ponieważ wywołanie idzie przez endpoint OpenAI-compatible, profil `LLM_MODEL=pllum-12b-instruct-2512` kosztuje jeden wpis w konfiguracji. Na obronie da się powiedzieć: „domyślnie polski Bielik, przełączalnie ministerialny PLLuM albo Gemma 4".

Ciekawostka: `Bielik-One-11B-v3.1-r1` (Apache-2.0) to model „decyzyjny" (choice/bool/score) pod vLLM 0.32. Pasuje do klasyfikacji typów pól w produkcji na GPU. Na Macu nieużyteczny (~30 GB VRAM w bf16).

## 3. Runtime

| Runtime | Wersja (zweryfikowana) | Licencja | Python 3.14 / Java | M4 16 GB | Werdykt |
|---|---|---|---|---|---|
| **llama.cpp `llama-server`** | buildy `b12606` (2026-11-21); istnieje tag `v1.0.0` | MIT | nie dotyczy (HTTP) | natywnie Metal; w kontenerze CPU (linux/arm64) | **Główny** |
| Docker Model Runner | v1.2.9 | Apache-2.0 | nie dotyczy | llama.cpp na hoście z Metal; kontenery widzą `model-runner.docker.internal` | Opcja na demo |
| **Ollama** | v0.40.17 | MIT | klient `ollama` 0.6.3 (czysty Python) | natywnie Metal | **Fallback** |
| vLLM | 0.34.0 | Apache-2.0 | `<3.15,>=3.11`, klasyfikator 3.14 ✔ | nie (Linux + NVIDIA) | Produkcja GPU |
| mlx-lm | 0.32.2 (mlx 0.32.4 ma koła cp314) | MIT | ✔ | tylko macOS, nie działa w kontenerze Linux | Nie |
| llama-cpp-python | 0.3.37 | MIT | klasyfikator 3.14, brak koła cp314 (kompilacja w obrazie) | CPU w kontenerze | Nie |
| ONNX Runtime GenAI | 0.20.0 | MIT | koła cp314 ✔ | brak gotowych modeli Bielik/PLLuM | Nie |
| LM Studio | — | aplikacja zamknięta ✘ | — | — | Wykluczone |

**Realistyczny projekt:**
- `docker-compose.yml` z dwoma serwisami: `app` (API) i `llm` (`ghcr.io/ggml-org/llama.cpp:server-<build>`, przypięty tag).
- `app` zna tylko `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` (sekret w runtime).
- Profil domyślny: wszystko w kontenerach, CPU, sieć `internal: true` bez wyjścia do internetu. Działa wszędzie, jest wolny.
- Profil demo na Macu: `LLM_BASE_URL=http://host.docker.internal:8080/v1` i natywny `llama-server -ngl 99` z Metal.
- Profil produkcyjny: ten sam kontener w wariancie `server-cuda` albo vLLM na serwerze GPU.

Dwie rzeczy do poprawienia w oficjalnym obrazie llama.cpp: baza to **Ubuntu 26.04** (nie Alpine), a Dockerfile **nie ustawia `USER`**. Trzeba dodać `user: "10001:10001"` w compose i wolumen z modelem tylko do odczytu.

**Czy lokalny endpoint OpenAI-compatible łamie zakaz „external API"?**
- *Nie łamie:* zakaz dotyczy usług zewnętrznych (SaaS, modele dostępne wyłącznie przez API). Lokalne modele open-weight są wprost dozwolone. Serwer modelu w tej samej sieci compose to komponent rozwiązania, tak jak baza danych. Wagi leżą na dysku, ruch nie opuszcza hosta, co da się pokazać siecią bez egressu.
- *Może łamać:* jury może czytać „żadnych API" dosłownie. Konfigurowalny URL pozwala technicznie wskazać chmurę. Serwer uruchomiony natywnie na hoście jest poza Dockerem, a Docker jest obowiązkowy.
- *Zabezpieczenie:* domyślny profil w 100% w kontenerach i offline; aplikacja odrzuca `LLM_BASE_URL` spoza loopback / sieci prywatnej, chyba że ustawiono jawną flagę; README opisuje profil Metal jako akcelerację sprzętową tej samej binarki.

**Szacowane tokens/s (generacja), M4 16 GB:**

| Model | Metal natywnie | CPU w kontenerze na Macu |
|---|---|---|
| Bielik 11B v3.1 Q4_K_M | 13–15 | 3–5 |
| PLLuM-12B Q4_K_M | 12–13 | 3–4 |
| Gemma 4 12B Q4_K_M | ~14 | 3–5 |
| Qwen3.5-9B Q4_K_M | ~17 | 4–6 |
| Bielik-Minitron-7B Q4_K_M | ~20 | 5–7 |
| Gemma 4 E4B Q4_K_M | 25–30 | 7–10 |

Pierwsza czynność po sklonowaniu: `llama-bench -m <gguf> -ngl 99 -p 512 -n 128` i zapis wyników.

## 4. Structured output

| Narzędzie | Wersja | Licencja | Python 3.14 / Java | Werdykt |
|---|---|---|---|---|
| **llama.cpp `response_format: json_schema` (GBNF)** | wbudowane | MIT | nie dotyczy | **Główne**, dla małych płaskich schematów |
| llguidance | 1.9.1 | MIT | koła cp314 abi3 ✔ | Opcjonalny backend llama.cpp (flaga budowania, wymaga Rust) |
| **Ollama `format` (JSON schema)** | 0.40.17 | MIT | — | **Fallback** |
| vLLM guided decoding / XGrammar 0.2.9 | 0.34.0 | Apache-2.0 | ✔ | Produkcja GPU |
| Outlines | 1.3.3 | Apache-2.0 | ✘ `requires_python <3.14` | Wykluczone |
| Instructor | 1.17.0 | MIT | czysty Python, brak klasyfikatora 3.14 | Zbędne |
| PydanticAI | 2.71.0 | MIT | klasyfikator 3.14 ✔ | Opcjonalnie |
| **Pydantic** | 2.14.4 | MIT | 3.14 ✔ | **Tak**: walidacja IR i wyniku |
| **openai SDK** | 3.57.0 | Apache-2.0 | 3.14 ✔ | **Tak**: klient (alternatywa: `httpx`) |
| BAML | 0.226.3 | Apache-2.0 | koła abi3, brak klasyfikatora 3.14 | Nie (DSL + codegen) |
| DSPy | 3.5.0 | MIT | `<3.16` | Nie (brak danych do optymalizacji) |
| LangChain / LangGraph | 1.5.2 / 1.2.24 | MIT | ✔ | Nie (ciężkie zależności dla 3 wywołań) |
| Spring AI / LangChain4j | 2.1.0 / 1.24.0 | Apache-2.0 | Java 21+ | Jeśli zespół wybierze Javę |
| jsonschema, jsonata-python, json-repair | 4.26.0 / 0.7.2 / 0.64.9 | MIT / Apache-2.0 / MIT | ✔ / czysty Python / czysty Python | Tak: walidacja schematu i wyrażeń JSONata |

**Dlaczego nie one-shot.** Zmierzone w repo: referencyjne JSON-y organizatora mają 97 i 104 KB, po minifikacji 41,9 i 44,7 tys. znaków, 69 i 73 pola, 83 i 89 identyfikatorów `id`, 29 i 31 warunków `SHOW`. To około 14–15 tys. tokenów wyjścia. Przy 14 tok/s daje to ponad 16 minut, czyli osiem razy powyżej celu. Constrained decoding nie przyspiesza generacji.

**Udokumentowane tryby awarii:**
- *Poprawny schemat, zła treść.* „The Constraint Tax" (2026): twarde ograniczenie podnosi poprawność schematu z 61,5% do 100%, ale obniża trafność odpowiedzi z 19,7% do 11,0% (modele < 3B). Wniosek autorów: „reason free, constrain late". Praca z IJCAI 2026 (modele 0,5–8B) potwierdza: constrained decoding gwarantuje składnię, nie poprawia semantyki i może ją pogarszać przy złożonych gramatykach.
- *Luki w obsłudze JSON Schema.* Dokumentacja GBNF llama.cpp: zagnieżdżone `$ref` nie działają, `prefixItems` nie działa, gramatyki mają „performance gotchas" (issue #4218). Zgłoszenia #25923 i #25895: serwer odrzuca duże schematy. JSONSchemaBench pokazuje to samo dla sześciu frameworków.
- *Obcięcie.* Limit `max_tokens` kończy generację w połowie obiektu; gramatyka nie domyka nawiasów.
- *Ciche obcięcie promptu w Ollamie.* Domyślny kontekst to 4K dla < 24 GiB VRAM. Trzeba ustawić `OLLAMA_CONTEXT_LENGTH`.
- *Spójność referencyjna.* Gramatyka bezkontekstowa nie wymusi unikalności UUID ani tego, że JSONata i `flow.links` wskazują istniejące identyfikatory.

**Zalecany wzorzec (główny):**
1. Parser deterministycznie wykrywa kandydatów na pola (etykieta, typ geometryczny, strona, pozycja).
2. Wywołanie A, per strona lub blok: model zwraca płaską listę pól w IR, jedna krótka pozycja na pole: `idx`, `label`, `type` (enum), `validators` (enum[]), `required`, `dict` (enum), `section_ref` (enum sekcji predefiniowanych lub `NEW:<nazwa>`).
3. Wywołanie B: przypisanie sekcji do stron tematycznych, kolejność, sekcje powtarzalne.
4. Wywołanie C: warunki jako trójki `(target_idx, SHOW|READ_ONLY, source_idx, operator, wartość)`.
5. Kod deterministyczny buduje finalny JSON: UUID, `techName`, siatka `x/y/rows/cols`, stringi JSONata z szablonów, `flow.links`, rozwinięcie sekcji predefiniowanych.
6. Walidacja: schemat organizatora, parsowanie każdej JSONaty, kontrola referencji. Przy błędzie jedno ponowienie z komunikatem błędu, potem fallback deterministyczny.

Schematy kroków A–C są płaskie, bez `$ref`, z enumami, `temperature` 0–0,1. Każde wywołanie ma jawny `max_tokens` i limit czasu.

**Budżet czasu na M4.** Przy ~14 tok/s w dwie minuty mieści się około 1500 tokenów wyjścia minus czas przetwarzania promptu. Dlatego:
- IR musi mieć ~15–20 tokenów na pole,
- statyczny prefiks promptu (instrukcje + przykłady) musi być identyczny między wywołaniami, żeby zadziałał cache promptu w `llama-server`,
- dla formularzy 10–16 stron na bazowym M4 realne są 3–5 minut z modelem 11B; do pokazu na żywo przygotować profil Minitron-7B.

**Fallback:** ten sam pipeline przez Ollama `format`, bez zmian w kodzie poza adresem i nazwą modelu.

## 5. Obraz czy tekst

Tekst + geometria jako wejście główne:
- PDF-y z warstwą tekstową dają dokładny tekst bez halucynacji; pola wyboru, linie kropkowane i tabele wynikają z geometrii.
- Obrazy próbne mają 1654 × do 37 424 px. Każdy VLM przeskaluje je w dół do nieczytelności. Trzeba ciąć na kafle wielkości strony (1654 × 2339 px przy 200 DPI).
- Na 16 GB nie zmieszczą się jednocześnie LLM 11B i osobny VLM.

VLM jako ścieżka awaryjna (skan, zdjęcie, słaby OCR): **Gemma 4 12B** obsługuje obraz i tekst jednym modelem, co jest drugim powodem wyboru jej na fallback. Alternatywa: Qwen3.5-9B.

Małe wyspecjalizowane modele OCR/VLM na licencjach permisywnych: PaddleOCR-VL (0,9B, Apache-2.0), GLM-OCR (MIT), LightOnOCR-2-1B (Apache-2.0), granite-docling-258M (Apache-2.0), DeepSeek-OCR-2 (Apache-2.0), dots.ocr (MIT), olmOCR-2-7B (Apache-2.0). **Nie znalazłem żadnego benchmarku jakości dla polskich formularzy**, więc wybór wymaga testu na plikach z `Docs/`.

## 6. Few-shot z referencyjnych JSON-ów

- **Dekompilator offline:** skrypt zamienia oba referencyjne JSON-y na IR (odwrotność buildera). Każdy przykład kurczy się z ~15 tys. do ~2 tys. tokenów. Test `build(decompile(ref)) == ref` (z dokładnością do UUID) jest jednocześnie testem jednostkowym buildera.
- **Biblioteka sekcji predefiniowanych** („Twoje dane", „Adres", „Podmiot wniosku", zgody): szablony z gotowymi polami, walidatorami i słownikami. Model wybiera `section_ref`, kod rozwija. Przy 10–20 szablonach cała lista nazw z jednozdaniowym opisem mieści się w prompcie; baza wektorowa jest zbędna.
- **Przykłady per krok:** pary „fragment formularza papierowego → linie IR", osobne dla kroków A, B i C.
- **Standardy COI** jako krótka lista reguł po polsku w prompcie systemowym.
- **Ryzyko:** tylko dwa przykłady, więc model może je kopiować. Pozostałe siedem formularzy z `Docs/` traktować jako zbiór kontrolny z testami strukturalnymi.

## 7. Koszt produkcyjny (on-prem)

Założenia: ~8 tys. tokenów promptu i ~2,5 tys. tokenów wyjścia na formularz; amortyzacja 3 lata, 250 dni roboczych; energia ~1,1 zł/kWh; analityk 100 zł/h z narzutami; ręczna konfiguracja formularza 2–4 h, weryfikacja wyniku z narzędzia 20–30 min. Ostatnie trzy liczby to moje założenia, nie dane COI.

| Skala | Sprzęt | Koszt jednorazowy | Koszt na formularz |
|---|---|---|---|
| ~100 / dzień | Stacja z jedną kartą 16 GB (klasa RTX 5060 Ti 16 GB: ~2,0–2,5 tys. zł w 2026 r.) albo istniejący serwer CPU w trybie nocnego batcha | ~8–10 tys. zł (CPU: 0 zł) | ~0,13 zł + energia < 0,02 zł |
| ~1000 / dzień | Serwer z kartą klasy RTX 5070 Ti 16 GB (~5,4–5,9 tys. zł, 10.2026), `--parallel 4`; wariant z zapasem: RTX 5090 32 GB (~34–38 tys. zł, 11.2026) | ~15–20 tys. zł (z 5090: ~50 tys. zł) | ~0,03 zł |

Praca ręczna: 200–400 zł za formularz. Z narzędziem: ~40–50 zł (sama weryfikacja). Sprzęt zwraca się po kilkudziesięciu formularzach. Ceny kart graficznych w 2026 r. są niestabilne (RTX 5090 kosztuje około czterokrotność ceny premierowej 9100 zł), więc wariant z kartą 16 GB jest bezpieczniejszy budżetowo.

## Źródła

Modele:
- https://huggingface.co/speakleash/Bielik-11B-v3.1-Instruct-GGUF
- https://huggingface.co/speakleash/Bielik-11B-v3.1-Instruct (gated)
- https://ollama.com/SpeakLeash/bielik-11b-v3.1-instruct
- https://huggingface.co/speakleash/Bielik-11B-v3.1-Instruct-MLX-4bit
- https://huggingface.co/speakleash/Bielik-Minitron-7B-v3.0-Instruct-GGUF
- https://huggingface.co/speakleash/Bielik-One-11B-v3.1-r1
- https://www.bielik.ai/en
- https://arxiv.org/abs/2601.11579 (Bielik 11B v3)
- https://arxiv.org/abs/2603.11881 (Bielik-Minitron-7B: Open PL, CPTUB, BFCL)
- https://arxiv.org/abs/2604.10799 (Bielik v3 PL, tokenizer)
- https://arxiv.org/abs/2505.02550 (Bielik v3 Small; uwaga o PLLuM poza leaderboardem)
- https://huggingface.co/CYFRAGOVPL/PLLuM-12B-instruct-2512
- https://huggingface.co/CYFRAGOVPL/PLLuM-4B-instruct-2512
- https://huggingface.co/CYFRAGOVPL/models
- https://huggingface.co/mradermacher/PLLuM-12B-instruct-2512-GGUF
- https://huggingface.co/google/gemma-4-12b-it
- https://ai.google.dev/gemma/docs/core/model_card_4
- https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/
- https://huggingface.co/unsloth/gemma-4-12b-it-GGUF
- https://huggingface.co/Qwen/Qwen3.5-9B
- https://huggingface.co/unsloth/Qwen3.5-9B-GGUF
- https://huggingface.co/Qwen/Qwen3.8-27B
- https://huggingface.co/mistralai/Ministral-3-14B-Instruct-2512
- https://huggingface.co/microsoft/phi-4
- https://huggingface.co/ibm-granite/granite-4.1-8b
- https://huggingface.co/openai/gpt-oss-20b
- https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct
- https://www.codesota.com/browse/nlp/polish-llm-general/open-pl-llm-leaderboard (kopia Open PL LLM Leaderboard, źródło wtórne)
- https://huggingface.co/spaces/speakleash/open_pl_llm_leaderboard

Runtime:
- https://github.com/ggml-org/llama.cpp/releases
- https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md
- https://github.com/ggml-org/llama.cpp/blob/master/.devops/cpu.Dockerfile
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://github.com/ggml-org/llama.cpp/issues/21655
- https://docs.docker.com/ai/model-runner/
- https://docs.docker.com/ai/model-runner/inference-engines/
- https://github.com/docker/model-runner
- https://github.com/ollama/ollama
- https://docs.ollama.com/context-length
- https://github.com/vllm-project/vllm/releases
- https://llmcheck.net/benchmarks
- https://www.kunalganglani.com/llm-benchmarks

Structured output:
- https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- https://github.com/ggml-org/llama.cpp/blob/master/docs/llguidance.md
- https://github.com/ggml-org/llama.cpp/issues/25923
- https://github.com/ggml-org/llama.cpp/issues/25895
- https://docs.ollama.com/capabilities/structured-outputs
- https://arxiv.org/abs/2605.26128 (The Constraint Tax)
- https://www.ijcai.org/proceedings/2026/0267.pdf
- https://arxiv.org/abs/2501.10868 (JSONSchemaBench)
- https://pypi.org/project/outlines/ , https://pypi.org/project/xgrammar/ , https://pypi.org/project/llguidance/ , https://pypi.org/project/instructor/ , https://pypi.org/project/pydantic-ai/ , https://pypi.org/project/pydantic/ , https://pypi.org/project/openai/ , https://pypi.org/project/baml-py/ , https://pypi.org/project/dspy/ , https://pypi.org/project/langchain/ , https://pypi.org/project/langgraph/ , https://pypi.org/project/llama-cpp-python/ , https://pypi.org/project/mlx-lm/ , https://pypi.org/project/vllm/ , https://pypi.org/project/onnxruntime-genai/ , https://pypi.org/project/jsonata-python/
- https://repo1.maven.org/maven2/dev/langchain4j/langchain4j/maven-metadata.xml
- https://repo1.maven.org/maven2/org/springframework/ai/spring-ai-model/maven-metadata.xml

VLM / OCR:
- https://huggingface.co/PaddlePaddle/PaddleOCR-VL , https://arxiv.org/abs/2603.24326
- https://huggingface.co/zai-org/GLM-OCR
- https://huggingface.co/lightonai/LightOnOCR-2-1B
- https://huggingface.co/ibm-granite/granite-docling-258M
- https://huggingface.co/deepseek-ai/DeepSeek-OCR-2
- https://huggingface.co/rednote-hilab/dots.ocr
- https://huggingface.co/allenai/olmOCR-2-7B-1025

Ceny:
- https://ithardware.pl/aktualnosci/karty_graficzne_ceny_polska-55700.html
- https://www.ceneo.pl/Karty_graficzne/Chipset:GeForce_RTX_5090.htm
- https://www.purepc.pl/karty-graficzne-nvidia-geforce-rtx-5000-blackwell-ceny-kwiecien-2026
- https://hdtvpolska.com/geforce-rtx-5070-ti-pny-16gb-promocja-amazon-polska/

## Czego nie udało się zweryfikować

- **Wyniki benchmarków Bielika 11B v3.1.** Karta modelu jest gated; podane liczby dotyczą v3.0.
- **Jakość polskiego w Gemma 4 i Qwen3.5.** Nie znalazłem żadnego wyniku na Open PL LLM Leaderboard, PLCC ani CPTUB. Leaderboard EuroEval nie dał się odczytać (strona renderowana w JS).
- **Wszystkie wartości tokens/s** to ekstrapolacja z pomiarów innych modeli, nie pomiary własne. Szybkość przetwarzania promptu nie została oszacowana ze źródeł.
- **Kontekst** PLLuM-12B-2512 (karta nie podaje) i Bielik-Minitron-7B (karta gated).
- **Niezawodność JSON/tool calling** poszczególnych modeli na polskich formularzach: brak takich testów; potrzebny własny test na plikach z `Docs/`.
- **Czy oficjalny obraz Docker llama.cpp ma wkompilowane llguidance** oraz dokładny format tagów obrazu (`server-b<numer>`); sprawdzić w rejestrze przed przypięciem. Rola tagu `v1.0.0` względem buildów `b12xxx` nie jest dla mnie jasna.
- **Licencja PLLuM-4B:** tag Apache-2.0 przy bazie objętej Gemma Terms of Use. Nie ustaliłem, czy to błąd, czy osobne uzgodnienie.
- **LM Studio** (zamknięta licencja) i **warunki licencyjne Docker Desktop dla administracji** podaję z pamięci, bez sprawdzenia w tej sesji.
- **Praca „Let Me Speak Freely"** (wpływ ograniczeń formatu na rozumowanie) nie została otwarta w tej sesji, więc jej nie cytuję jako dowodu.
- **Funkcje structured output w Spring AI 2.1.0 i LangChain4j 1.24.0:** zweryfikowałem tylko numery wersji.
- **Aktualne ceny** (listopad 2026) kart RTX 5060 Ti / 5070 Ti i komputerów Mac; ceny sprzętu serwerowego klasy enterprise nie były sprawdzane.
- **Czas pracy analityka** na ręczną konfigurację formularza: założenie do potwierdzenia przez COI.
