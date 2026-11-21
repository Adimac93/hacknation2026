# Macierz formatów: jeden formularz, osiem formatów wejścia

Każdy blankiet z folderów `Docs/3.`–`Docs/9.` (bez wzorcowego JSON-a i bez dokumentu „wizualizacja” w folderze 5) wysłaliśmy do działającej usługi przez `POST /api/v1/forms?details=true`. Skrypt: `devtools/format_matrix.py`, wynik niepoprawiany ręcznie.

- Data: 2026-11-21 22:22 UTC
- Maszyna: Linux x86_64, AMD Ryzen Threadripper 1920X 12-Core Processor, 8 rdzeni CPU
- Usługa: stos `docker compose` (web + api + tika), adres `http://127.0.0.1:8080`
- Tryb: reguły (bez modelu, `LLM_ENABLED=false`)
- Czas: zegar ścienny po stronie klienta, cały request przez nginx (wczytanie, OCR lub Tika, heurystyki, kompilacja, linter)

**Razem:** plików 53, HTTP 200: 53, błędy lintera: 0, najwolniejszy plik: `Wniosek o przyznanie stypendium.jpg` (20.9 s).

## Podsumowanie na formularz

| Formularz | Formaty OK | Pola (min–maks) | Tytuły zgodne | Najwolniejszy format |
|---|---|---|---|---|
| 3 | 8/8 | 19–22 | tak | `jpeg` (3.3 s) |
| 4 | 8/8 | 18–21 | nie (wariantów: 3) | `jpeg` (3.5 s) |
| 5 | 7/7 | 35–39 | tak | `jpeg` (2.5 s) |
| 6 | 8/8 | 50–69 | tak | `jpeg` (6.8 s) |
| 7 | 6/6 | 20–25 | nie (wariantów: 2) | `jpe` (9.1 s) |
| 8 | 8/8 | 49–55 | nie (wariantów: 5) | `jpg` (20.6 s) |
| 9 | 8/8 | 48–75 | tak | `jpg` (20.9 s) |

## Wszystkie pliki

| Formularz | Plik | HTTP | Czas [s] | Tryb | Strony | Pola | Błędy lintera | Uwagi lintera | Tytuł |
|---|---|---|---|---|---|---|---|---|---|
| 3 | `Wniosek o wydanie zaświadczenia.doc` | 200 | 0.0 | rules | 1 | 21 | 0 | 1 | Wniosek o wydanie zaświadczenia |
| 3 | `Wniosek o wydanie zaświadczenia.docx` | 200 | 0.1 | rules | 1 | 22 | 0 | 1 | Wniosek o wydanie zaświadczenia |
| 3 | `Wniosek o wydanie zaświadczenia.jpeg` | 200 | 3.3 | rules | 1 | 19 | 0 | 1 | Wniosek o wydanie zaświadczenia |
| 3 | `Wniosek o wydanie zaświadczenia.jpg` | 200 | 3.3 | rules | 1 | 19 | 0 | 1 | Wniosek o wydanie zaświadczenia |
| 3 | `Wniosek o wydanie zaświadczenia.ods` | 200 | 0.0 | rules | 1 | 21 | 0 | 1 | Wniosek o wydanie zaświadczenia |
| 3 | `Wniosek o wydanie zaświadczenia.pdf` | 200 | 0.1 | rules | 1 | 22 | 0 | 1 | Wniosek o wydanie zaświadczenia |
| 3 | `Wniosek o wydanie zaświadczenia.png` | 200 | 3.2 | rules | 1 | 19 | 0 | 1 | Wniosek o wydanie zaświadczenia |
| 3 | `Wniosek o wydanie zaświadczenia.xlsx` | 200 | 0.1 | rules | 1 | 21 | 0 | 1 | Wniosek o wydanie zaświadczenia |
| 4 | `Wniosek o wynajęcie świetlicy.doc` | 200 | 0.1 | rules | 1 | 20 | 0 | 3 | Wniosek o wynajęcie/użyczenie świetlicy wiejskiej |
| 4 | `Wniosek o wynajęcie świetlicy.docx` | 200 | 0.0 | rules | 1 | 20 | 0 | 3 | Wniosek o wynajęcie/użyczenie świetlicy wiejskiej |
| 4 | `Wniosek o wynajęcie świetlicy.jpeg` | 200 | 3.5 | rules | 1 | 18 | 0 | 1 | Wniosek |
| 4 | `Wniosek o wynajęcie świetlicy.jpg` | 200 | 3.5 | rules | 1 | 18 | 0 | 1 | Wniosek o wynajęcie/użyczenieświetlicy wiejskiej |
| 4 | `Wniosek o wynajęcie świetlicy.ods` | 200 | 0.1 | rules | 1 | 18 | 0 | 1 | Wniosek o wynajęcie/użyczenie świetlicy wiejskiej |
| 4 | `Wniosek o wynajęcie świetlicy.pdf` | 200 | 0.1 | rules | 1 | 21 | 0 | 3 | Wniosek o wynajęcie/użyczenie świetlicy wiejskiej |
| 4 | `Wniosek o wynajęcie świetlicy.png` | 200 | 3.5 | rules | 1 | 18 | 0 | 1 | Wniosek o wynajęcie/użyczenie świetlicy wiejskiej |
| 4 | `Wniosek o wynajęcie świetlicy.xlsx` | 200 | 0.0 | rules | 1 | 18 | 0 | 1 | Wniosek o wynajęcie/użyczenie świetlicy wiejskiej |
| 5 | `Wniosek o stwierdzenie nadpłaty podatku.DOC` | 200 | 0.1 | rules | 1 | 39 | 0 | 6 | Wniosek o stwierdzenie nadpłaty podatku |
| 5 | `Wniosek o stwierdzenie nadpłaty podatku.docx` | 200 | 0.1 | rules | 1 | 39 | 0 | 6 | Wniosek o stwierdzenie nadpłaty podatku |
| 5 | `Wniosek o stwierdzenie nadpłaty podatku.jpeg` | 200 | 2.5 | rules | 1 | 35 | 0 | 5 | Wniosek o stwierdzenie nadpłaty podatku |
| 5 | `Wniosek o stwierdzenie nadpłaty podatku.JPG` | 200 | 2.4 | rules | 1 | 36 | 0 | 5 | Wniosek o stwierdzenie nadpłaty podatku |
| 5 | `Wniosek o stwierdzenie nadpłaty podatku.ODS` | 200 | 0.1 | rules | 1 | 35 | 0 | 5 | Wniosek o stwierdzenie nadpłaty podatku |
| 5 | `Wniosek o stwierdzenie nadpłaty podatku.PDF` | 200 | 0.2 | rules | 1 | 39 | 0 | 6 | Wniosek o stwierdzenie nadpłaty podatku |
| 5 | `Wniosek o stwierdzenie nadpłaty podatku.PNG` | 200 | 2.5 | rules | 1 | 36 | 0 | 5 | Wniosek o stwierdzenie nadpłaty podatku |
| 6 | `Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.doc` | 200 | 0.1 | rules | 1 | 58 | 0 | 9 | Wniosek o wydanie zezwolenia na zajęcie pasa drogowego w celu prowadzenia robót |
| 6 | `Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.docx` | 200 | 0.1 | rules | 1 | 58 | 0 | 9 | Wniosek o wydanie zezwolenia na zajęcie pasa drogowego w celu prowadzenia robót |
| 6 | `Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.jpeg` | 200 | 6.8 | rules | 2 | 54 | 0 | 8 | Wniosek o wydanie zezwolenia na zajęcie pasa drogowego w celu prowadzenia robót |
| 6 | `Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.jpg` | 200 | 6.7 | rules | 2 | 59 | 0 | 8 | Wniosek o wydanie zezwolenia na zajęcie pasa drogowego w celu prowadzenia robót |
| 6 | `Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.ods` | 200 | 0.1 | rules | 1 | 50 | 0 | 6 | Wniosek o wydanie zezwolenia na zajęcie pasa drogowego w celu prowadzenia robót |
| 6 | `Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.pdf` | 200 | 0.4 | rules | 2 | 69 | 0 | 8 | Wniosek o wydanie zezwolenia na zajęcie pasa drogowego w celu prowadzenia robót |
| 6 | `Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.png` | 200 | 6.6 | rules | 2 | 54 | 0 | 8 | Wniosek o wydanie zezwolenia na zajęcie pasa drogowego w celu prowadzenia robót |
| 6 | `Wniosek o wydanie zezwolenia na zajęcie pasa drogowego.xlsx` | 200 | 0.1 | rules | 1 | 50 | 0 | 6 | Wniosek o wydanie zezwolenia na zajęcie pasa drogowego w celu prowadzenia robót |
| 7 | `Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanychza agresywne.DOC` | 200 | 0.1 | rules | 1 | 25 | 0 | 3 | Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanych za agresywne |
| 7 | `Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanychza agresywne.JPE` | 200 | 9.1 | rules | 2 | 20 | 0 | 1 | Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanych za agresywne |
| 7 | `Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanychza agresywne.JPG` | 200 | 9.0 | rules | 2 | 20 | 0 | 1 | Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanych za agresywne |
| 7 | `Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanychza agresywne.ODS` | 200 | 0.1 | rules | 1 | 21 | 0 | 1 | Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanych za agresywne |
| 7 | `Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanychza agresywne.PDF` | 200 | 1.2 | rules | 2 | 25 | 0 | 2 | Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawan ych za agresywne |
| 7 | `Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanychza agresywne.PNG` | 200 | 8.8 | rules | 2 | 20 | 0 | 1 | Wniosek o wydanie zezwolenia na hodowanie lub utrzymywanie psów ras uznawanych za agresywne |
| 8 | `Deklaracja o wysokości opłaty.doc` | 200 | 0.1 | rules | 1 | 51 | 0 | 8 | Deklaracja o wysokości miesięcznej opłaty |
| 8 | `Deklaracja o wysokości opłaty.docx` | 200 | 0.3 | rules | 1 | 51 | 0 | 9 | Deklaracja o wysokości miesięcznej opłaty za gospodarowanie odpadami komunalnymi |
| 8 | `Deklaracja o wysokości opłaty.jpeg` | 200 | 20.4 | rules | 6 | 50 | 0 | 9 | Deklaracja o wysokości miesiecznej oplaty za gospodarowanie odpadami komunalnymi |
| 8 | `Deklaracja o wysokości opłaty.jpg` | 200 | 20.6 | rules | 6 | 50 | 0 | 9 | Deklaracja o wysokości miesiecznej oplaty zagospodarowanieodpadamikomunalnymi |
| 8 | `Deklaracja o wysokości opłaty.ods` | 200 | 0.2 | rules | 1 | 49 | 0 | 6 | Deklaracja o wysokości miesięcznej opłaty za gospodarowanie odpadami komunalnymi |
| 8 | `Deklaracja o wysokości opłaty.pdf` | 200 | 2.0 | rules | 6 | 55 | 0 | 14 | Deklaracja o wysokości miesięcznej opłaty za gospodarowanie odpadami komunalnymi |
| 8 | `Deklaracja o wysokości opłaty.png` | 200 | 20.5 | rules | 6 | 50 | 0 | 9 | Deklaracja o wysokości miesięcznej oplaty za gospodarowanie odpadami komunalnymi |
| 8 | `Deklaracja o wysokości opłaty.xlsx` | 200 | 0.2 | rules | 1 | 49 | 0 | 6 | Deklaracja o wysokości miesięcznej opłaty za gospodarowanie odpadami komunalnymi |
| 9 | `Wniosek o przyznanie stypendium.doc` | 200 | 0.1 | rules | 1 | 72 | 0 | 12 | Wniosek o przyznanie stypendium sportowego Rady Miasta Zgierza |
| 9 | `Wniosek o przyznanie stypendium.docx` | 200 | 0.1 | rules | 1 | 75 | 0 | 12 | Wniosek o przyznanie stypendium sportowego Rady Miasta Zgierza |
| 9 | `Wniosek o przyznanie stypendium.jpeg` | 200 | 19.7 | rules | 16 | 63 | 0 | 10 | Wniosek o przyznanie stypendium sportowego Rady Miasta Zgierza |
| 9 | `Wniosek o przyznanie stypendium.jpg` | 200 | 20.9 | rules | 16 | 62 | 0 | 11 | Wniosek o przyznanie stypendium sportowego Rady Miasta Zgierza |
| 9 | `Wniosek o przyznanie stypendium.ods` | 200 | 0.1 | rules | 1 | 48 | 0 | 6 | Wniosek o przyznanie stypendium sportowego Rady Miasta Zgierza |
| 9 | `Wniosek o przyznanie stypendium.pdf` | 200 | 1.2 | rules | 16 | 72 | 0 | 12 | Wniosek o przyznanie stypendium sportowego Rady Miasta Zgierza |
| 9 | `Wniosek o przyznanie stypendium.png` | 200 | 20.2 | rules | 16 | 63 | 0 | 9 | Wniosek o przyznanie stypendium sportowego Rady Miasta Zgierza |
| 9 | `Wniosek o przyznanie stypendium.xlsx` | 200 | 0.1 | rules | 1 | 48 | 0 | 6 | Wniosek o przyznanie stypendium sportowego Rady Miasta Zgierza |
