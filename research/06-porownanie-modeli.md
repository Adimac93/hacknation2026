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
