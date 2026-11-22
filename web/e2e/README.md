# Test dymny E2E (Playwright)

Narzędzie tylko dla programisty: nie wchodzi do builda ani do obrazów Docker.

```sh
docker compose up -d --build        # w katalogu głównym repozytorium, aplikacja pod :8080
cd web
npx playwright install chromium     # jednorazowo, pobiera przeglądarkę
npm run e2e                         # E2E_BASE_URL zmienia adres (domyślnie http://localhost:8080)
```

Test wysyła do usługi 2 pliki z `Docs/` (limit nginx: 10 żądań POST na minutę), a analiza może trwać do ok. 60 s.

## Macierz formatów (`matrix.spec.ts`)

```sh
npm run e2e:matrix   # ok. 45-90 min, 58 testów
```

Wysyła każdy plik z `Docs/3.`-`Docs/9.` (także JPE, który przeglądarka ma odrzucić), potem scenariusze: paczka 12 plików z ponawianiem po 429, API niedostępne, obsługa samą klawiaturą, `/podglad`. Wynik trafia do `e2e/results.json` i `e2e/RESULTS.md` (regenerowane). `npm run e2e` pomija testy z tagiem `@matrix`. Częściowy przebieg (`npx playwright test matrix.spec.ts -g ...`) aktualizuje tylko własne wiersze.
