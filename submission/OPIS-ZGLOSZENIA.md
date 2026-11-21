# Opis zgłoszenia

## Tytuł

Biurokratka: kompilator formularzy urzędowych do formularzy elektronicznych COI

## Opis projektu (ok. 330 słów)

Biurokratka zamienia blankiet formularza urzędowego (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) w JSON konfiguracji formularza elektronicznego dla Generatora Formularzy COI. Użytkownikiem jest urzędnik cyfryzujący e-usługi, który dziś analizuje każdy wzór ręcznie.

Nie budujemy transkrypcji blankietu, tylko kompilator. Parser wyciąga z pliku tekst z układem (pdfplumber dla PDF, Apache Tika dla plików biurowych, RapidOCR dla skanów). Reguły i opcjonalny model językowy open-weight (Qwen3.5-9B, Apache-2.0) zwracają krótką reprezentację pośrednią. Końcowy JSON składa deterministyczny kod z biblioteki sekcji predefiniowanych COI, a linter sprawdza reguły techniczne i naprawia naruszenia. Model nigdy nie pisze końcowego JSON-a, dlatego plik zawsze jest poprawny strukturalnie. Gdy model nie odpowiada, usługa przechodzi na tryb reguł zamiast zwracać błąd. Ten tryb działa też bez sieci.

Co jest w środku: REST API `POST /api/v1/forms`; stanowisko urzędnika z widokiem audytora (tekst blankietu obok e-formularza, podświetlone linie źródłowe pola, pewność rozpoznania) i kolejką wsadową; podgląd e-formularza liczący warunki widoczności na żywo, z walidatorami PESEL, NIP i REGON, także jako osobna trasa dla dowolnego pliku JSON; raport z wynikiem lintera, propozycjami nowych słowników i czasami etapów. Dopasowujemy słowniki i dane z rejestrów, wskazujemy zależności między polami, sekcjami i stronami. Interfejs jest zgodny z zasadami WCAG 2.1 AA.

Wyniki dla formularzy 3, 4, 6, 7, 8 i 9 z materiałów organizatora leżą w katalogu `outputs/`: wszystkie przechodzą linter bez błędów, a przetwarzanie w trybie reguł trwa od 40 do 783 ms. Model przez endpoint open-weight kosztuje ok. 0,001 USD za formularz.

Wdrożenie: trzy kontenery Docker (web, api, tika) na oficjalnych obrazach z przypiętymi wersjami, użytkownik bez uprawnień, system plików tylko do odczytu, jeden opublikowany port. Przesłany plik istnieje wyłącznie w pamięci, w logach jest tylko skrót SHA-256 i rozmiar. Bez modelu usługa nie łączy się z niczym spoza kontenerów. Zależności to wyłącznie open source bez copyleftu; bramka licencyjna sprawdza je automatycznie, a dwa wyjątki (MPL-2.0, przechodnie) opisaliśmy w raporcie do potwierdzenia z mentorem. Docelowo model działa lokalnie na `llama-server`, zmiana wymaga tylko adresu endpointu.

Ograniczenia: skany dają mniej pewne pola, lokalny serwer modelu nie był testowany w czasie hackathonu, import do prawdziwego Generatora wymaga potwierdzenia z COI.

## Pola do uzupełnienia przed wysłaniem

- Link do repozytorium kodu: TODO
- Link do filmu: TODO
- Link do demonstracji: TODO (jeśli publiczne demo działa, patrz `ARCHITECTURE.md`, D24)
- Zespół (imiona i role): TODO
- Macierz formatów 9 × 8 (zgodność wyników między formatami): TODO, po przygotowaniu `research/08-macierz-formatow.md`

## Źródła liczb

`outputs/README.md` (pola, błędy lintera, czasy), `README.md` (koszt, czasy z modelem), `research/09-licencje.md` (licencje), `ARCHITECTURE.md` (potok, Docker).
