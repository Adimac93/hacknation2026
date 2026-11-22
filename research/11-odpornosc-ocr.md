# 11 — Odporność OCR na skany i zdjęcia z telefonu

Stan na 2026-11-22. Zadanie W8: na finale jury wgrywa nowe pliki, najpewniej skany albo zdjęcia telefonem (lekko obrócone, przekrzywione, rozmyte, o słabym kontraście, mocno skompresowane, w innej rozdzielczości, pojedyncza strona zamiast wysokiego paska stron). Dotąd ścieżkę OCR (`api/src/formcompiler/ingest/raster.py`) sprawdzaliśmy tylko na czystych rastrach organizatora.

## Zestaw testowy

Pierwsza strona formularzy 3, 6 i 8 (górne 2339 px pliku PNG z `Docs/`), przerobiona skryptem w katalogu roboczym (obrazów nie commitujemy). Warianty:

| Wariant | Co symuluje |
|---|---|
| `rot±1`, `rot±3`, `rot±7` | skan lub zdjęcie obrócone o tyle stopni (biały margines) |
| `rot90`, `rot180`, `rot270` | strona wgrana bokiem albo do góry nogami |
| `persp` | zdjęcie pod kątem: perspektywa 6%, kartka na ciemnym blacie, JPEG 85 |
| `blur1.5`, `blur2.5` | rozmycie Gaussa (sigma w pikselach przy 200 DPI) |
| `jpeg40` | kompresja JPEG, jakość 40 |
| `w1000`, `w800`, `w600` | zmniejszenie do tej szerokości |
| `w3300` | powiększenie do 3300 px (zdjęcie 12 Mpx), JPEG 85 |
| `light` | nierówne oświetlenie (spadek jasności o 45% w poprzek) i kontrast ściśnięty do ~90–205 |
| `phone` | wszystko naraz: perspektywa 4%, obrót 2°, ciemny blat, oświetlenie, rozmycie 1,0, szum, 1500 px |
| `phonebig` | `phone` powiększony do 3000 px |

`clean` to sama pierwsza strona, czyli jednocześnie wariant „pojedyncza strona zamiast paska”.

Pomiar bez HTTP: `ingest.read(..., FileKind.PNG/JPEG, settings)`, potem `pipeline.process` w trybie reguł (`refine=None`), Tesseract z `pol` (tessdata_fast, jak pakiet Debiana w obrazie Docker) jako zapas. Dla każdego wariantu:

- **linie**: odsetek linii czystej strony odnalezionych w wyniku (podobieństwo `difflib` ≥ 0,8), średnia z trzech formularzy,
- **ufność**: średnia ważona ufność RapidOCR dla przyjętego odczytu, minimum z trzech formularzy,
- **pola**: liczba pól IR w trybie reguł dla formularzy 3, 6 i 8 (czysta strona: 19, 36, 34),
- **tytuł**: w ilu formularzach tytuł z heurystyk zgadza się z tytułem czystej strony (podobieństwo ≥ 0,9, bo OCR czasem gubi „ę”),
- **czas**: najdłuższy czas `read` + `process` z trzech formularzy, MacBook M1 Pro, jedna strona.

## Wyniki

| Wariant | linie przed | ufność min przed | pola 3/6/8 przed | tytuł przed | czas max przed | linie po | ufność min po | pola 3/6/8 po | tytuł po | czas max po |
|---|---|---|---|---|---|---|---|---|---|---|
| clean | 1.00 | 0.98 | 19/36/34 | 3/3 | 2.9 | 1.00 | 0.98 | 19/36/34 | 3/3 | 3.0 |
| rot+1 | 0.95 | 0.98 | 19/37/35 | 3/3 | 2.8 | 0.99 | 0.98 | 19/37/34 | 3/3 | 3.0 |
| rot-1 | 0.95 | 0.98 | 19/35/35 | 3/3 | 3.1 | 0.99 | 0.98 | 19/38/34 | 3/3 | 3.3 |
| rot+3 | 0.76 | 0.98 | 18/38/35 | 3/3 | 2.8 | 0.98 | 0.98 | 19/40/34 | 3/3 | 3.6 |
| rot-3 | 0.72 | 0.98 | 19/36/35 | 3/3 | 3.2 | 0.99 | 0.98 | 19/40/34 | 3/3 | 3.5 |
| rot+7 | 0.65 | 0.98 | 37/35 | 1/3 | 2.9 (1× wyjątek, 500) | 0.99 | 0.98 | 19/38/34 | 3/3 | 3.3 |
| rot-7 | 0.62 | 0.98 | 19/41/35 | 0/3 | 3.4 | 0.99 | 0.97 | 19/40/34 | 3/3 | 3.1 |
| rot90 | 0.05 | 0.97 | 18/35/35 | 0/3 | 2.6 | 0.98 | 0.96 | 19/45/34 | 3/3 | 2.8 |
| rot180 | 0.00 | 0.61 | 17/17/17 | 0/3 | 4.3 | 1.00 | 0.98 | 19/36/34 | 3/3 | 2.9 |
| rot270 | 0.00 | 0.61 | 17/17/17 | 0/3 | 3.6 | 0.98 | 0.96 | 19/45/34 | 3/3 | 3.2 |
| persp | 0.90 | 0.98 | 19/38/35 | 3/3 | 2.6 | 0.98 | 0.98 | 19/38/34 | 3/3 | 3.1 |
| blur1.5 | 0.99 | 0.98 | 20/39/34 | 3/3 | 2.8 | 0.99 | 0.98 | 20/39/34 | 3/3 | 3.0 |
| blur2.5 | 0.87 | 0.97 | 19/35/34 | 3/3 | 2.5 | 0.87 | 0.97 | 19/35/34 | 3/3 | 2.7 |
| jpeg40 | 0.98 | 0.97 | 20/47/34 | 3/3 | 2.8 | 0.98 | 0.97 | 20/47/34 | 3/3 | 3.0 |
| w1000 | 0.99 | 0.97 | 19/42/34 | 3/3 | 2.5 | 0.99 | 0.97 | 19/42/34 | 3/3 | 2.6 |
| w800 | 0.99 | 0.97 | 19/36/35 | 3/3 | 2.0 | 0.99 | 0.97 | 19/36/35 | 3/3 | 2.1 |
| w600 | 0.98 | 0.96 | 18/43/35 | 3/3 | 2.9 | 0.98 | 0.96 | 18/43/35 | 3/3 | 2.1 |
| w3300 | 0.99 | 0.98 | 19/36/34 | 3/3 | 4.0 | 0.99 | 0.98 | 19/41/34 | 3/3 | 3.1 |
| light | 0.99 | 0.98 | 18/35/34 | 3/3 | 2.8 | 0.99 | 0.98 | 18/35/34 | 3/3 | 3.1 |
| phone | 0.80 | 0.98 | 19/35/35 | 3/3 | 2.7 | 0.96 | 0.98 | 19/35/35 | 3/3 | 3.0 |
| phonebig | 0.81 | 0.98 | 18/35/35 | 3/3 | 2.7 | 0.92 | 0.98 | 18/35/35 | 3/3 | 2.6 |

Linie, ufność i czas: średnia / minimum / maksimum z formularzy 3, 6, 8. Ufność „przed” dla `rot180` i `rot270` to ufność RapidOCR; stronę i tak czytał wtedy Tesseract (próg 0,8), też do góry nogami. Kolumny „po” pochodzą z pełnego przebiegu wcześniejszej wersji tej zmiany (krok zgrubny 1,0° zamiast 0,5°); ostateczny kod (commit c2fc680) dał identyczne linie, pola i tytuły na pierwszych 56 z 63 plików, zanim pomiar przerwało zamrożenie prac.

Przed zmianą:

- obrót o 3° i więcej rozbijał linie (pola tekstu przestają się nakładać w pionie), formularz 8 tracił do 58% linii, tytuł wypadał,
- strona obrócona o 90°, 180° albo 270° dawała śmieci: tytuł „Wniosek” (wartość domyślna), 17 pól z niczego; przy 180° i 270° RapidOCR miał ufność ~0,62–0,66 i stronę czytał Tesseract, też do góry nogami,
- `f3_rot+7` kończył się wyjątkiem: heurystyki zrobiły z pomieszanych linii tytuł dłuższy niż 255 znaków i walidacja `FormIR` rzuciła `ValidationError` (w API: błąd 500),
- zdjęcie pod kątem (`persp`, `phone`) gubiło do 43% linii formularza 8,
- duże zdjęcia (3300 px) czytały się do 4,0 s.

Rozmycie, JPEG 40, niska rozdzielczość (do 600 px) i słabe oświetlenie już wcześniej nie szkodziły: detektor PP-OCRv6 sam sobie z nimi radzi. CLAHE ani wyostrzanie nie są potrzebne, więc ich nie dodaliśmy.

## Co zmieniliśmy (`raster.py`)

Strona, która jest całym obrazem (pojedynczy raster albo strona zeskanowanego PDF), przed OCR przechodzi przez `upright`. Strony wycięte z wysokiego paska organizatora zostają bez zmian (ich geometria jest czysta, a przesuwanie współrzędnych psułoby obsługę zakładki między stronami).

1. **Skala.** Obraz szerszy niż 2000 px zmniejszamy do 1654 px (A4 w 200 DPI, jak rastry organizatora). OCR nie zyskuje nic powyżej tej rozdzielczości, a traci czas.
2. **Kartka na blacie.** Na kopii ~1000 px: Otsu, domknięcie, największy kontur, otoczka wypukła, przybliżenie czworokątem. Czworokąt przyjmujemy tylko, gdy zajmuje 30–97% zdjęcia, krawędź kartki jest ostrym skokiem jasności (pas 5 px po obu stronach różni się o ≥ 40 poziomów szarości) i na „blacie” z dala od krawędzi nie ma tekstu. Wtedy prostujemy perspektywę (`warpPerspective`). Skan bez tła i nierówno oświetlona kartka nie przechodzą tych warunków (test jednostkowy).
3. **Orientacja 90°.** Z atramentu zostawiamy tylko plamy wielkości liter (bez linii tabel i krawędzi). Profil wierszy i profil kolumn mierzymy energią skoków (suma kwadratów różnic sąsiednich wartości, metoda Postla), bo w przeciwieństwie do wariancji nie zależy od tego, gdzie na stronie leży blok tekstu. Na zestawie pionowy tekst daje profil kolumn 12–20 razy ostrzejszy od profilu wierszy, a poziomy profil wierszy 3,8–36 razy ostrzejszy od profilu kolumn (2,3 na syntetycznej stronie z testów); próg 2. Stronę obracamy wtedy o 90° w prawo.
4. **Pochylenie.** Ten sam profil wierszy dla kątów −15°…15° co 0,5°, potem dokładniej co 0,1°. Obracamy, gdy |kąt| ≥ 0,5° (mniejsze pochylenie OCR czyta dobrze, a interpolacja zjada drobne znaki). Estymator trafia w zadany kąt z dokładnością 0,1–0,3° na wszystkich wariantach; na prawdziwym skanie formularza 5 (JPG) znalazł pochylenie −0,8°, które rzeczywiście tam jest.
5. **Do góry nogami.** Polski tekst ma więcej atramentu nad pasem małych liter (wydłużenia górne, wielkie litery, kreski i kropki) niż pod nim (ogonki, wydłużenia dolne). Gdy pod pasem jest go wyraźnie więcej (stosunek < 0,6), obracamy o 180°. To rozstrzyga też kierunek obrotu z kroku 3. Na zestawie: strony odwrócone 0,09–0,55, proste 0,78–10,6.
6. **Siatka bezpieczeństwa.** Jeśli mimo to średnia ufność RapidOCR jest poniżej progu `OCR_MIN_CONFIDENCE` (0,8), czytamy stronę jeszcze raz obróconą o 180° i bierzemy lepszy odczyt; dopiero potem ewentualnie Tesseract. Strona prosta nie płaci za to nic.

`use_cls` zostaje `false` (CLAUDE.md, research/01): orientację rozstrzygamy dla całej strony, a nie dla każdej linii osobno.

Koszt kroków 1–5: ~60–75 ms na stronę (formularz 8). Czyste rastry organizatora (wszystkie PNG, JPG i JPEG z `Docs/`) dają ten sam tekst co przed zmianą, z wyjątkiem dwóch plików formularza 5 (JPG, JPEG), które naprawdę są pochylone o 0,6–0,8° i teraz są prostowane (zgodność tekstu 0,987–0,998, różnice w wykropkowaniach).

## Testy

`api/tests/test_raster.py`, obrazy generowane w teście (`cv2.putText`), bez plików binarnych:

- pochylenie ±1°, ±3°, ±7° jest usuwane do 0,3°,
- strona obrócona o 90°, 180°, 270° wraca do pionu,
- czysta strona, pusty i malutki obraz przechodzą bez zmian,
- zdjęcie kartki na ciemnym blacie pod kątem jest wycinane i prostowane; skan i nierówno oświetlona kartka nie są przycinane,
- szerokie zdjęcie jest skalowane do 1654 px,
- strony z paska nie są obracane,
- niska ufność uruchamia ponowny odczyt po obrocie o 180° przed Tesseractem,
- z wagami: strona pochylona o 4°, odwrócona i sfotografowana daje co najmniej 24 z 26 linii.

## Czego nie robimy i co zostaje

- **Czas.** Gęsta strona (formularz 8) czyta się 2,6–3,6 s, czyli tyle co przed zmianą (czysta strona ~2,9–3,0 s). Obrót powiększa płótno, stąd do ~3,6 s przy 3–7°. Pomiar na laptopie obciążonym innymi procesami; rozrzut ±0,3 s.
- **Wykropkowania.** Rozmycie 2,5 i zdjęcie gubią kropki wykropkowań („długość ……”), stąd niższy wskaźnik linii dla `f6_blur2.5` (0,65) i `f6_phonebig` (0,81). Tekst etykiet jest cały (podobieństwo znakowe 0,72 wynika z kropek), liczba pól i tytuł bez zmian.
- **Zagięta kartka, cień dłoni, zdjęcie z innymi przedmiotami na blacie.** Nie prostujemy krzywizny; czworokąt kartki wymaga ciemniejszego tła. Bez tła działa samo prostowanie pochylenia.
- **Pasek wielu stron, każda pochylona.** Strony z paska czytamy bez normalizacji.
- **Tytuł > 255 znaków.** Wyjątek z `f3_rot+7` po zmianie nie występuje, ale sam błąd w heurystykach (brak przycięcia tytułu przed `FormIR`) zostaje; zgłoszony koordynatorowi, bo leży poza plikami tego zadania.
