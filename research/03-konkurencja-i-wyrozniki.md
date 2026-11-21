# 03. Konkurencja, prior art i wyróżniki (strategia wygranej)

Stan na 2026-11-21. Wszystko poniżej sprawdzone w sieci w tej sesji, chyba że zaznaczono inaczej (sekcja „Czego nie udało się zweryfikować”).

## Rekomendacja

**Główna: „kompilator formularzy”, a nie OCR.** Pozycjonujemy rozwiązanie jako moduł importu do Generatora Formularzy e-Usług: lokalny model tylko *rozumie* blankiet, a JSON *składa* kod deterministyczny z biblioteki sekcji predefiniowanych COI. Na wyjściu zawsze stoi linter z auto-naprawą, więc plik zawsze się importuje.
Trzy rzeczy, które robimy przed wszystkim innym: (1) linter + auto-naprawa reguł technicznych, (2) biblioteka sekcji predefiniowanych z gotowymi warunkami `SHOW`, słownikami i danymi inicjalnymi, (3) harness oceny względem dwóch referencyjnych JSON-ów z liczbą na slajdzie.
Potem: ekran weryfikacji „dokument obok formularza” z pochodzeniem każdego pola oraz podgląd e-formularza liczący JSONata na żywo.
Dowód zgodności pokazujemy wprost: `docker run --network none`, raport licencji, tabela kosztu na formularz.

**Zapasowa: tryb „reguły najpierw”.** Jeżeli lokalny LLM jest za wolny lub niestabilny na M4 16 GB albo na maszynie jury, usługa przechodzi na ekstrakcję heurystyczną i szablony sekcji, a LLM służy najwyżej do upraszczania etykiet. Wynik jest uboższy, ale poprawny, szybki i powtarzalny. Ten tryb budujemy jako pierwszy, bo jest też ścieżką awaryjną trybu głównego.

**Powód:** w 2025 r. wygrywał „potencjał do wdrożenia”, a jury potrafiło odrzucić slajdy i zażądać demo na żywo. Tegoroczne zadanie COI dodaje do tego uruchomienie na nieznanych plikach.

Uwaga o czasie: wydarzenie trwa 24 h (21–22.11), wyniki w niedzielę. Ranking w sekcji 4 jest liczony pod ok. 20 godzin pracy 3–4 osób. Godzinę oddania sprawdźcie u organizatora.

## 1. Co wygrywało w HackNation 2025

Fakty: 16 wyzwań, ponad 1500 uczestników, 24 h, po 25 tys. zł. Jury wybierało po 3 finalistów na wyzwanie, finaliści prezentowali prototypy, wygrywał ten z największym „potencjałem do wdrożenia w administracji publicznej” ([gov.pl](https://www.gov.pl/web/cyfryzacja/tysiace-pomyslow-24-godziny-i-jeden-cel--usprawnic-panstwo-w-bydgoszczy-zakonczyl-sie-hacknation-2025)). Wyzwanie COI „Prawda w sieci” wygrał zespół „no signal”. Nie znalazłem jego repozytorium ani opisu.

| Źródło | Co wiemy | Wzorzec dla nas |
|---|---|---|
| Solvro, finalista „Kontrola zakładów wzajemnych” ([blog](https://solvro.pwr.edu.pl/en/blog/hacknation-2025/)) | Django + Playwright + Next.js + mały lokalny LLM. Drugi wynik po I etapie. Jury nie chciało slajdów, poprosiło o demo konkretnego przypadku. Zespół musiał improwizować i przegrał. | Obrona to demo, nie prezentacja. Ćwiczymy scenariusz na obcym pliku. |
| White Hats PWr, „AI w służbie decyzji” ([WIT PWr](https://wit.pwr.edu.pl/en/news/white-hats-win-hacknation-2025-370.html)) | Silnik + dodatek do Worda. Zespół uznał interfejs za „zdecydowanie najważniejszy”. | Wchodzimy w narzędzie, którego urzędnik już używa. U nas: plik gotowy do importu w Generatorze. |
| Treść zadania COI 2025 ([PDF w repo](https://github.com/Ch3shireDev/hacknation-2025)) | Kryteria: związek z wyzwaniem 25%, potencjał wdrożeniowy 25%, walidacja i bezpieczeństwo 20%, UX 15%, innowacyjność 15%. Wymagane makiety i scenariusz pozytywny oraz negatywny. | COI ocenia bezpieczeństwo i obsługę błędów. Pokazujemy też scenariusz negatywny (zły plik, nieczytelny skan). |
| Repo „Odnalezione zguby” ([GitHub](https://github.com/wertezaj/HACKNATION_2025_odnalezione_zguby)) | React + Express, OpenAI Vision i Google Maps przez API, klucz w kliencie, brak Dockera. Nie potwierdziłem, że to repo zwycięzcy. | W 2025 r. takie skróty uchodziły. W 2026 r. COI ich zakazuje, więc zgodność formalna sama jest wyróżnikiem. |
| Losy projektów po roku ([takajestbydgoszcz.pl](https://takajestbydgoszcz.pl/artykul/umowa-w-nask-i-inspiracja-n2582784)) | „Nagroda nie oznacza jednak automatycznego wdrożenia.” NASK podpisał umowę i zatrudnił członka zespołu. KAS testuje dwa rozwiązania. ZUS wstrzymał prace, bo zależą od integracji i nowego modelu procesu. CPK nie wdraża. | Wdrażalne jest to, co nie wymaga integracji i zmian prawa. Nasz moduł jest samodzielny: plik wchodzi, JSON wychodzi. |

## 2. Kontekst COI i sposób myślenia jurora

| Pojęcie | Co to jest (zweryfikowane) | Wniosek |
|---|---|---|
| Generator Formularzy e-Usług | Narzędzie online do tworzenia, edycji i publikacji formularzy, głównie dla JST. Publikacja w mobywatel.gov.pl, autouzupełnianie z rejestrów, integracja z e-Doręczeniami, w planie EZD. Ma „docelowo zastąpić” narzędzia ePUAP i nForms ([COI](https://coi.gov.pl/realizacje/rozwoj-cyfrowej-tozsamosci)). | COI ma do przeniesienia tysiące formularzy samorządowych. Liczy się przepustowość i standaryzacja. |
| Multiportal RP | Przebudowa gov.pl w jeden system dla całej administracji, ze wsparciem AI. Start prac zapowiedziany na jesień 2026 ([wnp.pl](https://www.wnp.pl/rynki/dyrektor-coi-multiportal-rp-pomoze-zalatwiac-sprawy-urzedowe-prace-nad-nim-rusza-jesienia,1067682.html), [ITwiz](https://itwiz.pl/coi-przeznaczy-290-mln-zl-na-rozbudowe-infrastruktury-it-i-gpu/)). | JSON ma być czytelny maszynowo także dla agentów AI (tak mówi treść zadania). |
| AI Hub | Wniosek na 160 mln zł: centralna infrastruktura, procedury, piaskownica, API. Do 500 GPU. Modele: „w szczególności PLLuM i Bielik”. Dla administracji centralnej i samorządowej ([ITwiz](https://itwiz.pl/coi-przeznaczy-290-mln-zl-na-rozbudowe-infrastruktury-it-i-gpu/)). | Polski model open-weight to naturalny wybór wizerunkowy. Architektura z wymiennym modelem pasuje do AI Hub. |
| Podejście COI do AI | Urzędnik jako „audytor i decydent”. Zero Trust, algorytmy „odizolowane od publicznej sieci”. COI wdraża PLLuM ([COI](https://www.coi.gov.pl/strefa-wiedzy/wpis/ai-jako-wsparcie-dla-urzednika)). | Człowiek zatwierdza, system pokazuje dowody. Praca bez sieci. |
| Kod mObywatela | Opublikowano tylko design system aplikacji mobilnej (komponenty UI, kolory, style, piktogramy), licencja MIT, dostęp po zalogowaniu ([instalki.pl](https://www.instalki.pl/news/bezpieczenstwo/open-source-wedlug-ministerstwa-cyfryzacji-opublikowali-kod-mobywatela-ale-tylko-ui/), [android.com.pl](https://android.com.pl/tech/1005279-kod-zrodlowy-mobywatela-opublikowany/)). | Nie ma oficjalnego pakietu npm dla weba. Podgląd stylizujemy sami, wzorując się na wizualizacjach z materiałów. Bez godła i logotypów. |
| CRWDE, ePUAP | Repozytorium wzorów dokumentów prowadzone w ePUAP na podstawie art. 19b ustawy o informatyzacji. Wzór ma wyróżnik, schemat i wizualizację ([lexlege](https://lexlege.pl/ustawa-o-informatyzacji-dzialalnosci-podmiotow-realizujacych-zadania-publiczne/art-19b/)). | To dług, który Generator ma spłacić. Dobre zdanie na slajd o problemie. |
| Prosty język | MC poleca Jasnopis i Logios jako bezpłatne narzędzia webowe. Zdania do 15–20 wyrazów ([gov.pl](https://www.gov.pl/web/cyfryzacja/prosty-jezyk)). Standardy COI z materiałów zadania dodają listę błędów: słowa powyżej 4 sylab, formy bezosobowe, „dokonać”, „posiadać”, imiesłowy na „-ąc”. | Nie wolno nam wołać zewnętrznych serwisów. Piszemy własny, offline’owy linter języka oparty na liście COI. |

Format JSON Generatora i jego renderer: nic publicznego nie znalazłem. Jedynym źródłem są materiały organizatora.

**Co skłoni jurora COI do wdrożenia:** (1) plik importuje się bez poprawek, (2) wynik wygląda jak zaprojektowany przez ich analityka (sekcje „Twoje dane”, „Adres”, „Podmiot wniosku”), (3) urzędnik widzi, skąd wzięło się każde pole, (4) działa bez internetu na zwykłym serwerze, (5) znany koszt i licencje. Oba referencyjne JSON-y mają ok. 70 komponentów i 29–31 reguł `SHOW`. Zespół, który tylko przepisze blankiet, przegra na zależnościach.

## 3. Prior art

| Nazwa | Wersja / data | Licencja | Python 3.14 / Java | M4 16 GB | Werdykt |
|---|---|---|---|---|---|
| Tim Paul (GDS), form-extractor-prototype ([repo](https://github.com/timpaul/form-extractor-prototype), [wpis](https://www.timpaul.co.uk/posts/using-ai-to-generate-web-forms-from-pdfs/)) | 2024–2025 | MIT | Node.js | n/d (LLM przez API) | **Pożyczamy idee**: schemat pośredni z `answer_type`, `hint_text`, `needs_routing`. Modelu przez API użyć nie wolno. |
| CommonForms / FFDNet ([repo](https://github.com/jbarrow/commonforms)) | 0.2.0, w `pyproject` 0.2.1 | Kod: brak pliku LICENSE (404). Zależy od `ultralytics`. | `>=3.10`, 3.14 niepotwierdzone | CPU, ONNX | **Odrzucić FFDNet** (ryzyko AGPL). Wariant FFDetr opisany jako „Apache-licensed” warto sprawdzić tylko przy zapasie czasu. |
| Docling (IBM) ([PyPI](https://pypi.org/project/docling/)) | 2.95.0 w indeksie | MIT | 3.14 niepotwierdzone | tak, CPU | Kandydat na parser układu. Szczegóły w raporcie o ekstrakcji. |
| PyMuPDF | – | AGPL-3.0 lub komercyjna ([docs](https://pymupdf.readthedocs.io/en/latest/_sources/about.rst)) | – | – | **Zakaz.** Najczęstsza pułapka licencyjna. |
| Surya, marker-pdf | – | GPL-3.0 lub wagi OpenRAIL z progiem przychodu ([repo](https://github.com/VikParuchuri/marker)) | – | – | **Zakaz.** |
| LayoutLMv3 | – | CC BY-NC-SA 4.0 ([karta HF](https://huggingface.co/microsoft/layoutlmv3-large)) | – | – | **Zakaz** (niekomercyjna). |
| FUNSD, XFUND | – | tylko niekomercyjne ([FUNSD](https://guillaumejaume.github.io/FUNSD), [QueryForm](https://arxiv.org/pdf/2211.07730)) | – | – | Tylko jako inspiracja. Nie trenować na nich. |
| Bielik 11B v3.1 | 10.11.2026 | Apache 2.0, karta HF za formularzem ([arXiv](https://arxiv.org/pdf/2604.10799)) | n/d (runtime) | tylko kwantyzacja, ciasno | Dobry wizerunkowo. Wybór modelu w raporcie o LLM. |
| PLLuM 2512 | 4B, 12B | Apache 2.0. Warianty 8B i 70B na licencji Llama ([porównanie](https://pasqualepillitteri.it/en/news/32726/european-open-llms-compared-languages-licenses)) | n/d | 4B tak, 12B ciasno | Tylko warianty Apache. Źródło wtórne. |
| `jsonata` (JS) | 2.2.2 | MIT ([licenses.dev](https://licenses.dev/npm/jsonata/2.2.2)) | przeglądarka | tak | **Użyć** w podglądzie. |
| `jsonata-python` | 0.7.0 | Apache-2.0 ([repo](https://repos.ecosyste.ms/hosts/GitHub/repositories/rayokota%2Fjsonata-python)) | 3.14 niepotwierdzone | tak | **Użyć** w linterze do sprawdzania warunków. |
| Azure Document Intelligence, AWS Textract, Google Form Parser | – | SaaS | – | – | Zakazane regulaminem. Zwracają pary klucz–wartość, nie projekt formularza. |
| Jotform Smart PDF Forms, Fillout ([Jotform](https://www.jotform.com/help/548-how-can-i-import-my-own-pdf-to-jotform), [Fillout](https://www.fillout.com/help/ai-forms.md)) | – | SaaS | – | – | Jotform najlepiej działa na PDF z polami AcroForm, część pól pomija. Kopiują pola, nie przeprojektowują. |
| SimpliGov SimpliAI Forms ([komunikat](https://insider.govtech.com/california/sponsored/simpligov-introduces-simpliai-forms-to-help-government-agencies-turn-pdfs-into-digital-forms-in-minutes)) | 04.2026 | SaaS | – | – | Deklaruje ponad 80% oszczędności czasu, bez metodyki i bez liczb o trafności. |
| GSA 10x Forms Platform ([strona](https://federalist-9ab3a388-1535-4bd5-a4bf-04c7933172d6.sites.pages.cloud.gov/site/gsa-tts/forms/)) | – | nie ustalono | – | – | Import PDF do kreatora, skip logic, USWDS. Ten sam model: import jako funkcja kreatora. |

**Czego prior art nie ma, a my możemy mieć:** przeprojektowania do standardu organizacji, warunków między polami (Tim Paul pisze wprost, że routing jest tylko flagowany), słowników i danych z rejestrów, jawnej pewności i pochodzenia pola, pracy offline. Tim Paul podsumowuje, że takie narzędzie zawsze coś myli i najlepiej działa jako rozszerzenie kreatora formularzy z poprawką człowieka ([wpis z 2025 r.](https://www.timpaul.co.uk/posts/could-ai-convert-all-the-pdf-forms-on-gov-uk-into-web-forms/)). To jest nasza teza na slajd.

Prace naukowe: CommonForms pokazuje, że detektor obiektów znajduje pola tekstowe, pola wyboru i podpisy (AP 81,0 dla FFDNet-L). AutoFormBench potwierdza przewagę detektorów nad klasycznym OpenCV ([arXiv](https://arxiv.org/abs/2603.29832)). Dla nas to argument, że na czystych blankietach z warstwą tekstową wystarczą heurystyki (kropki, kwadraty, tabele), a detektor jest zbędnym ryzykiem licencyjnym.

## 4. Wyróżniki: ranking wpływ / nakład

Kryteria: K = kompletność 30%, I = intuicyjność 20%, O = oryginalność 10%, J = jakość kodu 20%, W = potencjał wdrożeniowy 20%.

| # | Pomysł | Kryterium | Nakład | Dlaczego juror to doceni |
|---|---|---|---|---|
| 1 | Linter reguł technicznych z auto-naprawą (unikalne `id` i `techName`, dozwolone typy i walidatory, każde odwołanie w JSONata wskazuje istniejące pole, spójny `flow`) | K, J, W | 4–6 h | Plik zawsze się importuje. To warunek wszystkiego. |
| 2 | Biblioteka sekcji predefiniowanych jako szablony z gotowymi `SHOW`, TERYT, Kraje, PESEL | K (I, III), W | 4–6 h | Wynik wygląda jak praca analityka COI. Daje większość z ok. 30 reguł `SHOW` bez LLM. |
| 3 | Harness oceny względem 2 referencji (pokrycie pól, zgodność typów, sekcji, walidatorów, liczba warunków) i regresja na 9 formularzach × 8 formatów | J, W, O | 3 h | Liczba na slajdzie zamiast deklaracji. Mało zespołów to zrobi. |
| 4 | Pakiet zgodności: `--network none` na żywo, raport licencji, SBOM, non-root, tmpfs, JWT, sprawdzanie MIME | J, W | 2–3 h | COI w 2025 r. dawało 20% za bezpieczeństwo. Dowód, nie obietnica. |
| 5 | Ścieżka awaryjna z budżetem czasu i postępem na żywo (SSE) | W, I | 2–3 h | Obrona na nieznanym pliku nie może się wyłożyć. |
| 6 | Ekran weryfikacji: dokument obok formularza, ramka źródła pola, pewność, lista „do sprawdzenia” | I, O, W | 6–8 h | Urzędnik jako audytor, dokładnie jak w tekście COI. |
| 7 | Podgląd e-formularza liczący JSONata na żywo | K (rozsz. V), I | 5–7 h | Widać, że warunki działają. Najmocniejszy kadr filmu. |
| 8 | Linter prostego języka na liście błędów COI, widok „przed / po” etykiet | I, O | 2–3 h | Używamy ich własnego standardu jako testu. |
| 9 | Tabela kosztu: zł na formularz, CPU kontra GPU, kontra godziny analityka | W | 1 h | Kryterium wprost wymienia koszt. |
| 10 | Propozycja nowego słownika z uzasadnieniem | K (II) | 2 h | Osobny próg punktowy. |
| 11 | Tryb wsadowy (wiele plików, raport zbiorczy) | K (VI), I | 2 h | Wymieniony w zadaniu. |
| 12 | Dziennik audytowy bez treści pliku (skrót pliku, wersja modelu, użyte reguły) | W | 1 h | Rozliczalność w administracji. |
| 13 | Powtarzalność: temperatura 0, stałe ziarno, diff między przebiegami | J | 1 h | Ten sam plik daje ten sam wynik. |
| 14 | WCAG 2.1 AA frontendu z raportem axe | I, W | 1–2 h | Wymóg standardów COI. |
| 15 | Generator danych testowych do podglądu (poprawny PESEL, NIP) | O | 2 h | Miły dodatek. Tylko przy zapasie czasu. |

Pozycje 1–5 to minimum. Z 6 i 7 wybierzcie najpierw 7, jeśli zabraknie rąk. Kryteria wymieniają „Punkt V (Walidacje pól)”, a w treści zadania punkt V to aplikacja do wizualizacji, walidacje zaś to punkt VI. Zapytajcie mentorów, co liczy się do progu.

## 5. Ryzyka i zabezpieczenia

| Ryzyko | Zabezpieczenie |
|---|---|
| Nieznany plik to skan lub zdjęcie z telefonu | Zestaw testowy z własnych degradacji próbek (obrót, rozmycie, kompresja JPEG, cień). Prostowanie obrazu. Kafelkowanie bardzo wysokich obrazów (do 37 424 px). |
| Za wolno na żywo | Budżet czasu na żądanie, model ładowany przy starcie, mały model kwantyzowany, ścieżka bez LLM. Pomiar czasu dla każdego z 9 formularzy. |
| Naruszenie licencji | Bramka w CI na liście zależności. Zakaz: PyMuPDF, ultralytics, Surya, marker, LayoutLMv3. Sprawdzona licencja każdej wagi modelu. LibreOffice (MPL/LGPL) oznaczyć i uzgodnić z mentorem albo zastąpić. |
| Docker nie buduje się u jury | Obraz dla `amd64` i `arm64`. `onnxruntime` nie ma kół `musllinux`, więc Alpine z Pythonem i ML to pułapka ([issue](https://github.com/microsoft/onnxruntime/issues/25737)): użyć oficjalnego `python:3.14-slim` z przypiętą wersją i uzasadnić w README. Zapas: `docker save` na pendrive, wagi w obrazie lub wolumenie, budowa przetestowana na czystej maszynie. |
| JSON się nie importuje | Linter i schemat. Jeszcze dziś poprosić mentora COI o import jednego naszego pliku do prawdziwego Generatora. |
| Halucynacje modelu | Dekodowanie ograniczone schematem, model zwraca tylko reprezentację pośrednią, finalny JSON składa kod. |
| Jury nie chce slajdów | Scenariusz demo ćwiczony na obcych plikach, w tym scenariusz negatywny. Nagrany film jako zapas. |
| Prawa autorskie | Zwycięzca przenosi prawa majątkowe w 7 dni. Żadnego kodu o niejasnym pochodzeniu, wszyscy członkowie dostępni do podpisu. |

## 6. Film (3 min) i prezentacja (10 slajdów)

**Film.**
- 0:00–0:20: problem. Blankiet z BIP, obywatel drukuje. Jedno zdanie o ręcznej analizie każdego wzoru.
- 0:20–0:50: wrzucamy PDF, postęp na żywo, JSON po kilkudziesięciu sekundach. Na ekranie licznik czasu.
- 0:50–1:30: ekran weryfikacji. Klik w pole podświetla źródło na blankiecie. Jedno pole z niską pewnością poprawione ręcznie.
- 1:30–2:05: podgląd e-formularza. Wybór „Innej osoby” odsłania sekcję, adres z TERYT, PESEL z walidacją.
- 2:05–2:30: to samo na zdjęciu z telefonu i w trybie wsadowym.
- 2:30–2:50: terminal z `--network none`, raport licencji, wynik harnessu.
- 2:50–3:00: koszt na formularz i zdanie o wdrożeniu w Generatorze.

**Prezentacja.**
1. Tytuł i jedno zdanie obietnicy.
2. Problem w liczbach i w słowach COI.
3. Rozwiązanie: od blankietu do gotowego importu, jeden schemat.
4. Architektura: ekstrakcja, model lokalny, reprezentacja pośrednia, składanie, linter.
5. Zgodność ze standardami COI: sekcje predefiniowane, prosty język, przed i po.
6. Zależności, słowniki, dane inicjalne, nowy słownik.
7. Wyniki: metryki względem referencji, czasy, 9 formularzy × 8 formatów.
8. Narzędzie dla urzędnika: weryfikacja, podgląd, tryb wsadowy.
9. Wdrożenie: Docker, bezpieczeństwo, licencje, koszt na formularz, sprzęt.
10. Tabela zgodności z wymaganiami (każdy punkt zadania odhaczony) i plan dalszych prac z COI.

## Źródła

- https://www.gov.pl/web/cyfryzacja/tysiace-pomyslow-24-godziny-i-jeden-cel--usprawnic-panstwo-w-bydgoszczy-zakonczyl-sie-hacknation-2025
- https://www.chip.pl/2025/12/hacknation-2025-relacja
- https://solvro.pwr.edu.pl/en/blog/hacknation-2025/
- https://wit.pwr.edu.pl/en/news/white-hats-win-hacknation-2025-370.html
- https://takajestbydgoszcz.pl/artykul/umowa-w-nask-i-inspiracja-n2582784
- https://cyfrowa.rp.pl/biznes-ludzie-startupy/art43481951-24-godziny-na-cyfrowe-rozwiazania-znamy-zwyciezcow-hacknation-2025
- https://github.com/Ch3shireDev/hacknation-2025 (PDF-y zadań 2025, w tym `PRAWDA_W_SIECI.pdf`)
- https://github.com/wertezaj/HACKNATION_2025_odnalezione_zguby
- https://coi.gov.pl/realizacje oraz https://coi.gov.pl/realizacje/rozwoj-cyfrowej-tozsamosci
- https://www.coi.gov.pl/strefa-wiedzy/wpis/ai-jako-wsparcie-dla-urzednika
- https://itwiz.pl/coi-przeznaczy-290-mln-zl-na-rozbudowe-infrastruktury-it-i-gpu/
- https://www.wnp.pl/rynki/dyrektor-coi-multiportal-rp-pomoze-zalatwiac-sprawy-urzedowe-prace-nad-nim-rusza-jesienia,1067682.html
- https://www.instalki.pl/news/bezpieczenstwo/open-source-wedlug-ministerstwa-cyfryzacji-opublikowali-kod-mobywatela-ale-tylko-ui/
- https://android.com.pl/tech/1005279-kod-zrodlowy-mobywatela-opublikowany/
- https://github.com/slominskiwiktor/mdesign-react
- https://www.gov.pl/web/cyfryzacja/prosty-jezyk
- https://lexlege.pl/ustawa-o-informatyzacji-dzialalnosci-podmiotow-realizujacych-zadania-publiczne/art-19b/
- https://www.timpaul.co.uk/posts/using-ai-to-generate-web-forms-from-pdfs/
- https://www.timpaul.co.uk/posts/could-ai-convert-all-the-pdf-forms-on-gov-uk-into-web-forms/
- https://github.com/timpaul/form-extractor-prototype
- https://github.com/jbarrow/commonforms oraz https://huggingface.co/jbarrow/FFDNet-L
- https://arxiv.org/abs/2509.16506, https://arxiv.org/abs/2603.29832, https://arxiv.org/abs/2609.23679
- https://pypi.org/project/docling/
- https://pymupdf.readthedocs.io/en/latest/_sources/about.rst
- https://github.com/VikParuchuri/marker
- https://huggingface.co/microsoft/layoutlmv3-large
- https://guillaumejaume.github.io/FUNSD oraz https://arxiv.org/pdf/2211.07730
- https://arxiv.org/pdf/2604.10799 (Bielik v3)
- https://pasqualepillitteri.it/en/news/32726/european-open-llms-compared-languages-licenses
- https://licenses.dev/npm/jsonata/2.2.2
- https://repos.ecosyste.ms/hosts/GitHub/repositories/rayokota%2Fjsonata-python
- https://github.com/microsoft/onnxruntime/issues/25737 oraz https://github.com/microsoft/onnxruntime/issues/26309
- https://www.jotform.com/help/548-how-can-i-import-my-own-pdf-to-jotform
- https://www.fillout.com/help/ai-forms.md
- https://insider.govtech.com/california/sponsored/simpligov-introduces-simpliai-forms-to-help-government-agencies-turn-pdfs-into-digital-forms-in-minutes
- https://federalist-9ab3a388-1535-4bd5-a4bf-04c7933172d6.sites.pages.cloud.gov/site/gsa-tts/forms/
- Materiały organizatora w `Docs/` (treść zadania, regulamin, standardy projektowania, dwa referencyjne JSON-y)

## Czego nie udało się zweryfikować

- Jak wyglądało zwycięskie rozwiązanie COI 2025 („no signal”) i co jury w nim chwaliło. Brak repozytorium, wpisu i filmu.
- Żadnych publicznych cytatów jury z 2025 r. o konkretnych projektach. Wzorce w sekcji 1 pochodzą z relacji uczestników i z kryteriów zadań.
- Czy repo `wertezaj/...odnalezione_zguby` należy do zwycięskiego zespołu OneMoreFix.
- Czy „White Hats” i „Programiści PWR” to ten sam zespół (źródła podają różne nazwy).
- Publiczna dokumentacja formatu JSON Generatora Formularzy lub jego renderera: nie znalazłem żadnej.
- Oficjalny design system gov.pl dla weba (repozytorium, npm, licencja): nie znalazłem. Strona z kodem mObywatela nie wczytała się (renderowana po stronie klienta), licencję MIT znam tylko z mediów.
- Licencje i API Jasnopisu oraz Logiosa: brak informacji. Traktować jako narzędzia tylko do ręcznego użytku.
- Artykuł PAP o Multiportalu RP nie wczytał się. Dane o Multiportalu pochodzą z wnp.pl i ITwiz. Nie potwierdziłem, że prace faktycznie ruszyły.
- Licencja kodu `commonforms` (plik LICENSE zwraca 404) oraz wag FFDNet i FFDetr. Licencji AGPL-3.0 biblioteki `ultralytics` nie potwierdziłem źródłem w tej sesji, jest to wiedza powszechna.
- Wsparcie Pythona 3.14 w Docling, `jsonata-python` i `commonforms`. Dla `onnxruntime` koła `cp314` istnieją od 1.29.0 według zgłoszenia w obcym repozytorium, nie według PyPI.
- Licencje Donut, Florence-2 i Qwen2.5-VL: tylko z agregatorów albo wcale. Licencje PLLuM tylko ze źródła wtórnego.
- Czy GOV.UK Forms, i.AI, 18F lub Code for America mają oficjalny produkt „PDF na formularz”. Znalazłem tylko prywatny prototyp Tima Paula i stronę GSA 10x Forms Platform (bez repozytorium i licencji). i.AI Extract dotyczy dokumentów planistycznych, nie formularzy.
- Regulamin ogólny HackNation 2026: liczba finalistów na wyzwanie, format i czas obrony, godzina oddania.
