# 10 — Pokrycie formularzy referencyjnych

Stan na 2026-11-21, około 23:15. Pomiar: `devtools/coverage.py` (uruchamiany z `api/`), cały potok `pipeline.process` na blankietach formularzy 1 i 5, porównany z JSON-ami organizatora z tych samych folderów `Docs/`.

```sh
cd api
uv run python ../devtools/coverage.py            # tryb reguł: PDF, DOCX, PNG
uv run python ../devtools/coverage.py --llm      # tryb modelu: PDF, 2 przebiegi na formularz i wariant
```

DOCX wymaga Apache Tika pod `--tika-url` (domyślnie `http://127.0.0.1:9998`; w pomiarze lokalny `tika-server-standard-3.3.2.jar`, ta sama wersja co w `tika/Dockerfile`). PNG przechodzi przez lokalny OCR (RapidOCR, zapasowo Tesseract).

## Wynik w skrócie

Ścisłe dopasowanie po etykietach, łącznie 11 pól merytorycznych w obu referencjach (4 w formularzu 1, 7 w formularzu 5):

| Tryb | Wejście | Recall (łącznie) | Uwagi |
|---|---|---|---|
| Model, prompt produkcyjny (`full`) | PDF | **73–82%** (8–9/11) | formularz 1: 4/4 w obu przebiegach; formularz 5: 4/7 i 5/7 |
| Model, bez własnego przykładu (`loo`) | PDF | **64%** (7/11) | formularz 1: 4/4; formularz 5: 3/7 w obu przebiegach |
| Reguły | PDF, DOCX, PNG | **9%** (1/11) | tylko „Numer ewidencyjny działki” |

Po ręcznym przejrzeniu par (sekcja „Co obniża wynik”) tryb modelu `loo` pokrywa znaczeniowo 10 z 11 pól, a tryb reguł 5 z 11. To ocena ręczna, nie wynik skryptu.

We wszystkich 14 przebiegach: strony 4 jak w referencji, wszystkie trzy sekcje predefiniowane obecne (wnioskodawca, adresat, zgody), rodzaj adresata (urząd/organ) zgodny z referencją. Wszystkie przebiegi z `--llm` zakończyły się w trybie `llm` (bez powrotu do reguł).

## Metoda

Pola merytoryczne to pola na stronach między standardową stroną „Dane” a stroną kontaktu (`pages[1:-2]` po `decompile`), bez `TEXT_BLOCK` i `INFO_SECTION`, liczone tak samo w referencji i w naszym wyniku. Etykiety normalizujemy do sluga (małe litery, ASCII, same słowa, `compiler.slugify`) i porównujemy współczynnikiem `difflib.SequenceMatcher.ratio`. Pary łączymy zachłannie jeden do jednego, od najbardziej podobnych, aż do progu **0,6** (`MATCH_THRESHOLD`, ten sam co w `devtools/compare_models.py`). Recall = trafione / pola referencji, precision = trafione / nasze pola, „ten sam typ” = trafione pary z identycznym typem pola. Sekcje predefiniowane sprawdzamy po kluczach sekcji z biblioteki (`podmiot_wniosku` lub `twoje_dane`; sekcja adresata urzędu lub organu; dowolne pole `CONSENT_SECTION`). Kolumna „Podmioty” to liczba opcji pola „Wybierz, w czyim imieniu wnioskujesz” (osoba, podmiot, pełnomocnik); 0 oznacza, że pole zniknęło, bo formularz dopuszcza tylko osobę fizyczną.

Wariant `full` to prompt produkcyjny. Jego przykłady few-shot pochodzą właśnie z formularzy 1 i 5 (decyzja D12), więc model widzi skrócony blankiet i odpowiedź dla ocenianego formularza. To górna granica. Wariant `loo` usuwa z promptu przykład ocenianego formularza (zostaje ten drugi) i lepiej przybliża zachowanie na nowym blankiecie.

## Tryb reguł (`Settings(_env_file=None)`, bez modelu)

| Formularz | Wejście | Pola ref. | Nasze pola | Trafione | Recall | Precision | Ten sam typ | Sekcje predef. | Podmioty (ref.) | Strony (ref.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PDF | 4 | 2 | 1 | 25% | 50% | 0/1 | 3/3 | 0 (3) | 4 (4) |
| 1 | DOCX | 4 | 2 | 1 | 25% | 50% | 0/1 | 3/3 | 0 (3) | 4 (4) |
| 1 | PNG | 4 | 2 | 1 | 25% | 50% | 1/1 | 3/3 | 0 (3) | 4 (4) |
| 5 | PDF | 7 | 5 | 0 | 0% | 0% | — | 3/3 | 2 (3) | 4 (4) |
| 5 | DOCX | 7 | 5 | 0 | 0% | 0% | — | 3/3 | 2 (3) | 4 (4) |
| 5 | PNG | 7 | 2 | 0 | 0% | 0% | — | 3/3 | 2 (3) | 4 (4) |

Tryb reguł jest powtarzalny: PDF i DOCX dają identyczne pola, PNG gubi część linii w OCR (formularz 5: 2 pola zamiast 5).

## Tryb modelu (`flexai/Qwen3.5-9B@eu` przez EdenAI, PDF)

| Formularz | Wariant | Przebieg | Nasze pola | Trafione | Recall | Precision | Ten sam typ | Sekcje predef. | Podmioty (ref.) | Strony (ref.) |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | full | 1 | 4 | 4 | 100% | 100% | 4/4 | 3/3 | 2 (3) | 4 (4) |
| 1 | full | 2 | 4 | 4 | 100% | 100% | 4/4 | 3/3 | 2 (3) | 4 (4) |
| 5 | full | 1 | 7 | 4 | 57% | 57% | 4/4 | 3/3 | 3 (3) | 4 (4) |
| 5 | full | 2 | 7 | 5 | 71% | 71% | 5/5 | 3/3 | 3 (3) | 4 (4) |
| 1 | loo | 1 | 4 | 4 | 100% | 100% | 4/4 | 3/3 | 2 (3) | 4 (4) |
| 1 | loo | 2 | 4 | 4 | 100% | 100% | 4/4 | 3/3 | 2 (3) | 4 (4) |
| 5 | loo | 1 | 6 | 3 | 43% | 50% | 3/3 | 3/3 | 3 (3) | 4 (4) |
| 5 | loo | 2 | 6 | 3 | 43% | 50% | 3/3 | 3/3 | 3 (3) | 4 (4) |

Endpoint nie jest deterministyczny mimo `temperature` 0 i stałego ziarna: przebiegi `full` dla formularza 5 różnią się etykietą pola wyboru („Sposób rozliczenia nadpłaty” i „Wybierz sposób rozliczenia nadpłaty”), a przebiegi `loo` dają te same liczby przy innych etykietach. Koszt pomiaru: 8 wywołań modelu, około 0,01 USD.

## Co obniża wynik

1. **Referencja to przeprojektowanie, nie transkrypcja.** Organizator nadał polom nowe nazwy („Wybierz, co mamy zrobić z nadpłatą”, „Plik deklaracji podatkowej”), których nie ma na blankiecie. Ścisłe porównanie etykiet karze każdą inną, równie poprawną nazwę. Przykład z formularza 5, wariant `loo`: „Kwota nadpłaty” (NUMBER) zamiast „Kwota” (NUMBER), „Sposób zwrócenia nadpłaty” (RADIO) zamiast „Wybierz, co mamy zrobić z nadpłatą” (RADIO), „Korekta deklaracji” (FILE_UPLOADER) zamiast „Plik deklaracji podatkowej” (FILE_UPLOADER). Typy się zgadzają, etykiety nie przechodzą progu. Ręcznie: 6 z 7 pól pokrytych, brakuje tylko „Nazwa podatku” (podatek, na który zaliczyć nadpłatę).
2. **Dopasowanie zachłanne po etykiecie myli pola o podobnych nazwach.** „Rodzaj podatku” (nasze pole na podatek z nadpłatą) łączy się z referencyjnym „Nazwa podatku” zamiast z „Podatek, którego dotyczy nadpłata”. Liczba trafień się nie zmienia, ale para jest błędna.
3. **Tryb reguł przepisuje tekst blankietu.** Etykiety to fragmenty zdań („W kwocie”, „(Dz. U. z 2025 r. poz. 111 ze zm.) wnoszę o stwierdzenie nadpłaty z tytułu”), dwa pola w jednym wierszu łączą się w jedno („W miejscowości przy ulicy”, „Nr ewidencyjny działki w obrębie”), a przypisy „2)” i „3)” stają się polami. Znaczeniowo tryb reguł pokrywa 2 z 4 pól formularza 1 i 3 z 7 formularza 5, ale żadnej etykiety nie nazywa po nowemu. Nie rozpoznaje też wyboru „zaliczyć / zwrócić” jako pola RADIO.
4. **Warianty wnioskodawcy.** Referencje dopuszczają wszystkie trzy podmioty (osoba, firma, pełnomocnik) nawet wtedy, gdy blankiet o nich nie wspomina. Nasz potok ustawia je na podstawie blankietu: dla formularza 1 tryb reguł zostawia tylko osobę fizyczną, a model dwa warianty.
5. **Mała próba.** 11 pól w dwóch formularzach. Jedno pole zmienia wynik o 9 punktów procentowych. Liczby pokazują kierunek, nie precyzyjną skuteczność.

## Wnioski

- Szkielet formularza (strony, sekcje predefiniowane, adresat, zgody) zgadza się z referencją w każdym przebiegu, także bez modelu i z rastra.
- Pola merytoryczne nazywa po nowemu dopiero model: z 1/11 (reguły) do 7/11 przy ścisłym porównaniu bez podglądu odpowiedzi i do około 10/11 po ręcznej ocenie znaczeniowej.
- Do slajdów uczciwa liczba to **64% ścisłego recall i około 90% pokrycia znaczeniowego w trybie modelu bez własnego przykładu**, z zastrzeżeniem małej próby.
