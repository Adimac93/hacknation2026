# 07 — Korpus formularzy urzędowych: skąd brać blankiety do testów

Stan na 2026-11-21. Pomiary własne: narzędzia `devtools/corpus/`, uruchomione w kontenerze LXC 117 `wobbegong-corpus` na PVE (Debian 13, 4 rdzenie, 4 GB RAM). Kontener nie uruchamia żadnego modelu.

## Po co

Do ewaluacji i testów odporności, nie do trenowania. Próbki organizatora to 9 formularzy, a na obronie przyjdzie nowy plik. Potrzebujemy setek blankietów w różnych układach i formatach, w tym **wielu wariantów tych samych typów formularzy z różnych gmin**, żeby sprawdzić, czy usługa daje spójny wynik dla tej samej treści w innym układzie.

## Rekomendacja

1. **API ELI Sejmu jako źródło wzorów centralnych.** Deterministyczne, bez scrapingu, dobrze opisane. Daje około 1,1 tys. wzorów w PDF, w tym rastrowe.
2. **Indeks Common Crawl jako źródło formularzy gminnych.** Zapytanie do kolumnowego indeksu Parquet przez DuckDB, a pliki z archiwów WARC. Serwerów gmin nie dotykamy wcale.
3. **Długie przebiegi tylko na stabilnym łączu** (LXC na PVE). Wi-Fi na hackathonie zrywało DNS co kilka minut.
4. **Korpus nie trafia do repozytorium.** Commitujemy narzędzia i ten raport. Pliki leżą w `corpus/` (ignorowane przez git) i w kontenerze w `/opt/guppy/corpus`.

## Źródło 1: API ELI (`devtools/corpus/eli.py`)

Wyszukiwanie obowiązujących aktów po frazach w tytule („wzoru wniosku”, „wzorów formularzy”, „wzoru deklaracji”, „wzoru zgłoszenia”, „wzoru oświadczenia” i podobnych, razem 12 fraz), pobranie PDF aktu, pocięcie na załączniki, manifest JSONL z cechami.

```sh
uv run devtools/corpus/eli.py --out corpus
```

| Miara | Wartość |
|---|---|
| Akty znalezione (po odfiltrowaniu legitymacji, odznak, tablic itp.) | 556 |
| Akty z co najmniej jednym załącznikiem | 464 |
| Załączniki (osobne PDF-y) | 1160 |
| Kandydaci na formularz | **1065** (5658 stron, mediana 2 strony) |
| Załączniki rastrowe (skan w PDF) | 128 |
| Rozmiar wyciętych załączników | 523 MB |
| Czas pełnego przebiegu na LXC | około 10 min |

Kandydaci według typu w tytule aktu: wnioski 418, formularze 240, deklaracje 199, oświadczenia 97, zgłoszenia 66, informacje 30, zawiadomienia 15. Według lat: 2000–2009 około 130, 2010–2019 około 420, od 2020 około 520.

Kandydat na formularz to załącznik z co najmniej jedną z cech: 5 wykropkowań, 3 kratki (także glify z prywatnego obszaru Unicode, gdzie fonty symboliczne trzymają kratki), 40 ścieżek wektorowych na stronę, słowo „podpis” razem z nagłówkiem typu WNIOSEK/WZÓR, albo raster. Odrzucone załączniki to głównie teksty jednolite rozporządzeń w obwieszczeniach, wzory kopert wyborczych i fragmenty aktów zmieniających.

### Pułapki zmierzone na danych

- **Etykiety załączników nie stoją na początku strony.** W formularzach składanych graficznie kolejność tekstu jest dowolna: „Załącznik nr 1” bywa w środku albo na końcu warstwy tekstowej. Szukamy etykiety na całej stronie.
- **Etykiety powtarzają się i rozpadają.** Na stronach rastrowych etykieta występuje dwa razy i bywa przecięta w środku liczby: `Załącznik nr 1\r\n5`, `Załącznik nr Załącznik nr 18 18`, `ZAŁĄCZNIK nr 24`. Nowy segment zaczynamy tylko wtedy, gdy największy numer na stronie rośnie.
- **Stare PDF-y Dziennika Ustaw (około 2005–2010) mają przesunięte kodowanie fontów**: `Za∏àcznik` zamiast „Załącznik”. Mapowanie: `∏→ł, à→ą, Ê→ś, ´→ę, ˝→ż, ƒ→ń, ç→ć`, do tego znak `U+FFFE` w środku słów. Naprawiamy tylko tekst zawierający `∏`, bo ten znak nie występuje w poprawnym polskim tekście. Po naprawie liczba aktów bez wykrytego załącznika spadła ze 149 do 92, a liczba kandydatów wzrosła z 936 do 1065.
- **Około 90 aktów naprawdę nie ma wzoru w treści**: akty zmieniające, 1–2 strony, wzór opublikowany gdzie indziej.
- Nasz `ingest` będzie miał te same problemy z nowymi plikami PDF, więc te przypadki warto przenieść do testów ingestu.

## Źródło 2: Common Crawl (`devtools/corpus/commoncrawl.py`)

```sh
uv run devtools/corpus/commoncrawl.py index --crawls 6 --out corpus
uv run devtools/corpus/commoncrawl.py fetch --out corpus
```

Jak to działa:

1. Kolumnowy indeks URL-i Common Crawl to 300 plików Parquet na crawl, posortowanych po kluczu SURT. Ze stopek plików (statystyki `url_surtkey`) wybieramy te, które obejmują `pl,`. Dla CC-MAIN-2026-43 to 6 plików i 26 grup wierszy, około 37 mln URL-i z domen `.pl`.
2. Te pliki pobieramy w całości i odpytujemy lokalnie w DuckDB (zdalny odczyt samych grup wierszy działa, ale wywołuje blokadę, patrz pułapki). Filtr: status 200, typ wykryty przez crawler (PDF, DOC, DOCX, ODT, RTF, XLS, XLSX, ODS), w ścieżce `wniosek`, `formularz`, `druk`, `deklaracja`, `zgłoszenie`, `wzór`, `oświadczenie`. Deduplikacja po skrócie treści, wygrywa najnowsze pobranie.
3. `fetch` czyta każdy rekord zakresowym GET z pliku WARC (`warcio`), rozpoznaje format po sygnaturze i zapisuje plik pod skrótem SHA-256. Domyślnie bierze tylko hosty urzędowe (`gov.pl`, `bip`, `gmina`, `powiat`, `starostwo`, `um.`, `ug.` …) i URL-e pasujące do typów formularzy z zadania.

Jeden crawl (CC-MAIN-2026-43), zapytanie w 28 s:

| Miara | Wartość |
|---|---|
| Dokumenty pasujące do filtra | 22 888 |
| Unikalne treści | 21 453 |
| Domeny | 5 275 |
| W tym z hostów urzędowych | około 4,4 tys. |
| PDF / ODT / DOCX / DOC / XLSX | 21 951 / 403 / 301 / 122 / 75 |

Typy formularzy z zadania w jednym crawlu (dopasowanie po URL):

| Typ | Dokumenty | Domeny |
|---|---|---|
| zaświadczenie | 181 | 119 |
| stypendium, nagroda sportowa | 158 | 102 |
| deklaracja odpadowa | 127 | 62 |
| świetlica | 61 | 52 |
| zajęcie pasa drogowego | 21 | 9 |
| nadpłata | 15 | 15 |
| psy ras agresywnych | 12 | 9 |
| numer porządkowy | 9 | 9 |

Sześć ostatnich crawli (CC-MAIN-2026-21 do 2026-43), po 6–7 plików indeksu `.pl` na crawl, razem około 25 min na LXC:

| Miara | Wartość |
|---|---|
| Wiersze z sześciu crawli | 150 386 |
| Unikalne treści | 130 233 |
| Z hostów urzędowych | 25 020 |
| Wybrane do pobrania (host urzędowy albo typ z zadania) | **27 096** z 3 368 hostów |
| PDF / DOCX / DOC / ODT / XLS(X) / RTF wśród wybranych | 23 934 / 1 489 / 865 / 624 / 145 / 29 |

Typy formularzy z zadania po sześciu crawlach (dopasowanie po URL, reguły zaostrzone względem tabeli wyżej):

| Typ | Dokumenty | Hosty |
|---|---|---|
| zaświadczenie | 1 040 | 654 |
| deklaracja odpadowa | 729 | 390 |
| świetlica | 289 | 238 |
| zajęcie pasa drogowego | 189 | 87 |
| nadpłata | 94 | 76 |
| numer porządkowy | 88 | 78 |
| stypendium, nagroda sportowa | 40 | 33 |
| psy ras agresywnych | 20 | 18 |

Pobrane pliki typów z zadania: 2476 (PDF 2304, ODT 81, DOCX 65, DOC/XLS 24, RTF 2), 0 błędów. Ocena PDF-ów tą samą funkcją co dla ELI:

| Typ | PDF | Kandydat na formularz | Skan bez tekstu | Do 4 stron |
|---|---|---|---|---|
| zaświadczenie | 951 | 95% | 91 | 95% |
| deklaracja odpadowa | 692 | 88% | 84 | 78% |
| świetlica | 268 | 97% | 17 | 91% |
| zajęcie pasa drogowego | 166 | 95% | 9 | 98% |
| nadpłata | 91 | 97% | 3 | 100% |
| numer porządkowy | 83 | 100% | 20 | 100% |
| stypendium, nagroda sportowa | 34 | 94% | 3 | 71% |
| psy ras agresywnych | 19 | 95% | 1 | 100% |
| **razem** | **2304** | **93%** | **228** | **89%** |

228 skanów bez warstwy tekstowej to materiał do testów OCR na prawdziwych skanach zamiast próbek pogorszonych syntetycznie.

Pozostałe dokumenty urzędowe bez przypisanego typu (około 24,6 tys.) pobierają się w kontenerze. Pierwsze 5,5 tys. pobrań: 98% zapisanych, 1,7% obciętych przez crawler, 0 błędów i 0 blokad. Korpus zostaje na PVE: testy wsadowe uruchamiamy tam, bo łącze jest stabilniejsze niż na laptopie.

### Pułapki

- **CloudFront blokuje adres po gęstej serii małych zapytań.** Odczyt stopek 300 plików naraz, a potem zdalny skan grup wierszy (tysiące zapytań o zakresy bajtów), kończyły się odpowiedzią 403 „Request blocked” na około 20 minut. Progów Common Crawl nie publikuje. Rozwiązanie: stopki czytamy po kolei z przerwą 0,5 s i zapisujemy listę plików `.pl` w cache dla każdego crawla, a potrzebne pliki indeksu (około 670 MB każdy, około 4 GB na crawl) **pobieramy w całości jednym strumieniowym GET z wznawianiem** i odpytujemy lokalnie. Po tej zmianie żaden z sześciu crawli nie dostał blokady. Każde 403, 429 i 503 jest ponawiane z przerwą od 1 do 30 minut, a wynik każdego crawla zapisujemy osobno, więc przerwany przebieg wznawia się od miejsca przerwania.
- **Serwer CDX (`index.commoncrawl.org`) nie radzi sobie z wieloznacznikiem domeny** (`*.gov.pl` zwraca 504). Indeks Parquet działa bez problemu.
- **Crawler obcina duże odpowiedzi** (nagłówek `WARC-Truncated`). Takich plików nie zapisujemy, manifest je odnotowuje. Gdyby było ich dużo, można je dociągnąć ze źródła z zachowaniem `robots.txt`.

## Inne źródła (nie zrealizowane)

| Źródło | Dlaczego później |
|---|---|
| BIP-y gmin, crawl bezpośredni (listę dają comiesięczne dane Katalogu Podmiotów Publicznych na dane.gov.pl) | Common Crawl pokrywa ten sam materiał bez obciążania 2,5 tys. serwerów |
| Dzienniki urzędowe województw (uchwały ze wzorami deklaracji odpadowych i regulaminami stypendiów) | 16 różnych serwisów, scraping. Dobre źródło wariantów formularzy 8 i 9 |
| ePUAP, Centralne Repozytorium Wzorów Dokumentów Elektronicznych | Nie znaleźliśmy aktualnej, publicznej ścieżki pobierania. Wzory XSD/XSL przydałyby się jako odniesienie dla struktury pól |
| dane.gov.pl | Głównie zbiory danych, prawie bez formularzy |

## Prawo i licencje

- Dokumenty i materiały urzędowe nie są przedmiotem prawa autorskiego (art. 4 ustawy o prawie autorskim i prawach pokrewnych), więc wzory z aktów prawnych i druki urzędów można pobierać i używać do testów. Formularze z hostów nieurzędowych (sklepy z drukami, kancelarie) mogą być chronione, dlatego `fetch` domyślnie ich nie pobiera.
- Common Crawl udostępnia indeks i archiwa na własnych warunkach korzystania, które dopuszczają takie użycie. Prawa do treści zostają przy jej autorach.
- Zależności narzędzi: `httpx` (BSD-3-Clause), `pypdfium2` (Apache-2.0 lub BSD-3-Clause, PDFium BSD), `duckdb` (MIT), `warcio` (Apache-2.0). Bez copyleftu. Narzędzia nie są częścią usługi i nie trafiają do obrazu Docker.

## Jak użyć korpusu

1. Ingest: wszystkie pliki przez `ingest`, bez modelu. Liczymy błędy parsowania, czas, odsetek stron z tekstem i z OCR. Przypadki brzegowe z tego raportu (kolejność tekstu, przesunięte kodowanie, rastry) jako testy regresji.
2. Spójność: warianty tego samego typu z różnych gmin → porównanie IR (zbiór pól, typy, sekcje predefiniowane).
3. Linter: każdy wynik przez `lint` bez błędów. To jest liczba do prezentacji: „N formularzy, 100% przechodzi reguły techniczne”.
