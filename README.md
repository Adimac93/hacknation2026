# Biurokratka - Kompilator Formularzy

Projekt na HackNation 2026, zadanie Centralnego Ośrodka Informatyki „Cyfryzacja formularzy”.

Usługa przyjmuje blankiet formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) i zwraca JSON konfiguracji formularza elektronicznego, zgodny z regułami technicznymi i standardami projektowania COI. Działa lokalnie, bez usług zewnętrznych, na modelu językowym open-weight.

**Stan: etap projektu.** Kod jeszcze nie istnieje. Instrukcje budowania obrazu Docker, uruchomienia, konfiguracji i opis REST API pojawią się tutaj razem z implementacją.

## Dokumenty

| Plik | Zawartość |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | architektura rozwiązania, potok przetwarzania, kontrakt wyjścia, decyzje |
| [`PLAN.md`](PLAN.md) | plan realizacji, podział pracy, kamienie milowe, ryzyka |
| [`CLAUDE.md`](CLAUDE.md) | zasady pracy dla agentów AI w repozytorium |
| [`research/`](research/) | raporty: OCR i parsowanie, model LLM, konkurencja i wyróżniki, stos i licencje, korpus formularzy |
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
