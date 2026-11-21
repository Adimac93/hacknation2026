# Porównanie modeli dla kroku A (D20)

Data: 2026-11-21. Narzędzie: `devtools/compare_models.py`, krok A (inwentarz) z `api/src/formcompiler/llm.py`. Oba modele przez EdenAI, endpoint UE, `temperature` 0, `seed` 7, `response_format` z `json_schema` (`strict`).

## Metoda

- Wejście: tekst warstwy tekstowej PDF formularzy 1 i 5 (`pdfplumber`), linie numerowane `L1…` jak w `Document.linearize`.
- Wzorzec pól: strony przedmiotu z `decompile` referencji (`ir.pages[1:-2]`): 4 pola w formularzu 1 i 7 pól w formularzu 5. Adresat i flagi `applicant` ustalone ręcznie z referencji: 1 to „Wójt Gminy Elbląg” (ORGAN), 5 to „Urząd Gminy Ulan-Majorat” (URZAD). W obu referencjach wszystkie trzy flagi to `true`.
- Dwa warianty promptu:
  - `loo`: przykład few-shot tylko z drugiego formularza, więc model nie widzi odpowiedzi. **Te liczby są miarodajne.**
  - `full`: produkcyjny prompt z obiema referencjami. Model widzi wzorcową odpowiedź, więc wynik pokazuje tylko, czy umie ją skopiować.
- Pokrycie: dopasowanie etykiet 1:1 po normalizacji (`slugify`), podobieństwo `difflib` ≥ 0,6. Ta miara zaniża wynik przy dłuższych, ale poprawnych etykietach („Kwota nadpłaty” do „Kwota” to 0,53), dlatego tabela niżej podaje też ocenę ręczną.
- „Nadmiarowe (z biblioteki)”: pola bez dopasowania; w nawiasie te, które dublują sekcje predefiniowane (klucz z `RESERVED_KEYS` albo etykieta podobna ≥ 0,8 do pola biblioteki).
- Koszt policzony z `usage` i cen z `research/05`, sekcja 2a.

## Wyniki

| Model | Formularz | Wariant | Pokrycie | Zgodność typów | Nadmiarowe (z biblioteki) | `applicant` | Adresat | Czas [s] | Tokeny wej./wyj. | Koszt [USD] |
|---|---|---|---|---|---|---|---|---|---|---|
| `mistral/ministral-8b-2512@eu` | 1 | loo | 1/4 | 100% | 7 (2) | 3/3 | nie | 6.2 | 4014/840 | 0.00080 |
| `flexai/Qwen3.5-9B@eu` | 1 | loo | 4/4 | 100% | 0 (0) | 3/3 | nie | 3.0 | 3765/272 | 0.00042 |
| `mistral/ministral-8b-2512@eu` | 5 | loo | 2/7 | 100% | 6 (0) | 3/3 | tak | 8.4 | 2770/906 | 0.00061 |
| `flexai/Qwen3.5-9B@eu` | 5 | loo | 2/7 | 100% | 5 (0) | 3/3 | nie | 4.6 | 2565/555 | 0.00034 |
| `mistral/ministral-8b-2512@eu` | 1 | full | 4/4 | 100% | 0 (0) | 3/3 | tak | 4.5 | 4614/457 | 0.00084 |
| `flexai/Qwen3.5-9B@eu` | 1 | full | 4/4 | 100% | 0 (0) | 3/3 | tak | 3.5 | 4312/273 | 0.00047 |
| `mistral/ministral-8b-2512@eu` | 5 | full | 5/7 | 100% | 5 (0) | 3/3 | tak | 15.9 | 3841/1260 | 0.00084 |
| `flexai/Qwen3.5-9B@eu` | 5 | full | 4/7 | 100% | 1 (0) | 3/3 | tak | 4.2 | 3535/450 | 0.00042 |

Koszt łączny: 0,0047 USD za 8 wywołań, plus 0,0022 USD za powtórzenie wariantu `loo` (niżej). Oba modele odpowiedziały poprawnym JSON-em w pierwszej próbie.

### Ocena ręczna wariantu `loo` (pola merytorycznie poprawne)

| | Ministral-3-8B | Qwen3.5-9B |
|---|---|---|
| Formularz 1 | 4/4, ale z rozwlekłymi etykietami („Miejscowość, w której znajduje się budynek”). Dodatkowo wymyślone pola „Numer budynku” i „Numer lokalu” oraz telefon i e-mail, które dublują bibliotekę | 4/4, etykiety jak w referencji, bez nadmiarowych pól |
| Formularz 5 | 6/7: brak wyboru RADIO „zaliczyć albo zwrócić”, zamiast niego dwa osobne pola tekstowe. Dodatkowo dwa puste „Dokument załączony 1/2” | 5/7: jest RADIO z dwiema opcjami, brak pól „nazwa podatku” i „numer rachunku”. Dodatkowo „Liczba załączników” (NUMBER, zbędne) |
| Razem trafione | 10/11 | 9/11 |
| Precyzja (trafione / zwrócone) | 10/16 = 62% | 9/11 = 82% |
| Adresat | f1: ORGAN pomylony na URZAD; f5: poprawny | f1: „Urząd Gminy Elbląg”, URZAD (powinien być „Wójt Gminy Elbląg”, ORGAN); f5: niepełna nazwa „Urząd Gminy” |

### Powtarzalność

Wariant `loo` uruchomiłem drugi raz z tym samym ziarnem. Qwen3.5-9B zwrócił identyczne odpowiedzi w obu formularzach. Ministral zwrócił inne odpowiedzi w obu formularzach; pokrycie w formularzu 5 zmieniło się z 2/7 na 3/7. Przez EdenAI Ministral nie jest więc deterministyczny mimo `temperature` 0 i `seed`. Lokalny `llama-server` z tym samym ziarnem powinien być powtarzalny, ale tego nie sprawdziliśmy.

## Rekomendacja

**Qwen3.5-9B**, z zastrzeżeniem małej próby (dwa formularze).

- Merytorycznie oba modele są blisko: Ministral trafia o jedno pole więcej, Qwen ma wyraźnie wyższą precyzję i nie dubluje sekcji predefiniowanych.
- Qwen trzyma styl etykiet z referencji i jako jedyny złożył wariantowy wybór w RADIO bez podpowiedzi. Ministral pisze etykiety opisowe, które trzeba by skracać.
- Qwen był 2–3 razy szybszy i zwrócił 1,5–3 razy mniej tokenów wyjścia. Lokalnie liczba tokenów wyjścia przekłada się wprost na czas odpowiedzi.
- Tylko Qwen był powtarzalny przez API.
- Ryzyka Qwena:
  - EdenAI nie potwierdza dla niego parametru `seed`, a mimo to odpowiedzi były identyczne,
  - przez EdenAI nie zwrócił tokenów rozumowania, ale w lokalnym `llama-server` tryb rozumowania trzeba wyłączyć w konfiguracji serwera (szablon czatu), nie w kliencie, który zostaje neutralny,
  - Q4 ok. 6 GB wobec 5,5 GB dla Ministrala.

Bez względu na model do poprawy w prompcie kroku A (oba modele mylą się tak samo):

- adresat: „Wójt/Burmistrz …” to ORGAN z nazwą funkcji, a nazwę urzędu trzeba brać w całości z bloku adresata,
- nie tworzyć pól na puste pozycje listy załączników („Dokument załączony 1/2”, „Liczba załączników”); wystarczy jedno `FILE_UPLOADER` na każdy nazwany załącznik,
- pola zależne od wariantu (rachunek przy zwrocie, tytuł przy zaliczeniu) wypisywać obok RADIO.
- `to_subject_pages` już naprawia klucze spoza ASCII (Qwen zwrócił `obręb`).

Przed zamknięciem D20 warto puścić oba modele na formularzach 3, 4 i 6 i ocenić wyniki ręcznie (bez wzorca). Koszt to ułamek centa.

## Przykład odpowiedzi Qwen3.5-9B (formularz 5, wariant `loo`)

```json
{"section": "Uzasadnienie wniosku", "key": "uzasadnienie", "label": "Uzasadnienie", "type": "TEXTAREA", "required": true, "src": ["L20", "L21", "L22", "L23"]}
{"section": "Sposób zaliczenia/zwrócenia", "key": "sposob_zaplaty", "label": "Sposób zaliczenia/zwrócenia kwoty", "type": "RADIO", "required": true, "options": ["Zaliczyć na poczet przyszłego zobowiązania podatkowego", "Zwrócić przelewem na wskazany rachunek"], "src": ["L24", "L25", "L27"]}
{"section": "Dane wnioskodawcy", "key": "kwota_nadplaty", "label": "Kwota nadpłaty", "type": "NUMBER", "required": true, "src": ["L18"]}
{"section": "Załączniki", "key": "plik_korekta_deklaracji", "label": "Korekta deklaracji", "type": "FILE_UPLOADER", "required": true, "src": ["L31"]}
```

Surowe odpowiedzi i `results.jsonl` są w katalogu tymczasowym autora, poza repo. Odtworzenie z `api/`: `uv run python ../devtools/compare_models.py --out <katalog>`.

## Decyzja (18:50)

Model docelowy: **Qwen3.5-9B** (D20, D3). Na hackathonie `flexai/Qwen3.5-9B@eu` przez EdenAI. Poprawki promptu kroku A z listy wyżej wchodzą niezależnie od modelu.

## Runda 2: formularze 3, 4, 6

Data: 2026-11-21, wieczór. Tylko `flexai/Qwen3.5-9B@eu`. Prompt kroku A po poprawkach z listy wyżej:

- adresat z bloku adresata: funkcja to ORGAN, a nazwa urzędu w całości,
- jedno `FILE_UPLOADER` na każdy nazwany załącznik, bez pól na puste pozycje listy,
- pola zależne od wariantu wypisane zaraz po RADIO, z nowym polem `show_if_option` (`field_key`, `value`), które `to_subject_pages` zamienia na `Cond` IR.

Formularze 3, 4 i 6 nie mają wzorca, a prompt zawiera przykłady tylko z referencji 1 i 5 (D12), więc model tych formularzy nie widział. Przebieg jest taki jak w usłudze: tekst PDF (`pdfplumber`), potem `heuristics.analyze`, `llm.refine`, `sections.assemble`, `compiler.build` i `lint.fix`. Narzędzie: `devtools/compare_models.py --unlabeled 3 4 6`.

| Formularz | Pola | Trafne | Zbędne lub błędne | Brakujące | Adresat | Lint (błędy / ostrzeżenia) | Czas [s] | Tokeny wej./wyj. | Koszt [USD] |
|---|---|---|---|---|---|---|---|---|---|
| 3. Zaświadczenie | 5 | 4 | 1 (pole „Inny cel” dwa razy, jako TEXT_FIELD i jako TEXTAREA) | brak | dobrze: „Urząd Miasta i Gminy Młynary”, URZAD | 0 / 6 (L103) | 5.7 | 3898/590 | 0.00048 |
| 4. Świetlica | 11 | 6 | 5 (4 oświadczenia jako CHECKBOX bez opcji; „Zgoda osoby odpowiedzialnej” jako TEXT_FIELD) | RADIO „wynajęcie albo użyczenie” | dobrze: „Wójt Gminy Płoskinia”, ORGAN | 0 / 9 (L103) | 7.0 | 3944/873 | 0.00052 |
| 6. Pas drogowy | 21 | 20 | 1 (plik pełnomocnictwa dubluje bibliotekę) | adres osoby odpowiedzialnej („zam.”); drobiazg | źle: „Burmistrz Miasta i Gminy w Daleszycach” z klauzuli RODO, do tego URZAD; na blankiecie jest „Urząd Miasta i Gminy Miasteczko” | 0 / 12 (L103) | 12.8 | 4819/1646 | 0.00093 |

Koszt rundy 2: 0,0017 USD za trzy formularze plus 0,0008 USD za powtórkę `loo`. Każde wywołanie przeszło w pierwszej próbie. Każdy formularz złożył się w poprawny JSON bez błędów lintera; ostrzeżenia to wyłącznie L103 (długie słowa w etykietach i tekstach).

Jakość etykiet: krótkie i rzeczowe, np. „Numer ewidencyjny działki”, „Data rozpoczęcia robót”, „Szczegółowy plan sytuacyjny”, „Instytucja, do której złożony zostanie wniosek”. Słabsze:

- „Cel złożenia zaświadczenia” (formularz 3) zamiast „Czego ma dotyczyć zaświadczenie”,
- powierzchnie w formularzu 6 jako TEXT_FIELD z jednostką w etykiecie („- m2”) zamiast NUMBER,
- „Przewidywana ilość uczestników” w formularzu 4 jako TEXT_FIELD zamiast NUMBER,
- tytuły stron przedmiotu bywają mylące („Dane wnioskodawcy” dla celu zaświadczenia).

Dobre przeprojektowanie: w formularzu 6 model zamienił tabelę „długość × szerokość × razem” (po dwa wiersze na kategorię) na jedno pole powierzchni na kategorię, dołożył pole „Całkowita powierzchnia zajęcia” i nie powielał wierszy. W formularzu 3 dodał załącznik z potwierdzeniem opłaty skarbowej, wywnioskowany z pouczenia o opłacie 17 zł, i pole „Inny cel” z warunkiem `show_if` na opcji „Inne”.

### Przykład: formularz 3 po poprawkach

```text
strona „Dane wnioskodawcy” (nazwa do poprawy), adresat: Urząd Miasta i Gminy Młynary (URZAD), applicant: wszystkie flagi true
sekcja „Cel wniosku”
  cel_zlozenia_zaswiadczenia  CHECKBOX, wymagane  „Cel złożenia zaświadczenia”
    opcje: Ilość posiadanych użytków rolnych w hektarach fizycznych i przeliczeniowych;
           Ilość dzierżawionych użytków rolnych …; Okres posiadania gospodarstwa rolnego;
           Nieposiadanie użytków rolnych / gospodarstwa rolnego na terenie Gminy Młynary; Inne
  cel_zlozenia_zaswiadczenia_inne  TEXT_FIELD  „Inny cel (proszę wpisać)”  show_if: cel = „Inne”
  cel_zlozenia_zaswiadczenia_inny  TEXTAREA    „Inny cel (proszę wpisać)”  show_if: cel = „Inne”   ← duplikat
  instytucja_do_ktorej_zlozony_wniosek  TEXT_FIELD, wymagane  „Instytucja, do której złożony zostanie wniosek”
sekcja „Załączniki”
  plik_potwierdzenia_przelewu  FILE_UPLOADER, wymagane  „Potwierdzenie uiszczenia opłaty skarbowej”
```

### Formularze 1 i 5 (`loo`) przed i po poprawkach promptu

| Formularz | Przed: pokrycie, nadmiarowe, adresat | Po: pokrycie, nadmiarowe, adresat |
|---|---|---|
| 1 | 4/4, 0, źle („Urząd Gminy Elbląg”, URZAD) | 4/4, 0, **dobrze** („Wójt Gminy Elbląg”, ORGAN) |
| 5 | 2/7 automatycznie (5/7 ręcznie), 5, źle („Urząd Gminy”) | 3/7 automatycznie (6/7 ręcznie), 3, **dobrze** („Urząd Gminy Ulan-Majorat”) |

W formularzu 5 zniknęły „Liczba załączników” i „Dodatkowe załączniki”. Pojawił się `show_if_option`: „Numer rachunku bankowego” jest widoczny tylko przy opcji „Zwrócić przelewem na wskazany rachunek” i poprawnie przechodzi na `Cond`. Nadal brakuje pola „Nazwa podatku” przy zaliczeniu. „Kwota nadpłaty” spadła z NUMBER na TEXT_FIELD.

### Wnioski i dalsze poprawki

1. Adresat działa, gdy blok adresata jest jednoznaczny (1, 3, 4, 5). W formularzu 6 blok ma tylko „Urząd Miasta i Gminy / Miasteczko”, a model wolał nazwę z klauzuli RODO. Do promptu: „bierz adresata tylko z bloku adresata, nigdy z klauzuli informacyjnej”. Spójność rodzaju z nazwą (słowo „Burmistrz” w nazwie daje ORGAN) warto wymusić w `refine`, kodem.
2. Oświadczenia nadal trafiają jako CHECKBOX bez opcji (formularz 4). Łamie to zasadę „zgody i oświadczenia tylko w CONSENT_SECTION”, a linter tego nie złapał. Do zrobienia:
   - w `to_subject_pages` odrzucać CHECKBOX bez opcji albo zamieniać go na treść zgody,
   - w linterze dodać regułę na CHECKBOX bez opcji i bez słownika.
3. Typy liczbowe: dopisać do promptu „powierzchnia, liczba osób, kwota to NUMBER”.
4. Duplikaty pól zależnych („Inny cel” dwa razy): w `to_subject_pages` scalać pola o tej samej etykiecie w jednej sekcji.
5. Brak RADIO „wynajęcie albo użyczenie” (formularz 4): wybór zapisany w tytule z gwiazdką „niepotrzebne skreślić” model pomija. Kandydat na heurystykę: ukośnik plus przypis „niepotrzebne skreślić” w tytule daje RADIO.

### Runda 2b: poprawki po rundzie 2 (formularze 4 i 6)

Zmiany:

- prompt: adresat „tylko z bloku adresata, nigdy z klauzuli informacyjnej”; NUMBER także dla liczby osób i powierzchni,
- `refine`: rodzaj adresata wynika z początku nazwy (Wójt, Burmistrz, Prezydent, Starosta, Marszałek, Zarząd to ORGAN; Urząd, Starostwo to URZAD), a pusty adresat wraca do wyniku heurystyk.

Koszt: 0,0013 USD.

- **Formularz 4: wyraźna poprawa.** Bez oświadczeń jako CHECKBOX, „Przewidywana ilość uczestników” jako NUMBER, „Zgoda osoby odpowiedzialnej” jako FILE_UPLOADER. Pól jest 8. Nowe zbędne pole: „Zgoda na korzystanie ze świetlicy” (FILE_UPLOADER). Nadal brakuje RADIO „wynajęcie albo użyczenie”.
- **Formularz 6: wynik mieszany.**
  - Adresat nadal z klauzuli RODO („Burmistrz Miasta i Gminy w Daleszycach”). Teraz ma przynajmniej spójny rodzaj ORGAN, ale nazwa nie pochodzi z blankietu. Blok adresata jest tu niepełny („Urząd Miasta i Gminy / Miasteczko”), więc model szuka pełnej nazwy gdzie indziej.
  - Powierzchnie spadły z TEXT_FIELD do TEXTAREA.
  - Doszły „Liczba dni realizacji” (NUMBER, sensowne) i błędne „Zaświadczenie (zam.)”.
  - Odpowiedzi tego samego modelu przy niewielkiej zmianie promptu potrafią się wyraźnie zmienić, więc pojedynczy przebieg jest słabą miarą.

Otwarte: punkty 2, 4 i 5 z listy wyżej (CHECKBOX bez opcji w linterze, scalanie duplikatów, RADIO z „niepotrzebne skreślić”) oraz adresat przy niepełnym bloku. Dla adresata rozsądny kierunek to porównanie z blokiem adresata z heurystyk i odrzucenie nazwy, której słów nie ma w nagłówku blankietu.

## Runda 3: pełny `pipeline.process` na formularzach 3, 4, 6 i 7

Data: 2026-11-21, noc. `flexai/Qwen3.5-9B@eu`, `LLM_ENABLED=true`, dokument z `devtools/compare_models.load_document` (tekst PDF), potem `pipeline.process`: heurystyki, `llm.refine`, `assemble`, `build` i `lint.fix`. Narzędzie: `compare_models.py --pipeline 3 4 6 7`.

Zmiany przed tą rundą, wszystkie deterministyczne i pokryte testami w `tests/test_llm.py`:

- `clean_inventory` (czysta funkcja) poprawia odpowiedź modelu, zanim stanie się IR:
  - usuwa pola, które dublują sekcje predefiniowane: dane osobowe i kontaktowe po kluczu i etykiecie (dokładnie albo z podobieństwem ≥ 0,9), wszystko o pełnomocnictwie oraz części adresu (ulica, miejscowość, kod, numer domu) w sekcji o wnioskodawcy,
  - usuwa oświadczenia do odhaczenia (CHECKBOX bez opcji z etykietą „Oświadczam/Zapoznałem/Zobowiązuję…”) i zgody,
  - pole wyboru bez opcji i bez słownika zamienia na TEXT_FIELD (to samo robi też `_field`, więc reguła L025 nie ma czego łapać),
  - usuwa zduplikowane etykiety w obrębie sekcji,
  - pola ze stron o tytułach udających strony biblioteki („Dane…”, „Kontakt…”, „Zgody…”, „Strona końcowa”, „Podsumowanie”) przenosi na pierwszą dozwoloną stronę przedmiotu albo na stronę „Szczegóły wniosku”,
  - `show_if_option` zostawia tylko wtedy, gdy linie źródłowe pola leżą w zakresie linii pola wyboru, czyli pole jest w tekście częścią wariantu.
- `refine`:
  - adresata przyjmuje tylko wtedy, gdy każde słowo nazwy występuje nad tytułem wniosku (z tolerancją odmiany); inaczej zostaje adresat z heurystyk,
  - flagi `entities` i `proxy` bierze od modelu tylko przy śladzie w tekście (NIP, REGON, KRS, osoba prawna, nazwa firmy, siedziba; pełnomocnik, osoba upoważniona); inaczej zostają wartości z heurystyk.
- Prompt:
  - flagi `true` tylko przy wyraźnym śladzie, a w przykładzie z referencji 1 `proxy=false`, bo blankiet nie wspomina pełnomocnika,
  - tytuły stron od przedmiotu sprawy, nigdy „Dane…” ani „Kontakt…”,
  - warianty „A/B*” z przypisem „niepotrzebne skreślić” dają RADIO,
  - warunek tylko dla pól wewnątrz wariantu,
  - pomijanie oświadczeń.
- Linter: nowa reguła **L025** (`error`): pole SELECT, RADIO albo CHECKBOX bez opcji i bez słownika.

| Formularz | Lint (błędy / ostrzeżenia) | Strony / pola przedmiotu | Trafne | Zbędne lub błędne | Brakujące | Flagi (persons, entities, proxy) | Adresat | Czas modelu [s] | Tokeny | Koszt [USD] |
|---|---|---|---|---|---|---|---|---|---|---|
| 3. Zaświadczenie | 0 / 1 | 2 / 5 | 4 | 1: „Liczba egzemplarzy” (blankiet wspomina egzemplarze tylko w pouczeniu o opłacie) | brak | T, N, N (dobrze) | Urząd Miasta i Gminy Młynary, URZAD (dobrze) | 7.1 | 4080/567 | 0.00052 |
| 4. Świetlica | 0 / 5 | 1 / 8 | 7 | 1: „Zgoda osoby odpowiedzialnej” jako TEXT_FIELD; powinien być FILE_UPLOADER z warunkiem | brak; RADIO „Wynajem / Użyczenie” jest | T, N, N (dobrze) | Wójt Gminy Płoskinia, ORGAN (dobrze) | 6.5 | 4126/968 | 0.00056 |
| 6. Pas drogowy | 0 / 12 | 3 / 18 | 16 | 2: powierzchnie jako TEXT_FIELD zamiast NUMBER; „Termin realizacji robót” jako jedno pole tekstowe zamiast dwóch dat | data od/do (zastąpiona polem tekstowym) | T, T, T (dobrze: „nazwa firmy”, pełnomocnik) | „Urząd Miasta i Gminy”, URZAD; nazwa z RODO odrzucona, wynik z heurystyk niepełny (bez „Miasteczko”) | 9.7 | 5001/1487 | 0.00072 |
| 7. Psy | 0 / 8 | 1 / 16 | 11 | 5: „Rodzaj wniosku” jako jedno RADIO z 5 pomieszanymi kombinacjami (powinny być 2 wybory); „Rodzaj psa” dubluje tę informację; oznakowanie rozbite na pole „Mikroprocesor” + RADIO „Tatuaż/Brak” zamiast jednego RADIO z 3 opcjami; „Numer konta” to konto urzędu, nie dana wnioskodawcy; „Imię psa” zamiast imienia poprzedniego właściciela | załącznik: kopia zaświadczenia o szczepieniu | T, N, N (dobrze) | Urząd Miejski Wrocławia, URZAD (dobrze) | 11.4 | 5441/1792 | 0.00073 |

Wszystkie cztery formularze przeszły w trybie `llm` w pierwszej próbie i nie mają błędów lintera; ostrzeżenia to tylko L103 (długie słowa). Koszt rundy 3: 0,0058 USD (dwa pełne przebiegi i jeden pokazowy przebieg formularza 3). Powtórka dała identyczne odpowiedzi.

Porównanie z problemami z próby koordynatora (formularz 3) i z rundy 2:

| Problem | Teraz |
|---|---|
| strona „Kontakt i zgody (szczegóły)” z telefonem i e-mailem | brak; pola wycięte jako duplikaty biblioteki, strona nie powstaje |
| strona przedmiotu „Dane wnioskodawcy” | „Cel zaświadczenia”; pola z zakazanych tytułów trafiłyby na pierwszą dozwoloną stronę |
| `entities` i `proxy` równe `true` w prostym wniosku | w 3, 4 i 7 `false` (brak śladu w tekście); w 6 `true`, bo tekst ma „nazwa firmy” i pełnomocnika |
| warunek SHOW na polu „Podmiot…” | brak; warunek zostaje tylko przy „Inny cel”, wewnątrz opcji „Inne” |
| CHECKBOX bez opcji (formularz 4) | brak; oświadczenia wycięte, a reguła L025 pilnuje reszty |
| duplikat „Inny cel” | brak |
| RADIO z „niepotrzebne skreślić” (formularz 4) | jest: „Wynajem / Użyczenie” |
| adresat z klauzuli RODO (formularz 6) | odrzucony; zostaje adresat z heurystyk |
| adres wnioskodawcy w przedmiocie (formularz 7, pierwszy przebieg) | wycięty regułą „część adresu w sekcji o wnioskodawcy” |

### Formularz 3 po poprawkach (cały formularz)

```text
Wniosek o wydanie zaświadczenia                                 tryb: llm, 0 błędów lintera
Strona „Dane”
  Urząd, do którego jest składany wniosek: Nazwa urzędu (Urząd Miasta i Gminy Młynary)
  Twoje dane: Imię, Nazwisko, Numer PESEL
  Adres zamieszkania: Kraj (słownik Kraje), Miejscowość, Kod pocztowy, Ulica, TERYT, Numer budynku, Numer lokalu
  (bez sekcji firmy i pełnomocnika: entities=false, proxy=false)
Strona „Cel zaświadczenia”
  Rodzaj zaświadczenia
    CHECKBOX, wymagane: Cel złożenia zaświadczenia
      opcje: Ilość posiadanych użytków rolnych …; Ilość dzierżawionych użytków rolnych …;
             Okres posiadania gospodarstwa rolnego; Nieposiadanie użytków rolnych … Gminy Młynary; Inne
    TEXT_FIELD: Inny cel (proszę wpisać)          widoczne, gdy wybrano „Inne”
  Cel złożenia: TEXT_FIELD „Instytucja, do której złożone zostanie zaświadczenie”
  Liczba egzemplarzy: NUMBER „Liczba egzemplarzy”   ← zbędne
Strona „Opłata”
  Opłata: FILE_UPLOADER „Plik potwierdzenia wpłaty opłaty skarbowej”
Strona „Kontakt i zgody” (z biblioteki): Numer telefonu, Adres e-mail, zgoda
Strona „Strona końcowa” (z biblioteki)
```

### Co dalej

1. Typy liczbowe i daty nadal zależą od formularza: w 6 powierzchnie są TEXT_FIELD, a termin jest jednym polem tekstowym. Możliwa naprawa kodem: etykieta z „m2”, „powierzchni”, „liczb…”, „ilość” daje NUMBER, a etykieta „termin … od … do” daje dwa pola DATEPICKER.
2. Formularz 7 ma złożone wybory („hodowanie/utrzymywanie* charta/chartów* lub mieszańca…*”), które model skleja w jedno RADIO z kombinacjami. Lepszy przykład few-shot nie wchodzi w grę (D12), więc zostaje instrukcja: każdy ukośnik z gwiazdką to osobne RADIO.
3. Dane urzędu (numer konta, opłata 82 zł) powinny trafiać do TEXT_BLOCK, a nie do pola do wypełnienia.
4. Adresat przy niepełnym bloku (formularz 6): heurystyka obcina nazwę po pierwszej linii („Urząd Miasta i Gminy” bez „Miasteczko”). Poprawka należy do `heuristics.py` (sklejanie kolejnej linii bloku), poza zakresem tego zadania.
