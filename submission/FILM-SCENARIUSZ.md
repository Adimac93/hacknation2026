# Scenariusz filmu (maks. 3:00)

Cel: pokazać jurorowi w trzy minuty: problem, działanie na żywo, widok audytora, podgląd e-formularza, przypadek negatywny, tryb reguł kontra model, wsad, bezpieczeństwo i koszt. Układ czasowy oparty na `research/03-konkurencja-i-wyrozniki.md`, sekcja 6.

Wszystkie akcje na działającej aplikacji pod `http://localhost:8080` (`docker compose up -d --build --wait`, trzy kontenery `healthy`). Pliki z `Docs/` (katalog organizatora, nie edytować, tylko wskazać w oknie wyboru pliku).

## Pliki użyte w filmie

| Skrót | Plik | Po co |
|---|---|---|
| A | `Docs/3. Wniosek o wydanie zaświadczenia - formularze do cyfryzacji/Wniosek o wydanie zaświadczenia.pdf` | główny przebieg, szybki w trybie reguł (40 ms w `outputs/README.md`) |
| B | `Docs/6. Wniosek o wydanie zezwolenia na zajęcie pasa drogowego w celu prowadzenia robót - formularze do cyfryzacji/Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.pdf` | większy formularz (69 pól), tryb model: 11 s wg `README.md` |
| C | `Docs/4. Wniosek o wynajęcie lub użyczenie świetlicy wiejskiej - formularze do cyfryzacji/Wniosek o wynajęcie świetlicy.jpg` | skan (OCR) |
| D | `Docs/8. Deklaracja o wysokości miesięcznej opłaty za gospodarowanie odpadami komunalnymi - formularze do cyfryzacji/Deklaracja o wysokości opłaty.docx` | format biurowy (Tika), do wsadu |
| E | `Docs/9. Wniosek o przyznanie stypendium, nagrody lub wyróżnienia sportowego Rady Miasta (Połączenie 3 wniosków w 1) - formularze do cyfryzacji/Wniosek o przyznanie stypendium.pdf` | do wsadu |
| X1 | dowolny plik tekstowy `notatki.txt` poza repozytorium (wcześniej utworzony, pusty lub z jednym zdaniem) | błąd po stronie przeglądarki: zły typ |
| X2 | kopia pliku A z rozszerzeniem zmienionym na `.docx` (`cp A falszywy.docx`, w katalogu poza repozytorium) | błąd po stronie API: treść niezgodna z rozszerzeniem, 415 `application/problem+json` |

Dokładne nazwy plików sprawdź przed nagraniem (`ls "Docs/<katalog>"`); katalogi 3, 4, 6, 8, 9 zawierają po kilka formatów tego samego wniosku.

## Scenariusz

Narracja po polsku, tempo ok. 130 słów na minutę. Razem ok. 380 słów.

| Czas | Obraz / akcja na ekranie | Narracja |
|---|---|---|
| 0:00–0:15 | Zdjęcie lub wydruk blankietu A obok pustego pola wyboru pliku. Napis: „Jeden blankiet = ręczna analiza”. | „Urzędy nadal publikują blankiety jako PDF, DOC i skany. Każdy trzeba ręcznie przeanalizować i przeprojektować na formularz elektroniczny. Biurokratka robi to w kilka sekund i oddaje plik gotowy do importu w Generatorze Formularzy COI.” |
| 0:15–0:40 | Strona startowa. Pokaż listę formatów i limit 20 MB, napis „Plik nie jest zapisywany na serwerze”. Kliknij „Wybierz pliki”, wybierz plik A. Kolejka plików: pasek postępu, status „Analiza”, potem „Gotowe”. | „Wgrywam wniosek o zaświadczenie. Obsługujemy osiem formatów. Plik trafia tylko do pamięci. Postęp widać na żywo, wynik jest po ułamku sekundy w trybie reguł.” |
| 0:40–1:15 | Zakładka „Dokument i formularz”. W polu „Pokaż źródło pola” wybierz kilka pól: podświetlają się linie blankietu, pojawia się „Pewność rozpoznania”. Wybierz jedno pole poniżej 70%: komunikat „sprawdź to pole przed eksportem”. | „To widok audytora. Po lewej tekst blankietu, po prawej e-formularz. Wybieram pole i widzę, z których linii powstało oraz jak pewne jest rozpoznanie. Pole poniżej siedemdziesięciu procent jest oznaczone do sprawdzenia, więc urzędnik poprawia tylko to, co trzeba.” |
| 1:15–1:40 | Przewiń podgląd e-formularza. Wybierz opcję, która odsłania sekcję (np. wniosek składany przez inną osobę, jeśli występuje w wyniku; w przeciwnym razie użyj formularza B). Wpisz błędny PESEL (komunikat), potem poprawny. Przejdź przyciskiem „Dalej” do ostatniej strony (nazwy przycisków sprawdź w aplikacji przed nagraniem). | „Podgląd liczy warunki na żywo. Wybór opcji odsłania sekcję, PESEL jest walidowany sumą kontrolną. To nie jest transkrypcja blankietu, tylko formularz zaprojektowany według standardów COI: strony tematyczne, sekcje predefiniowane, słowniki.” |
| 1:40–1:55 | Zakładka „Raport”: wiersz „Tryb: reguły”, tabela „Kontrola zgodności” (0 błędów, liczba uwag), „Proponowane słowniki”, „Czas przetwarzania”. Zakładka „JSON”, przyciski „Kopiuj”, „Pobierz JSON”. | „Raport pokazuje wynik lintera: zero błędów, uwagi jakościowe i propozycje nowych słowników. JSON pobieram jednym kliknięciem.” |
| 1:55–2:15 | Przypadek negatywny: przeciągnij X1 na strefę: czerwony komunikat „Nie dodano 1 plików”. Następnie wybierz X2: wiersz kolejki ze statusem „Błąd” i komunikatem. | „A jeśli plik jest zły? Zły typ odrzuca już przeglądarka. Plik, który udaje dokument, odrzuca API: treść nie zgadza się z rozszerzeniem, odpowiedź to problem plus JSON, nigdy błąd 500.” |
| 2:15–2:35 | Wgraj naraz pliki B, C, D, E. Kolejka: pasek „Plik n z 4”. Otwórz wynik C (skan): pokaż, że pola z OCR mają niższą pewność. Zakładka „Raport” dla B z poprzednio nagranego przebiegu z modelem: „Tryb: model językowy” (wstaw wcześniej nagrany fragment, patrz niżej). | „Tryb wsadowy przetwarza kolejkę po kolei, także skany przez OCR i pliki biurowe przez Tikę. Bez modelu działają reguły. Z modelem open-weight etykiety są lepsze: dla większego formularza to ok. jedenastu sekund i około jednej dziesiątej centa.” |
| 2:35–2:52 | Terminal: `docker compose ps` (trzy `healthy`), `docker inspect --format '{{.Config.User}} {{.HostConfig.ReadonlyRootfs}}' <kontener api>`. Opcjonalnie: `python3 devtools/check_licenses.py` (ostatnie linie: wynik bramki). | „Całość to trzy kontenery: użytkownik bez uprawnień, system plików tylko do odczytu, jeden port na hoście. Tika nie ma dostępu do internetu. Bramka licencyjna sprawdza każdą zależność: tylko open source bez copyleftu.” |
| 2:52–3:00 | Slajd lub ekran końcowy: logo, adres repozytorium (TODO), hasło. | „Biurokratka: jeden blankiet, formularz gotowy do importu. Dziękujemy.” |

Uwaga do liczby w narracji 2:15–2:35: „około jednej dziesiątej centa” wynika z `README.md` (ok. 0,001 USD za formularz). Jeśli wolisz nie podawać kwoty, zamień na „ułamek centa”.

## Tryb reguł kontra model (jak to sfilmować)

Interfejs nie ma przełącznika trybu; tryb wynika z konfiguracji `api` (`LLM_ENABLED`). Rozwiązanie:

1. Nagraj przebieg pełny w trybie reguł (bez `.env`), jak wyżej.
2. Osobno uruchom stos z `.env` z `LLM_ENABLED=true` (`.env.example` zawiera konfigurację; klucz tylko w `.env`, nie pokazuj go w kadrze) i nagraj tylko: wgranie pliku B, odliczanie postępu, zakładkę „Raport” z „Tryb: model językowy” i tabelą czasów.
3. Zmontuj obie części w punkcie 2:15–2:35. Nie wklejaj do kadru terminala z `.env`.

Jeśli model jest niedostępny w dniu nagrania: pomiń fragment modelu i zostaw zdanie o trybie reguł jako siatce bezpieczeństwa (awaria modelu nie daje błędu, usługa przechodzi na reguły).

## Wskazówki nagrania

- Rozdzielczość 1366 × 768, zoom przeglądarki 100%, okno bez paska zakładek i zakładek osobistych (tryb pełnoekranowy `F11`).
- Pole „Token JWT” jest w zwiniętym bloku „Uwierzytelnianie (opcjonalne)”: nie rozwijaj go. Jeśli usługa wymaga tokenu, wpisz go przed nagraniem i nie pokazuj go w kadrze.
- Przed nagraniem wyczyść kolejkę (odśwież stronę) i zamknij inne karty z danymi osobistymi. Używaj czystego profilu przeglądarki.
- Wszystkie pliki wskazuj z okna wyboru pliku: nie pokazuj ścieżek spoza repozytorium.
- Wykonaj próbę generalną na tych samych plikach; czasy w narracji (40 ms, 11 s) to wartości z `outputs/README.md` i `README.md`, zmierz je ponownie na maszynie nagrania i popraw narrację, jeśli odbiegają.
- Dźwięk: nagraj narrację osobno i zmontuj; ekran nagraj bez dźwięku. Napisy po polsku (plik `.srt`) poprawiają dostępność.
- Film umieść w otwartym repozytorium wideo i wstaw link do `OPIS-ZGLOSZENIA.md` oraz na slajd 10 (TODO).
- Jeśli któryś krok przekracza limit czasu, skróć akcję (np. wsad do trzech plików), nie narrację.
