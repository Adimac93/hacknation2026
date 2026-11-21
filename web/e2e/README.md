# Test dymny E2E (Playwright)

Narzędzie tylko dla programisty: nie wchodzi do builda ani do obrazów Docker.

```sh
docker compose up -d --build        # w katalogu głównym repozytorium, aplikacja pod :8080
cd web
npx playwright install chromium     # jednorazowo, pobiera przeglądarkę
npm run e2e                         # E2E_BASE_URL zmienia adres (domyślnie http://localhost:8080)
```

Test wysyła do usługi 2 pliki z `Docs/` (limit nginx: 10 żądań POST na minutę), a analiza może trwać do ok. 60 s.
