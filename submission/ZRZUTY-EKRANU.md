# Zrzuty ekranu do slajdów i zgłoszenia

Pliki PNG zapisz w `submission/slides/img/` pod dokładnie podanymi nazwami. `slides.html` wczytuje je automatycznie; brakujący plik to podpisana pusta ramka. Po dodaniu zrzutów uruchom `node submission/slides/build.mjs`, aby odświeżyć PDF (wymaga Playwrighta: `cd web && npm i --no-save playwright && npx playwright install chromium`).

Ustawienia wspólne: aplikacja na `http://localhost:8080`, okno 1366 × 768 (albo viewport Playwrighta 1366 × 768), zoom 100%, czysty profil, pole „Token JWT” zwinięte i puste. Zrzuty bez danych osobowych; do pokazania używaj tylko plików z `Docs/`.

| Plik | Slajd | Kroki | Co ma być widać |
|---|---|---|---|
| `ekran-weryfikacja.png` | 4 | Wgraj `Docs/3. …/Wniosek o wydanie zaświadczenia.pdf`. Po statusie „Gotowe” otwórz zakładkę „Dokument i formularz”. W polu „Pokaż źródło pola” wybierz pole, które ma pewność poniżej 70% (jeśli takiego nie ma, dowolne pole). | tekst dokumentu z podświetlonymi liniami, komunikat „Pewność rozpoznania”, obok podgląd e-formularza |
| `ekran-kolejka.png` | 5 | Wgraj naraz pliki z `Docs/` katalogi 3, 4, 6 (po jednym PDF). Zrób zrzut w trakcie przetwarzania lub po nim, z sekcją „Kolejka plików”. | pasek postępu, statusy tekstem („Analiza”, „Gotowe”), nazwy plików |
| `ekran-podglad.png` | 5 | Wgraj `Docs/6. …/Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.pdf`, zakładka „Dokument i formularz”. W podglądzie wybierz opcję odsłaniającą sekcję i wpisz niepoprawny PESEL (komunikat błędu). | podgląd e-formularza z odsłoniętą sekcją i komunikatem walidacji |
| `ekran-raport.png` | 5 | Dowolny wynik, zakładka „Raport”. Przewiń tak, by widać „Tryb”, „Kontrola zgodności” i „Czas przetwarzania”. | tryb, tabela kodów lintera, tabela czasów |
| `terminal-docker.png` | 8 | W terminalu: `docker compose ps` oraz `docker inspect --format '{{.Name}} user={{.Config.User}} readonly={{.HostConfig.ReadonlyRootfs}}' $(docker compose ps -q)`. Ciemny motyw terminala o dużej czcionce (min. 18 pt), bez ścieżek osobistych w prompcie. | trzy kontenery `healthy`, `user`, `readonly=true` |

## Dodatkowe zrzuty do zgłoszenia (opcjonalne, nie są w slajdach)

Zapisz w `submission/slides/img/` (dla porządku, slajdy ich nie używają).

| Plik | Kroki | Co ma być widać |
|---|---|---|
| `ekran-start.png` | strona główna bez plików | strefa wgrywania, lista formatów, limit 20 MB, „Plik nie jest zapisywany na serwerze” |
| `ekran-json.png` | zakładka „JSON” po analizie | edytor JSON, przyciski „Kopiuj” i „Pobierz JSON” |
| `ekran-blad.png` | przeciągnij `notatki.txt` na strefę wgrywania | alert „Nie dodano 1 plików” z powodem |
| `ekran-podglad-json.png` | trasa `/podglad`, wczytaj plik z `outputs/` | podgląd dowolnego JSON-a bez udziału usługi |

## Skrypt (dla leada)

Playwright, viewport 1366 × 768: `page.goto("http://localhost:8080")`, `page.setInputFiles('input[type=file]', [...])`, `page.getByRole("tab", { name: "Raport" }).click()`, `page.screenshot({ path: "submission/slides/img/<nazwa>.png" })`. Pola i role wynikają z `web/src/workspace/*.tsx` (zakładki mają role `tab`, wybór pola źródła to `select#origin-field`). Zrzuty dla slajdów utrzymaj w proporcji zbliżonej do ramek (kolumna ok. 700 px wysokości na slajdzie 4, 430 px na slajdzie 5); obraz jest skalowany do ramki bez przycinania.
