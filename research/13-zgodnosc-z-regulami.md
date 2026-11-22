# 13. Zgodność wyniku z regułami COI (audyt W10)

Audyt sześciu plików `outputs/*.json` (tryb modelu, wygenerowane usługą) i obu referencji względem:
schematu `importowanyPlikJsonSchemat (1).json`, opisu `OpisImportowanegoPlikuJSON (1).docx`,
„Reguł technicznych konfiguracji formularzy” (2), dokumentu „Słowniki”, „Dane inicjalne”
oraz `ARCHITECTURE.md` 5.6.

Wynik: wszystkie 6 plików z `outputs/` przechodzą schemat organizatora (z udokumentowanymi
odstępstwami poniżej) i linter bez błędów, także z nowymi regułami L026–L031.

## Schemat JSON organizatora

Test: `api/tests/test_conformance.py` (zależność dev `jsonschema` 4.26, MIT; zależności
przechodnie `attrs`, `jsonschema-specifications`, `referencing`, `rpds-py`, wszystkie MIT).

| Odstępstwo schematu | Co robimy | Uzasadnienie |
|---|---|---|
| Schemat sprawdza tylko wpisy strony; pola zagnieżdżone leżą w `repetingSectionGrid` (literówka) z `items: {}` | test waliduje każdy element `repeatingSectionGrid` tym samym schematem co wpis strony | referencje i Generator używają `repeatingSectionGrid`; bez tego schemat nie sprawdza żadnego pola wejściowego |
| `defaultValue` jako `string` | dopuszczamy też listę stringów | reguły techniczne: SELECT `"defaultValue": []`; obie referencje mają listę w SELECT |
| `consentSectionConfig.required` na poziomie konfiguracji | `required` w każdej zgodzie | reguły techniczne i obie referencje |
| referencja 1: `validation: {}` w trzech polach | akceptowane tylko dla referencji | błąd tamtego pliku; opis importu: „tablica stringów”; kompilator zawsze pisze listę, `fix` naprawia (L010) |

Wynik przed zmianami (surowy schemat z rekurencją): jedyne błędy to `defaultValue` jako lista w SELECT
(6/6 wyników, 2/2 referencji) i `validation: {}` w referencji 1.

## Reguły techniczne

| Reguła | Jak wymuszamy | Stan |
|---|---|---|
| Tytuł formularza niepusty, najwyżej 255 znaków | L001, `FormIR.title` max 255 | ok |
| Co najmniej dwie strony | L002 + naprawa | ok |
| Strona końcowa oznaczona FINISH, pozostałe MAIN | L003, L004, `schema.Tab.type` Literal | ok |
| Każda strona ma co najmniej jedno pole | L007 | ok |
| Pole tylko w sekcji / sekcji powtarzalnej | L005, kompilator | ok |
| Sekcja na stronie, brak sekcji w sekcji | L006, kompilator | ok |
| Brak pól wejściowych na stronie FINISH | L008 | ok |
| Na FINISH „wyłącznie INFO_SECTION” | L008 dopuszcza też TEXT_BLOCK | znane odstępstwo: obie referencje mają na FINISH sekcję z TEXT_BLOCK; idziemy za referencjami |
| Każde pole ma atrybut obligatoryjności | `validation` zawsze lista (REQUIRED albo pusta), L010 | ok |
| Strony połączone przepływem | L023, L024 + naprawa | ok |
| Zależności jako stany JSONata | kompilator z szablonu, L020–L022 | ok |
| Sekcja: stan tylko SHOW; pole: SHOW lub READ_ONLY | **L031 (nowa)**; TEXT_BLOCK, INFO_SECTION, CONSENT_SECTION tylko SHOW | naprawione teraz (wcześniej niesprawdzane) |
| Typ komponentu z listy 11 | L009, `schema.ComponentType` | ok |
| Walidator z listy 9, dowolny tylko w TEXT_FIELD, w pozostałych tylko REQUIRED | L011, L012 + naprawa | ok |
| Słownik tylko w SELECT, RADIO, CHECKBOX; wtedy `options` puste | L013, L014, walidator IR | ok |
| Pole wyboru ma opcje albo słownik | L025 | ok |
| Nazwa słownika z listy COI | **L026 (nowa)**: Kraje, Województwo, Powiat, Gmina, Miejscowość, Numery kierunkowe + TERYT_DOWODOWY, TERYT_4G_DOWODOWY z referencji | naprawione teraz |
| Słowniki adresowe i Kraje tylko w liście rozwijanej | **L027 (nowa)** | naprawione teraz |
| Opcje: `id`, `name`, `techName` | kompilator | ok |
| Opcje różne w obrębie pola, `techName` opcji niepusty | **kompilator `_options`** (usuwa puste i powtórzone, `opcja_N` gdy slug pusty) + **L029 (nowa)** z naprawą | naprawione teraz; IR nie zabrania powtórzeń, np. opcja „-” dawała pusty `techName` |
| `techName` obowiązkowy i unikalny | L018 + naprawa, wzorzec klucza w IR `^[a-z][a-z0-9_]{0,59}$` | ok |
| Sekcja ma tytuł | `SectionIR.title` wymagany | ok (brak reguły lintera dla pustego tytułu; znana luka, niska waga) |
| Sekcja bez pól | **L030 (nowa)** z naprawą (usunięcie sekcji, przeliczenie `y`) | naprawione teraz; `SectionIR.fields` może być puste |
| INFO_SECTION ma opis | brak reguły | znana luka; nie emitujemy INFO_SECTION |
| CONSENT_SECTION: `consents` z `description` i `required`, `files` | kompilator, `schema.Consent` | ok |
| `selectAllEnabled` w CONSENT_SECTION | nie emitujemy (pole opcjonalne) | ok |

## Dane inicjalne

| Reguła | Jak wymuszamy | Stan |
|---|---|---|
| `defaultValue: "<ŹRÓDŁO>.<atrybut>"`, `defaultValueType: "EXTERNAL_SYSTEM"` | L015, wzorzec w IR | ok |
| Atrybut z listy danego źródła | **L028 (nowa)**, pełne listy PESEL (16), PESEL_ADDRESS (18), MLPZ (15); test, że biblioteka sekcji używa tylko tych atrybutów | naprawione teraz (wcześniej np. `PESEL.shoeSize` przechodził) |
| Pole z rejestru PESEL tylko do odczytu | L016 + naprawa | ok |
| Pole z MLPZ tylko do odczytu | nie wymuszamy | znane odstępstwo: obie referencje mają pola MLPZ edytowalne (`readOnly: false`); dokument mówi o danych „z Rejestru” |

## Kontrakt z ARCHITECTURE.md 5.6

Sprawdzone skryptem na 6 wynikach: siatka `x: 0`, `cols: 3`; `rows` sekcji = liczba pól + 1;
`y` narastająco i równe `questionOrder`; opisy jako dokument HTML; wszystkie `id` stron, pól i przejść
to UUID (w referencji 5 trzy przejścia mają krótkie identyfikatory, więc Generator ich nie wymaga);
`searchEnabled` i `multiLevelTree` tylko w SELECT; SELECT z TERYT ma `multiLevelTree: true`.
Brak odchyleń.

## Zmiana wyniku kompilatora

`compiler._options` zmienia wynik tylko dla IR z pustymi lub powtórzonymi opcjami albo opcjami,
z których slug jest pusty. Obecne `outputs/` takich nie mają, więc ich regeneracja nie jest potrzebna.
