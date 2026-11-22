# 14. Opis zgłoszenia

Tekst do formularza oddania projektu (HackNation 2026, zadanie COI „Cyfryzacja formularzy”). Liczby pochodzą z repozytorium, źródła w nawiasach.

## Tytuł

Biurokratka: kompilator formularzy urzędowych do Generatora Formularzy COI

## Opis krótki (1–2 zdania)

Usługa REST, która z blankietu urzędowego w jednym z 8 formatów (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) tworzy przeprojektowany e-formularz zgodny ze standardami COI jako JSON gotowy do importu w Generatorze. Do tego stanowisko urzędnika: dokument obok formularza, pochodzenie każdego pola i podgląd e-formularza na żywo.

## Opis szczegółowy

**Problem.** Urzędy publikują wnioski jako pliki biurowe i skany, a każdy wzór analityk musi ręcznie przeprojektować w Generatorze Formularzy: strony, sekcje, słowniki, warunki i walidacje.

**Rozwiązanie: kompilator, nie OCR.** Plik zamieniamy na dokument z układem (pdfplumber dla PDF, Apache Tika dla plików biurowych, RapidOCR dla zdjęć i skanów), z dokumentu powstaje krótka reprezentacja pośrednia (IR) listy pól, a końcowy JSON składa kod deterministyczny z biblioteki sekcji predefiniowanych COI. Linter sprawdza reguły techniczne i automatycznie naprawia naruszenia. Model językowy pisze wyłącznie IR, nigdy końcowego JSON-a, więc wynik zawsze przechodzi reguły techniczne. Awaria modelu nie kończy się błędem: usługa przechodzi na tryb reguł.

**Model open-weight, wymienny konfiguracją.** Qwen3.5-9B (Apache-2.0), na hackathonie wołany przez EdenAI na endpoincie UE. Klient używa tylko wspólnej części API zgodnego z OpenAI, więc przejście na lokalny `llama-server` na infrastrukturze COI to zmiana jednej zmiennej `LLM_BASE_URL`. Przełącznik `LLM_ENABLED=false` daje tryb reguł bez żadnych połączeń sieciowych.

**Stanowisko urzędnika.** Kolejka plików z trybem wsadowym, tekst dokumentu obok podglądu e-formularza, podświetlenie linii źródłowych wybranego pola z pewnością rozpoznania, raport lintera, propozycje nowych słowników i pobranie JSON-a. Urzędnik weryfikuje wynik zamiast przepisywać blankiet.

**Dowody.**
- 53 z 53 blankietów z materiałów (formularze 3–9 we wszystkich formatach): HTTP 200 i 0 błędów lintera (`research/08-macierz-formatow.md`).
- 6 wynikowych JSON-ów w `outputs/` w trybie modelu, 0 błędów lintera (`outputs/README.md`).
- Model odtwarza 64–82% pól referencji organizatora (ok. 90% po ocenie znaczeniowej) (`research/10-pokrycie-referencji.md`).
- Tryb reguł bez modelu: 100% pól referencji 1 i 57% referencji 5 (`research/10`, pomiar W6); zdjęcia krzywe, obrócone i z perspektywą prostowane przed OCR (`research/11-odpornosc-ocr.md`).
- Zgodność z oficjalnym schematem JSON sprawdzana testem dla wszystkich wyników i referencji (`research/13-zgodnosc-z-regulami.md`).
- 588 testów backendu i 204 frontendu.

**Rozszerzenia.** I: słowniki i 54 pola z rejestrów; II: propozycje nowych słowników w raporcie; III: 117 warunków SHOW; IV: upload i podgląd JSON-a; V: podgląd e-formularza z JSONata na żywo; VI: walidacje (PESEL, NIP, REGON, kod pocztowy).

**Bezpieczeństwo i licencje.** Przesłany plik istnieje tylko w pamięci, w logach jest tylko skrót SHA-256 i rozmiar. Walidacja uploadu po sygnaturze treści, kontenery bez uprawnień i z systemem plików tylko do odczytu, limit zapytań. Wszystkie zależności na licencjach bez copyleftu, sprawdzane automatyczną bramką (`devtools/check_licenses.py`, `research/09-licencje.md`); dwa świadome wyjątki MPL-2.0 w zależnościach przechodnich (D26).

**Koszt i wdrożenie.** Ok. 0,001 USD za formularz przez EdenAI, zero w trybie reguł i przy modelu lokalnym. Całość uruchamia `docker compose up -d --build --wait` (trzy kontenery), sprawdzone na czystym Debianie 13 amd64.

**Linki.** Demo: https://formularze.heckyeah.pl (model Qwen3.5-9B przez EdenAI, zapas: tryb reguł). Film (87 s): https://formularze.heckyeah.pl/film.mp4, w repozytorium `web/public/film.mp4`, źródło w `video/`. Repozytorium: https://github.com/Adimac93/hacknation2026.
