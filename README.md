# Biurokratka - Kompilator Formularzy

Projekt na HackNation 2026, zadanie Centralnego Ośrodka Informatyki „Cyfryzacja formularzy”.

Usługa przyjmuje blankiet formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) i zwraca JSON konfiguracji formularza elektronicznego, zgodny z regułami technicznymi i standardami projektowania COI. Działa lokalnie, bez usług zewnętrznych, na modelu językowym open-weight.

Usługa działa w trzech kontenerach (`web`, `api`, `tika`). Bez modelu pracuje w trybie reguł; model językowy jest opcjonalny i wymienny przez `LLM_BASE_URL`.

## Dokumenty

| Plik | Zawartość |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | architektura rozwiązania, potok przetwarzania, kontrakt wyjścia, decyzje |
| [`PLAN.md`](PLAN.md) | plan realizacji, podział pracy, kamienie milowe, ryzyka |
| [`CLAUDE.md`](CLAUDE.md) | zasady pracy dla agentów AI w repozytorium |
| [`research/`](research/) | raporty: OCR i parsowanie, model LLM, konkurencja i wyróżniki, stos i licencje, korpus formularzy, raport licencji zależności |
| [`DESIGN.md`](DESIGN.md) | zasady interfejsu (tokeny, dostępność, komponenty) dla frontendu `web/` |
| [`ksiega-znaku-biurokratka.pdf`](ksiega-znaku-biurokratka.pdf) | Księga znaku Biurokratka v2, źródło prawdy wizualnej |
| [`logo-pack/`](logo-pack/README.md) | logo w wersjach kolorystycznych (SVG, PNG, WebP) |
| [`devtools/corpus/`](devtools/corpus/) | narzędzia do zbierania korpusu testowego (API ELI, Common Crawl); nie są częścią usługi |
| `Docs/` | materiały organizatora |

## Uruchomienie

Sprawdzone na Debianie 13 (amd64, Docker 26.1, Compose 2.26) w trybie reguł, bez modelu.

```sh
cp .env.example .env            # opcjonalnie; bez .env usługa działa w trybie reguł
docker compose up -d --build --wait
docker compose ps               # web, api i tika: healthy
```

Usługi: `web` (nginx, port 8080 opublikowany tylko na `127.0.0.1`: interfejs pod `/` i `/podglad`, proxy do API pod `/api`, `/health`, `/docs`), `api` (bez opublikowanego portu, dostępne tylko przez `web`) i `tika` (tylko sieć wewnętrzna `backend`, bez wyjścia na zewnątrz). Wszystkie kontenery działają jako użytkownik bez uprawnień, z systemem plików tylko do odczytu i `/tmp` w `tmpfs`. `web` ogranicza przesyłanie do 10 plików na minutę z jednego adresu IP.

Najważniejsze zmienne (`.env`): `LLM_ENABLED` (`false` = tryb reguł), `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_ALLOW_REMOTE`, `MAX_UPLOAD_MB` (domyślnie 20), `REQUEST_TIMEOUT_S`. `TIKA_URL` ustawia `compose.yaml`.

```sh
curl http://127.0.0.1:8080/health
# {"status":"ok","llm_enabled":false}

curl -F "file=@wniosek.pdf" http://127.0.0.1:8080/api/v1/forms                 # JSON formularza
curl -F "file=@wniosek.pdf" "http://127.0.0.1:8080/api/v1/forms?details=true"  # {form, report}
```

Błędy mają format `application/problem+json`, np. 415 (treść niezgodna z rozszerzeniem) i 413 (plik ponad `MAX_UPLOAD_MB`).

Wynikowe JSON-y w `outputs/` generuje działająca usługa (plików nie poprawiamy ręcznie):

```sh
uv run --project api python devtools/generate_outputs.py --api http://127.0.0.1:8080
```

## Model językowy

Model tylko porządkuje i nazywa pola (IR). Końcowy JSON zawsze składa `compiler`, a sprawdza `lint`. Klient używa wyłącznie API zgodnego z OpenAI (`messages`, `temperature`, `seed`, `max_tokens`, `response_format` z `json_schema`), więc ten sam kod działa z każdym z trzech wariantów.

**Tryb reguł (domyślny).** `LLM_ENABLED=false` albo brak `.env`. Usługa nie łączy się z niczym poza własnymi kontenerami, pola wyznaczają heurystyki. Na ten tryb usługa przechodzi też sama, gdy model nie odpowiada albo zwraca błąd (bez błędu 500).

**EdenAI (konfiguracja hackathonu, D11, D21).** Model open-weight `Qwen3.5-9B` (Apache-2.0) na endpoincie UE. Wartości z `.env.example`:

```sh
LLM_ENABLED=true
LLM_ALLOW_REMOTE=true            # zdalny host wymaga jawnej zgody
LLM_BASE_URL=https://api.eu.edenai.run/v3
LLM_MODEL=flexai/Qwen3.5-9B@eu
LLM_API_KEY=...                  # tylko w .env, nigdy w repozytorium
```

**Docelowo: lokalny `llama-server`.** Ten sam model w GGUF (Q4_K_M, ok. 5,5 GB) na `llama-server` z llama.cpp (MIT), na CPU albo na karcie z 16 GB pamięci. Tryb rozumowania wyłącza się po stronie serwera, klient zostaje bez zmian:

```sh
llama-server -m Qwen3.5-9B-Q4_K_M.gguf --jinja --reasoning-budget 0 \
  -c 32768 --host 0.0.0.0 --port 8080
```

```sh
LLM_ENABLED=true
LLM_BASE_URL=http://host:8080/v1   # np. http://host.docker.internal:8080/v1 z kontenera api
LLM_MODEL=Qwen/Qwen3.5-9B
```

`LLM_ALLOW_REMOTE` nie jest potrzebne: adresy lokalne, prywatne i nazwy bez kropki (`host`, `*.internal`, `*.local`) są dozwolone bez niego. Tej konfiguracji nie testowaliśmy w czasie hackathonu: laptop demonstracyjny (M1 Pro, 16 GB RAM) uruchamia tylko `web`, `api` i `tika`, a model wołamy przez EdenAI.

## Koszt i czas

Pomiary z formularzy z `Docs/`. Szczegóły dla każdego formatu wejścia: [`research/08-macierz-formatow.md`](research/08-macierz-formatow.md).

| Krok | Wynik |
|---|---|
| Model przez EdenAI, koszt | ok. 0,001 USD za formularz; formularz 8: 10,6 tys. tokenów wejścia + 6,3 tys. wyjścia = 0,0012 USD |
| Model przez EdenAI, czas | formularz 4: 6,5 s; formularz 6: 11 s; formularz 8: 45 s |
| Tryb reguł, PDF | 0,05–2 s na formularz |
| OCR zdjęcia 16 stron | 15 s na M1 Pro, 21 s na serwerze z 8 rdzeniami |

Lokalny `llama-server` nie ma kosztu za wywołanie; czas zależy od sprzętu i nie był mierzony.

## Licencje

Dozwolone są tylko licencje open source bez copyleftu: MIT, BSD, Apache-2.0, ISC, 0BSD, PSF, a SIL OFL-1.1 wyłącznie dla dwóch fontów (`CLAUDE.md`, zasada 1). Bramka licencyjna sprawdza zależności uruchomieniowe Pythona (`pip-licenses`) i pakiety npm z `web/package-lock.json`, wypisuje też licencje wag modeli:

```sh
python3 devtools/check_licenses.py           # kod wyjścia 1 przy niedozwolonej licencji
python3 devtools/check_licenses.py --write   # dodatkowo zapisuje raport
```

Raport z wyjątkami i ich uzasadnieniem: [`research/09-licencje.md`](research/09-licencje.md). Dwie zależności przechodnie na MPL-2.0 (`certifi`, `tqdm`) bramka przepuszcza z ostrzeżeniem; raport opisuje, dlaczego nie da się ich usunąć.

## Testy i jakość

API (z katalogu `api/`):

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict src
```

Frontend (z katalogu `web/`):

```sh
npm ci
npx biome check .
npm test
npm run build
```
