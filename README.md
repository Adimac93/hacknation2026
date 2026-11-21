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
| [`research/`](research/) | raporty: OCR i parsowanie, model LLM, konkurencja i wyróżniki, stos i licencje |
| [`DESIGN.md`](DESIGN.md) | zasady interfejsu (tokeny, dostępność, komponenty) dla frontendu `web/` |
| [`ksiega-znaku-biurokratka.pdf`](ksiega-znaku-biurokratka.pdf) | Księga znaku Biurokratka v2, źródło prawdy wizualnej |
| [`logo-pack/`](logo-pack/README.md) | logo w wersjach kolorystycznych (SVG, PNG, WebP) |
| `Docs/` | materiały organizatora |
