# 01 — OCR i parsowanie dokumentów: co wybrać dla polskich formularzy

Stan na 2026-11-21. Pomiary własne: MacBook M4 16 GB, CPython 3.14.3, wszystko w `/tmp/orca-research-ocr/`.

## Rekomendacja

1. **Architektura: hybryda „natywna warstwa tekstowa, OCR tylko dla rastra”.** Na próbkach parser natywny działa w 2–340 ms na plik i zachowuje kratki, kropki i tabele. OCR gubi wszystkie wykropkowania i 62–100% kratek.
2. **OCR główny (propozycja dla decyzji D5): RapidOCR 3.10.0 + ONNX Runtime 1.32.0 z modelami PP-OCRv6 small** (kod i wagi Apache-2.0, ONNX Runtime MIT, bez PyTorch). Zmierzone: CER 1,2–4,2%, 1,0–1,8 s na stronę A4, działa na Python 3.14. Wymaga `Global.use_cls=false` (patrz pomiary). Chodzi o pakiet `rapidocr`, a nie o stary `rapidocr-onnxruntime` 1.4.4, który ma `requires-python <3.13`.
3. **OCR zapasowy: Tesseract 5.5.4 `pol`** (Apache-2.0). Zmierzone: CER 4–12%, 0,5–2,1 s na stronę, 96–175 MB RAM. Jedyny wariant, który instaluje się na Alpine.
4. **Parsery natywne:** `pdfplumber` + `pypdfium2` + `pypdf` (PDF), `python-docx` + własny odczyt `numbering.xml` (DOCX), `python-calamine` + `openpyxl` (XLSX/ODS), **Apache Tika 3.3.2** jako sidecar tylko dla binarnego DOC. Wszystko MIT/BSD/Apache-2.0.
5. **Zapas dla całej warstwy parsowania: Docling 2.151.1** (MIT), jeśli własne parsery zjedzą za dużo czasu. Lokalnie nie zmierzony.
6. **Rozpoznawaj format po sygnaturze pliku, nie po rozszerzeniu.** Próbka `7. .../*.DOC` to w rzeczywistości OOXML (DOCX).
7. **Wysokie obrazy tnij na strony A4 przed OCR.** Bez cięcia Tesseract odrzuca plik, a RapidOCR daje CER 99,9%.
8. **Lokalny VLM do obrazów stron: domyślnie nie.** W Dockerze na Macu nie ma GPU, a zewnętrzne pomiary dają dziesiątki sekund na stronę na CPU.

## Pomiary własne

Prawda odniesienia: `pdftotext` (poppler, tylko do eksperymentu) z pasującego PDF. CER = odległość Levenshteina po znakach, po NFC, zwinięciu białych znaków i usunięciu ciągów kropek oraz glifów kratek. „CER sort.” = to samo po posortowaniu słów, czyli bez wpływu kolejności czytania. Skrypty: `/tmp/orca-research-ocr/scripts/`.

| Wejście | Silnik | CER | CER sort. | Trafione słowa | Diakrytyki | Czas | Szczyt RSS |
|---|---|---|---|---|---|---|---|
| Form. 3, 1 strona | RapidOCR, `use_cls=false` | 4,2% | 2,3% | 100% | 47/47 | 1,3 s | 1,1 GB |
| Form. 3 | Tesseract `--psm 6` (najlepszy) | 8,9% | 8,8% | 97,9% | 47/47 | 0,5 s | 87 MB |
| Form. 3 | Tesseract `--psm 3` (domyślny) | 11,7% | 12,4% | 89,0% | 42/47 | 0,6 s | 96 MB |
| Form. 7, 2 strony | RapidOCR, `use_cls=false` | 1,8% | 1,6% | 98,8% | 168/170 | 4,4 s | 1,7 GB |
| Form. 7 | RapidOCR, ustawienia domyślne | 16,2% | 17,6% | 82,5% | 139/170 | 4,3 s | 1,5 GB |
| Form. 7 | Tesseract `--psm 3` | 4,2% | 5,5% | 98,3% | 170/170 | 2,1 s | 161 MB |
| Form. 9, 16 stron po cięciu | RapidOCR, `use_cls=false` | 1,2% | 1,5% | 99,8% | 438/440 | 15,7 s | 1,5 GB |
| Form. 9, 16 stron po cięciu | Tesseract `--psm 3` | 20,5% | 20,8% | 94,5% | 410/440 | 7,2 s | nie mierzono |
| Form. 9, bez cięcia | RapidOCR | 99,9% | — | 0,2% | 0/440 | 2,7 s | 2,1 GB |
| Form. 9, bez cięcia | Tesseract | błąd `Image too large: (1654, 37424)` | — | — | — | — | — |
| Form. 7 pogorszony syntetycznie | RapidOCR | 24,6% | 2,6% | 95,9% | 154/170 | 3,7 s | 1,2 GB |
| Form. 7 pogorszony syntetycznie | Tesseract `--psm 3` | 4,6% | 8,3% | 94,5% | 169/170 | nie mierzono | nie mierzono |

Uwagi do tabeli:

- **`use_cls`**: domyślny klasyfikator orientacji RapidOCR (stary model PP-OCRv4 mobile) obracał losowe linie o 180° i dawał śmieci typu `Zao a i i i in w`. Po wyłączeniu CER spadł z 16,2% do 1,8%.
- **Pogorszenie syntetyczne**: skala 60% (około 120 DPI), obrót 1,5°, rozmycie, JPEG q35. To nie jest prawdziwy skan ani zdjęcie z telefonu. Wysoki CER RapidOCR wynika z mojego naiwnego składania linii po obrocie (CER sort. 2,6%), więc potrzebny jest deskew. RapidOCR zgubił tu 10 z 36 liter `ą`, Tesseract 0.
- **Kratki**: Tesseract 0/5, 0/5 i 0/50 (zamienia je na `s>` albo pomija). RapidOCR 0/5, 0/5 i 19/50 (zwraca `□` tylko dla części kratek formularza 9).
- **Wykropkowania**: żaden silnik ich nie zwraca wiarygodnie. Tesseract daje szum typu `...............e.eeea aaa aaa`, RapidOCR zostawia pojedynczą kropkę.
- **Naiwna detekcja kratek w OpenCV** (kontury kwadratowe z dziurą): 15 trafień przy 5 prawdziwych na formularzu 3, 79 na jednej stronie formularza 9, 0 na obrazie pogorszonym. Łapie litery `o`, `a`, `D`. Bez maskowania ramkami słów z OCR jest bezużyteczna.

Parsery natywne (pomiar na tych samych plikach):

| Plik | Narzędzie | Czas | Co zachowane |
|---|---|---|---|
| PDF form. 7, 2 strony | pdfplumber 0.11.11 | 0,13 s | 2 tabele (5×8, 8×6), 219 prostokątów, 5 glifów kratek U+2751, nazwy i rozmiary fontów |
| PDF form. 9, 16 stron | pdfplumber / pypdfium2 / pypdf | 0,34 s / 0,013 s / 0,13 s | glify U+25A1 i U+F092 (SymbolMT), wielokropki U+2026 jako pola |
| PDF form. 3 | pdfplumber | 0,02 s | 5 kratek U+F0F0 (Wingdings), 189 znaków `…` |
| DOCX form. 3 | python-docx 1.2.0 | 0,003 s | akapity; **kratki giną**: są punktorami listy w `numbering.xml` (Wingdings U+F0F0), a 4 pola tekstowe `w:txbxContent` nie trafiają do `.paragraphs` |
| DOC form. 3 (binarny) | Tika 3.3.2 `-x` | 0,45 s ze startem JVM | XHTML, trafione słowa 100%, kratki jako `·` w akapicie klasy listy |
| „DOC” form. 7 (faktycznie OOXML) | Tika 3.3.2 | 0,49 s | 2 tabele, glif kratki U+F071 |
| XLSX / ODS | python-calamine 0.9.1 | 1–2 ms | komórki; `openpyxl` dodaje 35 scalonych zakresów |

Żaden z 9 przykładowych PDF nie ma AcroForm (`pdfinfo`: `Form: none`, `pypdf.get_fields()` = `None`). Wszystkie mają warstwę tekstową.

## Pytanie 1: porównanie silników OCR i modeli

| Nazwa, wersja | Licencja: kod / wagi | Python 3.14 | M4 16 GB | Polski, układ, kratki | Werdykt |
|---|---|---|---|---|---|
| RapidOCR 3.10.0 + PP-OCRv6 small | Apache-2.0 / Apache-2.0 | zainstalowany i uruchomiony | 1,0–1,8 s/str., 1,1–1,7 GB | CER 1,2–4,2%; brak układu i tabel; kratki częściowo | **główny** |
| Tesseract 5.5.4 `pol` | Apache-2.0 / Apache-2.0 | binarka; `tesserocr` 2.13.0 ma koła cp314 | 0,5–2,1 s/str., 96–175 MB | CER 4–12%; kolejność zależy od `--psm`; kratki 0; limit 32 767 px | **zapasowy** |
| PaddleOCR 3.7.0 (PP-OCRv6, PP-StructureV3) | Apache-2.0 / Apache-2.0 | **nie**: `paddlepaddle` 3.3.1 na PyPI ma koła tylko cp39–cp313 | nie mierzono | te same wagi rozpoznawania co RapidOCR; PP-StructureV3 daje układ i tabele | odrzucony na 3.14 |
| PaddleOCR-VL-1.6 (0,96 mld) | Apache-2.0 / Apache-2.0 | wymaga `paddlepaddle` albo nieoficjalnych GGUF/MLX | źródło zewn.: około 53 s/str. na CPU M5 Pro; dokumentacja odradza CPU | źródło zewn.: 96,3 w OmniDocBench v1.6 | tylko eksperyment |
| EasyOCR 1.7.2 | Apache-2.0 / nie zweryfikowano | nie testowano; wymaga PyTorch | nie mierzono | brak układu | odrzucony: ostatnie wydanie 2024-09-24 |
| Docling 2.151.1 (layout heron, TableFormer) | MIT / Apache-2.0 i CDLA-Permissive-2.0 | klasyfikator 3.14 na PyPI; lokalnie nie uruchomiony | nie mierzono; wymaga PyTorch | model układu ma klasy Checkbox-Selected/Unselected, Form, Key-Value Region; OCR przez RapidOCR | zapas dla warstwy parsowania |
| Granite-Docling-258M / SmolDocling-256M | Apache-2.0 / CDLA-Permissive-2.0 | przez `transformers` lub MLX | źródło zewn.: 1,7 s/str. MLX na M3 Max, 15,9 s w PyTorch | karta modelu: tylko angielski; polski nieudokumentowany | odrzucony |
| GLM-OCR (1,3 mld) | Apache-2.0 / MIT | nie testowano | nie mierzono | źródło zewn.: 95,2 w OmniDocBench | kandydat na opcjonalny VLM |
| LightOnOCR-2-1B | Apache-2.0 / Apache-2.0 | nie testowano | nie mierzono | nie zweryfikowano | kandydat na opcjonalny VLM |
| olmOCR-2-7B | Apache-2.0 / Apache-2.0 | `olmocr` 0.4.27 bez klasyfikatora 3.14 | 8,3 mld parametrów | — | odrzucony: za duży |
| dots.ocr (3,0 mld) | MIT / MIT | nie testowano | za ciężki na CPU | — | odrzucony |
| DeepSeek-OCR (3,3 mld) / DeepSeek-OCR-2 | MIT / MIT; wersja 2: Apache-2.0 | nie testowano | za ciężki na CPU | — | odrzucony |
| GOT-OCR 2.0 | repo bez wykrytej licencji / wagi Apache-2.0 | nie testowano | 0,56–0,72 mld | brak ruchu od 2025-02 | odrzucony |
| Chandra 0.3.0 / chandra-ocr-2 | Apache-2.0 / **OpenRAIL-M zmodyfikowana** (próg 2 mln USD, zakaz konkurencji) | — | 5,3–8,8 mld | — | odrzucony: licencja wag |
| Surya 0.24.0, Marker 2.2.0 | Apache-2.0 / **OpenRAIL-M zmodyfikowana** (próg 5 mln USD) | brak klasyfikatora 3.14 | — | — | odrzucone: licencja wag |
| MinerU 4.2.3 | **„MinerU Open Source License”** = Apache-2.0 plus próg komercyjny i obowiązek atrybucji; do 3.1.0 AGPL. Wagi: MinerU2.5-2509 AGPL-3.0, MinerU2.5-Pro Apache-2.0 | `<3.15` | — | — | odrzucony: licencja niestandardowa |

Odrzucone z powodu copyleft, potwierdzone w metadanych PyPI: **PyMuPDF 2.1 (AGPL-3.0)**, **Ultralytics 8.4.216 (AGPL-3.0)**, **doclayout-yolo (AGPL-3.0)**, poppler (GPL), antiword (GPL). Surya i Marker nie są już GPL (kod Apache-2.0), ale wagi mają licencję z progiem przychodu. Nowości też odrzucone: HunyuanOCR (licencja `tencent-hunyuan-community`), Nanonets-OCR2 (brak znacznika licencji), Qianfan-OCR (4,7 mld parametrów).

Docker: `onnxruntime`, `opencv-python-headless` i `docling-parse` **nie mają kół musllinux**, więc RapidOCR i Docling wymagają `python:3.14-slim` (Debian), nie Alpine. Koła musllinux mają `pypdfium2`, `python-calamine`, `lxml`, `tesserocr`. Zmierzony rozmiar venv ze stosem głównym: 300 MB (onnxruntime 80, cv2 67, rapidocr z modelami 32, numpy 24). `pol.traineddata` z Homebrew: 4,8 MB.

## Pytanie 2: czy typowe wskazania organizatorów wystarczą

| Wskazany silnik | Czy wystarczy | Czym zastąpić |
|---|---|---|
| Tesseract 5 `pol` | Tekst tak (94–99% słów), ale gubi kratki i wykropkowania, nie daje tabel, a kolejność czytania zależy od `--psm` (CER od 4% do 27% na tych samych stronach). Pada na obrazie 37 424 px. | RapidOCR jako główny, Tesseract jako zapas i druga opinia dla diakrytyków na słabych skanach |
| PaddleOCR | Jakość tak, ale `paddlepaddle` nie ma kół dla Python 3.14, więc nie spełnia wymogu języka. | RapidOCR: te same wagi PP-OCRv6 w ONNX |
| EasyOCR | Nie: projekt bez wydań od 2024-09, wymaga PyTorch. | RapidOCR |

## Pytanie 3: wejścia cyfrowe

| Format | Wybór | Licencja | Python 3.14 | Uwagi |
|---|---|---|---|---|
| PDF | `pdfplumber` 0.11.11 (słowa, bbox, prostokąty, tabele) + `pypdfium2` 5.15.2 (render stron bez tekstu) + `pypdf` 7.1.1 (AcroForm) | MIT; BSD-3/Apache-2.0; BSD-3 | uruchomione | `pdfminer.six` (MIT) jest zależnością pdfplumber |
| DOCX | `python-docx` 1.2.0 + odczyt `numbering.xml` i `w:txbxContent` przez `lxml` | MIT; BSD-3 | uruchomione | `docx2python` 3.7.2 (MIT) to alternatywa, nie testowana |
| XLSX | `python-calamine` 0.9.1 + `openpyxl` 3.1.5 (scalenia) | MIT | uruchomione | |
| ODS | `python-calamine` | MIT | uruchomione | **`odfpy` odradzam**: GitHub podaje GPL-2.0, PyPI trzy licencje naraz; `ezodf` martwy od 2015 |
| DOC binarny | Apache Tika 3.3.2 (`tika-server`, wewnątrz POI HWPF) | Apache-2.0 | n/d (Java) | W Pythonie brak utrzymywanego parsera DOC bez copyleft |

**LibreOffice headless**: licencja MPL-2.0 / LGPLv3+, a pakiet Debiana zawiera też komponenty GPL. Uruchamiany jako osobny proces nie „zaraża” naszego kodu, ale przy regule „tylko non-copyleft” to ryzyko formalne, a obraz rośnie o setki MB. Odradzam; Tika robi to samo na Apache-2.0.

**Konwertery „wszystko w jednym”:**

| Narzędzie | Licencja | Python 3.14 | Werdykt |
|---|---|---|---|
| Docling 2.151.1 | MIT | klasyfikator jest | Najlepsza jednolita reprezentacja (`DoclingDocument` → Markdown, HTML, DocTags, JSON z bbox). Obsługuje PDF, DOCX, XLSX, ODS, obrazy; DOC tylko przez LibreOffice. Ciężki (PyTorch). **Zapas.** |
| Apache Tika 3.3.2 / 4.2.0 | Apache-2.0 | Java | XHTML bez współrzędnych. Tylko dla DOC. W linii 4.x domyślne wyjście to Markdown, a konfiguracja to JSON. |
| MarkItDown 0.1.9 | MIT | klasyfikator jest | Sam Markdown, bez bbox i kratek; obsługa DOC/ODS niepotwierdzona. Odrzucony. |
| Unstructured 0.27.37 | Apache-2.0 | **nie** (`requires-python <3.14`) | Odrzucony. |

**Reprezentacja pośrednia**: własna, cienka lista bloków na stronę: `{typ: heading|paragraph|list_item|table|checkbox|blank|footnote, tekst, bbox, font, bold, źródło: native|ocr, pewność}`. Do modelu językowego serializowana jako Markdown ze znacznikami `[ ]` dla kratek i `____` dla pól. Gotową alternatywą jest `DoclingDocument`.

Uwaga do stosu z `ARCHITECTURE.md` (Tika dla wszystkich plików biurowych): to działa, ale Tika spłaszcza kratki-punktory z `numbering.xml` do znaku `·` w akapicie listy. Glif kratki wstawiony jako znak (U+F071 w formularzu 7) zostaje. Heurystyka pól musi więc traktować krótkie listy punktowane jako kandydatów na opcje wyboru. Wagi Doclinga na CDLA-Permissive-2.0 są permisywne, ale tej licencji nie ma na liście dozwolonych w `CLAUDE.md`.

Jeśli zespół wybierze Javę 21: PDFBox 3.0.8, POI 6.0.0, Tika 4.2.0, Tess4J 5.21.0, ONNX Runtime Java 1.32.0 (wersje z Maven Central, nie testowane).

## Pytanie 4: bardzo wysokie obrazy

Obserwacja: próbki mają szerokość 1654 px (A4 przy 200 DPI), a wysokość to dokładna wielokrotność 2339 px: 4678 = 2 strony, 14 034 = 6, 37 424 = 16. Zgadza się z liczbą stron PDF.

Algorytm (`scripts/split.py`, zmierzony):

1. `page_h = round(W·√2)`. Jeśli `H ≈ n·page_h`, tnij w `k·H/n`.
2. Sprawdź, czy wiersz cięcia jest pusty (profil poziomy: ciemne piksele ≤ W/400).
3. Jeśli nie, przesuń cięcie do najszerszego pustego pasa w zakresie ±15% wysokości strony.
4. Jeśli pustego pasa brak (zdjęcie), tnij z zakładką 100–150 px i usuwaj zduplikowane linie.

Wynik: na formularzach 7, 8 i 9 wszystkie wiersze cięcia miały 0 ciemnych pikseli. Cięcie daje też naturalną granicę stron dla dalszych etapów i pozwala OCR-ować strony równolegle. Obraz 1654×37 424 w skali szarości to około 62 MB w RAM.

## Pytanie 5: hybryda i lokalny VLM

Hybryda: **tak**. Parser natywny jest 10–1000 razy szybszy, bezbłędny znakowo i jako jedyny zachowuje semantykę pól (glif kratki, wielokropek, tabela, pogrubienie). OCR uruchamiaj tylko dla stron bez warstwy tekstowej oraz dla JPG/PNG.

VLM dla obrazów stron: **nie w ścieżce domyślnej**. Powody:

- Docker na macOS nie udostępnia GPU ani MLX, więc model w kontenerze liczy na CPU.
- Zewnętrzny pomiar PaddleOCR-VL 1.6: około 53 s na stronę na CPU. Formularz 16-stronicowy to kilkanaście minut, za długo na pokaz na żywo.
- 16 GB RAM trzeba zostawić dla modelu językowego generującego JSON.
- Polski w małych modelach dokumentowych (Granite-Docling) jest nieudokumentowany.

Sensowny wyjątek: flaga opcjonalna dla rastra o niskiej pewności OCR, ograniczona do 1–2 stron. Kandydaci z czystą licencją: GLM-OCR, LightOnOCR-2-1B, PaddleOCR-VL-1.6. Żaden nie został zmierzony lokalnie.

## Czego nie udało się zweryfikować

- **Docling na Python 3.14**: instalacja nie zakończyła się w czasie eksperymentu. Brak pomiaru jakości, czasu, RAM i wykrywania kratek.
- **Prawdziwe skany i zdjęcia z telefonu**: brak w próbkach. Test pogorszenia był syntetyczny.
- **PP-OCRv6 medium**: testowałem tylko wariant small dołączony do RapidOCR.
- **Wszystkie modele VLM**: szybkość i jakość polskiego na M4 nie zmierzone; liczby pochodzą ze źródeł zewnętrznych.
- **PaddlePaddle 3.4.0**: wzmianki o wydaniu poza PyPI; nie sprawdziłem, czy ma koła cp314.
- **EasyOCR, docx2python, MarkItDown, kreuzberg 4.10.4**: nie instalowane.
- **Rozmiary obrazów Docker**: mierzony tylko venv na macOS, nie zbudowany obraz.
- **Wersje pakietów Alpine** `tesseract-ocr` i `tesseract-ocr-data-pol` dla gałęzi 3.23: strona pakietu nie odczytana (dla 3.20 jest 5.3.4, dla 3.23 pakiet `-dev` ma 5.5.1).
- **Lista 46 języków łacińskich PP-OCRv6**: polski potwierdzony tylko pośrednio (streszczenie aneksu arXiv) i moim pomiarem diakrytyków.
- **Licencja wag EasyOCR** i status licencyjny repozytorium GOT-OCR 2.0.
- **Tessdata**: Homebrew dostarcza plik 4,8 MB; nie sprawdziłem, czy `tessdata_best` poprawia wynik.
- **Wymóg LibreOffice dla DOC w Doclingu** i kolejność wyboru silnika OCR: tylko z dokumentacji i zgłoszeń.

## Źródła

- PyPI (wersje, licencje, koła, `requires-python`): https://pypi.org/project/rapidocr/ , https://pypi.org/project/onnxruntime/ , https://pypi.org/project/paddlepaddle/ , https://pypi.org/project/paddleocr/ , https://pypi.org/project/docling/ , https://pypi.org/project/docling-parse/ , https://pypi.org/project/unstructured/ , https://pypi.org/project/mineru/ , https://pypi.org/project/PyMuPDF/ , https://pypi.org/project/ultralytics/ , https://pypi.org/project/doclayout-yolo/ , https://pypi.org/project/odfpy/ , https://pypi.org/project/pdfplumber/ , https://pypi.org/project/pypdfium2/ , https://pypi.org/project/pypdf/ , https://pypi.org/project/python-calamine/ , https://pypi.org/project/tesserocr/ , https://pypi.org/project/markitdown/ , https://pypi.org/project/easyocr/
- PaddleOCR, wydania i PP-OCRv6: https://github.com/PaddlePaddle/PaddleOCR/releases , https://arxiv.org/abs/2606.13108 , https://huggingface.co/blog/PaddlePaddle/pp-ocrv6
- PaddlePaddle a Python 3.14: https://github.com/PaddlePaddle/Paddle/issues/79527
- PaddleOCR-VL, dokumentacja: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html
- PaddleOCR-VL na CPU (pomiar zewnętrzny): https://codecut.ai/olmocr2-vs-paddleocr-vl/
- RapidOCR, wydania: https://github.com/RapidAI/RapidOCR/releases
- Tesseract: https://github.com/tesseract-ocr/tesseract , https://github.com/tesseract-ocr/tessdata_best
- Docling: https://github.com/docling-project/docling , https://docling-project.github.io/docling/usage/supported_formats/ , https://github.com/docling-project/docling/issues/2927 , https://arxiv.org/html/2509.11720v1 , https://huggingface.co/docling-project/docling-layout-heron
- Granite-Docling: https://huggingface.co/ibm-granite/granite-docling-258M , https://www.ibm.com/granite/docs/models/docling , https://www.neywalabs.ai/blog/docling-mlx-vlm-case-study
- Licencje wag (Hugging Face): https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6 , https://huggingface.co/PaddlePaddle/PP-OCRv6_small_rec , https://huggingface.co/allenai/olmOCR-2-7B-1025 , https://huggingface.co/rednote-hilab/dots.ocr , https://huggingface.co/deepseek-ai/DeepSeek-OCR , https://huggingface.co/deepseek-ai/DeepSeek-OCR-2 , https://huggingface.co/stepfun-ai/GOT-OCR2_0 , https://huggingface.co/lightonai/LightOnOCR-2-1B , https://huggingface.co/datalab-to/chandra-ocr-2 , https://huggingface.co/zai-org/GLM-OCR , https://huggingface.co/opendatalab/MinerU2.5-2509-1.2B , https://huggingface.co/opendatalab/MinerU2.5-Pro-2604-1.2B , https://huggingface.co/tencent/HunyuanOCR , https://huggingface.co/ds4sd/SmolDocling-256M-preview
- Surya, Marker, Chandra: https://github.com/datalab-to/surya , https://github.com/datalab-to/marker , https://github.com/datalab-to/chandra , https://www.datalab.to/pricing
- MinerU, licencja: https://github.com/opendatalab/MinerU/blob/master/LICENSE.md , https://github.com/opendatalab/MinerU/releases/tag/mineru-3.1.0-released
- Ranking OmniDocBench (zewnętrzny): https://blog.roboflow.com/best-open-source-ocr-models/
- Apache Tika: https://tika.apache.org/4.0.0/ , https://repo1.maven.org/maven2/org/apache/tika/tika-app/3.3.2/
- Maven Central (wersje Java): https://repo1.maven.org/maven2/org/apache/pdfbox/pdfbox/ , https://repo1.maven.org/maven2/org/apache/poi/poi-scratchpad/ , https://repo1.maven.org/maven2/net/sourceforge/tess4j/tess4j/
- odfpy: https://github.com/eea/odfpy
- LibreOffice, licencje: https://metadata.ftp-master.debian.org/changelogs/main/libr/libreoffice/stable_copyright
- Alpine: https://pkgs.alpinelinux.org/package/v3.20/community/x86_64/tesseract-ocr-data-pol , https://pkgs.alpinelinux.org/package/v3.23/community/x86_64/py3-onnxruntime
