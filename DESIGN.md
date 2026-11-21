# DESIGN.md — Biurokratka

Zasady budowania interfejsów Biurokratki (frontend `web/`: React 19, Vite, TypeScript). Źródło prawdy wizualnej: `ksiega-znaku-biurokratka.pdf` (PDF). Ten plik jest wiążący dla agentów AI i ludzi. Jeśli coś tu nie pasuje do zadania, zapytaj — nie improwizuj nowego stylu.

## 1. Zasady nadrzędne

1. **Dostępność przed estetyką.** Minimum WCAG 2.1 AA w każdym widoku. Element, który nie spełnia wymagań, nie trafia do `main`.
2. **Płasko i na siatce.** Zero zaokrągleń, zero gradientów, zero dekoracji. Strukturę budują linie 2 px i siatka.
3. **Atrament na papierze.** Interfejs jest w ~90% czarno-szary. Czerwień tylko dla akcji głównej, postępu, znaku i błędów.
4. **Wszystko do lewej.** Nagłówki, tekst, etykiety w przyciskach. Nic nie centrujemy (wyjątek: litera w kratce).
5. **Tylko tokeny.** Żadnych surowych hexów, px spoza skali ani nowych fontów w komponentach.

## 2. Tokeny

Wklej do `web/src/styles/tokens.css` i używaj wyłącznie przez `var(--…)`.

```css
:root {
  /* kolory podstawowe */
  --color-bg: #f3f2f2;          /* Papier — tło */
  --color-surface: #eae9e9;     /* Szary arkusz — tła sekcji, karty */
  --color-white: #ffffff;       /* Biel — pola input, litery KRATKI na ciemnym */
  --color-text: #201e1d;        /* Atrament — tekst, linie, ramki kratek */
  --color-accent: #ec3013;      /* Czerwień kratki — znak, akcja główna, postęp */

  /* kolory uzupełniające (tylko tekst i stany) */
  --color-accent-text: #ae1800; /* czerwień tekstowa: linki, komunikaty błędów, drobny akcent */
  --color-text-muted: #605d5d;  /* grafit: podpowiedzi, tekst drugorzędny */
  --color-divider: color-mix(in srgb, #201e1d 40%, transparent);
  --color-border-input: #605d5d;
  --color-success: #2e6b3e;
  --color-warning: #8a5a00;
  --color-info: #2459a0;
  --color-accent-hover: #dd2b0f;   /* accent-600 */
  --color-accent-tint: #ffe0d9;    /* accent-200, tła ostrzeżeń/zaznaczeń */
  --color-track: #d7d3d3;          /* neutral-300, tor paska postępu */

  /* typografia */
  --font-body: "Archivo", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --font-fallback-office: Arial, "Liberation Sans", sans-serif; /* tylko DOCX/e-mail */

  /* odstępy (jedyna dozwolona skala) */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-6: 24px; --space-8: 32px; --space-12: 48px; --space-16: 64px;

  --rule: 2px;      /* każda linia podziału */
  --radius: 0;      /* zawsze 0 */
  --shadow-md: 0 3px 10px color-mix(in srgb, #2d2b2b 16%, transparent); /* tylko dialogi i menu */
}
```

Fonty: Archivo (400, 600, 800) i IBM Plex Mono (400, 600), licencja SIL OFL. **Hostuj lokalnie** (`web/public/fonts/`, `@font-face`, `font-display: swap`) — usługa nie może pobierać niczego z sieci (patrz CLAUDE.md, zasada 2). Nie używaj Google Fonts CDN w produkcji.

## 3. Kontrast — tabela dozwolonych par

| Tekst / tło | Kontrast | Wolno używać do |
|---|---|---|
| Atrament / Papier | 14,8:1 | każdy tekst |
| Papier / Atrament | 14,8:1 | każdy tekst |
| Czerwień tekstowa `#ae1800` / Papier | 6,4:1 | każdy tekst, linki, błędy |
| Grafit `#605d5d` / Papier | 5,6:1 | tekst drugorzędny (min. 15 px) |
| Biel / Zieleń, Bursztyn, Błękit stanu | ≥ 5,3:1 | etykiety stanów |
| Czerwień kratki `#ec3013` / Papier | 3,7:1 | **tylko** ikony, obramowania, fokus, tekst ≥ 24 px lub ≥ 19 px bold |
| Biel / Czerwień kratki | 4,2:1 | **tylko** tekst ≥ 19 px bold (przycisk główny) |
| Biel / Czerwień tekstowa `#ae1800` | 7,2:1 | każdy tekst (małe przyciski główne) |
| Atrament / Czerwień kratki | 4,0:1 | **tylko** tekst ≥ 19 px bold, litery znaku |

Zakaz: `#ec3013` jako kolor tekstu poniżej 24 px. Zakaz: tekst z `opacity` lub `color-mix` jako sposób na „wyciszenie” — użyj `--color-text-muted`.

## 4. Typografia w interfejsie

| Rola | Krój | Waga | Rozmiar / interlinia |
|---|---|---|---|
| Tytuł strony | Archivo | 800 | 42 / 1.12, `letter-spacing: -0.015em` |
| Nagłówek sekcji | Archivo | 800 | 25 / 1.12 |
| Podtytuł | Archivo | 800 | 20 / 1.2 |
| Etykieta pola | Archivo | 600 | 15 / 1.4 |
| Tekst | Archivo | 400 | 15 / 1.55 (min. 15 px) |
| Podpowiedź pod polem | Archivo | 400 | 14 / 1.5, `--color-text-muted` |
| Dane, JSON, PESEL/NIP/REGON, `techName` | IBM Plex Mono | 400 / 600 | 14 / 1.6 |
| Etykieta sekcji (kicker) | Archivo | 600 | 13, wersaliki, `letter-spacing: 0.08em` |

- Nagłówki semantyczne `h1`→`h3` bez przeskakiwania poziomów; jeden `h1` na widok.
- Długość wiersza tekstu ciągłego maks. ~70 znaków (`max-width: 68ch`).
- `text-wrap: pretty` dla akapitów. Nie justuj tekstu.
- Rozmiary w `rem`, żeby działało powiększenie przeglądarki do 200% bez utraty treści.

## 5. Znak w interfejsie

- W nagłówku aplikacji: **wersja liniowa** (11 kratek w rzędzie), szerokość ≥ 154 px.
- Ekran startowy / pusty stan: wersja podstawowa (2 rzędy po 6), szerokość ≥ 96 px.
- Favicon, ikona PWA: **sygnet** (B nad K) na kwadracie Papieru lub Czerwieni.
- Pole ochronne: 1 szerokość kratki z każdej strony.
- Znak jest SVG/komponentem z `role="img"` i `aria-label="Biurokratka"`. Litery w kratkach nie są czytane osobno. Link do strony głównej: `<a href="/" aria-label="Biurokratka — strona główna">`.
- Wersje kolorystyczne: jasna (domyślna), ciemna (KRATKA z białymi literami), na czerwieni (KRATKA w atramencie), achromatyczna. Nie twórz innych.
- Nie animuj, nie obracaj, nie rozciągaj, nie zmieniaj kroju liter w znaku.

## 6. Układ

- Siatka 12 kolumn, `gap: var(--space-6)`, marginesy strony `var(--space-8)` (desktop) / `var(--space-4)` (mobile).
- Maks. szerokość treści 1280 px; formularze maks. 720 px.
- Sekcje oddziela `border-top: var(--rule) solid var(--color-divider)`. Granica główna (nagłówek aplikacji, początek tabeli) — `var(--color-text)`.
- Karty: `background: var(--color-surface)`, bez cienia, bez obramowania lub z linią 2 px. Cień tylko dla warstw nad treścią (dialog, menu rozwijane).
- Responsywność: mobile-first, bez stałych wysokości dla bloków z tekstem, bez poziomego przewijania strony przy 320 px.

## 7. Komponenty

### Przycisk
- Główny: tekst biały, Archivo 800. Tło `--color-accent` (`#ec3013`, 4,2:1) tylko przy etykiecie ≥ 19 px; przy mniejszej etykiecie tło `--color-accent-text` (`#ae1800`, 7,2:1 z bielą).
- Drugorzędny: przezroczysty, `border: 2px solid var(--color-text)`, tekst atramentowy.
- Tekstowy (ghost): tylko tekst atramentowy z podkreśleniem na hover.
- Etykieta wyrównana do lewej, ikona strzałki po prawej stronie etykiety.
- Wysokość min. 44 px, padding `12px 16px`. Hover: `--color-accent-hover`; pressed: `--color-accent-text`.
- Na stronie maksymalnie jeden przycisk główny.
- `disabled` — `opacity: .45` + `aria-disabled`, ale nadal czytelna etykieta; preferuj wyjaśnienie, dlaczego akcja jest niedostępna.

### Pole tekstowe
- `<label for>` zawsze widoczny, nad polem. Placeholder nie zastępuje etykiety.
- Tło `--color-white`, `border: 2px solid var(--color-border-input)` (≥ 3:1), wysokość min. 44 px.
- Fokus: `outline: 2px solid var(--color-accent); outline-offset: 2px`.
- Wymagane: tekst „(wymagane)” w etykiecie, nie sama gwiazdka; `aria-required="true"`.
- Błąd: obramowanie `--color-accent-text`, komunikat pod polem z ikoną i tekstem, `aria-invalid="true"`, `aria-describedby` → id komunikatu. Komunikat mówi, co zrobić: „Wpisz 11 cyfr numeru PESEL”.
- Pola z danymi (PESEL, NIP, REGON, kod pocztowy) w `--font-mono`, `inputmode="numeric"`, `autocomplete` zgodny ze specyfikacją HTML.

### Kratka wyboru (checkbox / radio)
- Checkbox: kwadrat 24 px, ramka 2 px atrament, zaznaczenie = wypełnienie `--color-accent` z wewnętrznym odstępem 4 px (jak w znaku). Radio jest kołem (jedyny wyjątek od zera zaokrągleń), żeby różnica między wyborem jednokrotnym i wielokrotnym była widoczna kształtem.
- Obszar klikalny (etykieta + kratka) min. 44 × 44 px. Natywny `<input>` ukryty wizualnie, nie `display:none`.
- Grupy w `<fieldset>` z `<legend>`.

### Upload pliku
- Strefa upuszczania: `border: 2px dashed var(--color-text-muted)`, tekst do lewej, lista formatów (PDF, DOC, DOCX, ODS, XLSX, JPG, JPEG, PNG) i limit rozmiaru zawsze widoczne.
- Zawsze dostępny zwykły przycisk „Wybierz plik” (strefa drag & drop nie jest jedynym sposobem).
- Po wyborze: nazwa pliku, rozmiar, przycisk „Usuń”. Komunikat o prywatności: „Plik nie jest zapisywany na serwerze.”

### Postęp analizy
- Belka 12 px: tor `--color-track`, wypełnienie `--color-accent`. `role="progressbar"` z `aria-valuenow/min/max` lub `aria-valuetext` („Krok 2 z 3: analiza struktury”).
- Zmiany kroków ogłaszane w `aria-live="polite"`. Bez spinnerów bez tekstu.
- Respektuj `prefers-reduced-motion: reduce` — wtedy bez animacji przejść.

### Stany i komunikaty
- Sukces / ostrzeżenie / info / błąd: ikona + tytuł + treść. Kolor stanu tylko na ikonie i etykiecie tekstowej (`.tag`), bez kolorowej lewej belki. Tło `--color-surface`, dla błędu `--color-accent-tint`.
- Błąd krytyczny formularza: podsumowanie błędów na górze z linkami do pól, fokus przeniesiony na podsumowanie.

### Tabela
- Nagłówek: Archivo 600, linia dolna 2 px atrament. Wiersze: linia 2 px `--color-divider`. Bez pasków zebry.
- `<th scope>`, `<caption>` (może być wizualnie ukryty). Liczby w `--font-mono`, wyrównane do prawej (jedyny wyjątek od reguły „do lewej”).

### Podgląd JSON
- Tło `--color-text`, tekst `--color-bg`, `--font-mono` 14 px, wartości logiczne/kluczowe `--color-accent-400` (`#ff9783`, 6,9:1 na atramencie).
- Przyciski „Kopiuj” i „Pobierz JSON” obok, z komunikatem potwierdzenia w `aria-live`.

### Dialog
- `<dialog>` natywny lub `role="dialog"` + `aria-modal`, pułapka fokusu, zamknięcie Escape, powrót fokusu do wywołującego elementu. Cień `--shadow-md`, bez zaokrągleń.

## 8. Ikony

- Wyłącznie Lucide (licencja ISC), `stroke-width: 2`, `stroke-linecap: square`, `stroke-linejoin: miter`, rozmiar 20 lub 24 px, kolor `currentColor`.
- Ikona dekoracyjna: `aria-hidden="true"`. Przycisk z samą ikoną: `aria-label` + widoczny tooltip; min. 44 × 44 px.
- Bez emoji w interfejsie.

## 9. Ruch

- Przejścia 120–200 ms, `ease-out`, tylko `opacity` i `transform`.
- Żadnych animacji dekoracyjnych, paralaksy, auto-przewijania. `prefers-reduced-motion` wyłącza wszystko poza zmianą stanu.

## 10. Treść i ton

- Druga osoba, liczba pojedyncza, prosty język. Konkret i następny krok: „Rozpoznaliśmy 24 pola. Sprawdź 3 oznaczone pola przed eksportem.”
- Bez marketingowego entuzjazmu („magia AI”), bez żargonu („obiekt wejściowy”, „payload”) w tekstach dla użytkownika.
- Daty `21.11.2026`, liczby z separatorem spacji (`12 500`), procenty `45%`.
- Nazwa produktu zawsze „Biurokratka” (w tekście ciągłym wielka litera), w znaku — wersaliki w kratkach.
- Teksty interfejsu po polsku; `lang="pl"` na `<html>`.

## 11. Checklista przed commitem (każdy widok)

- [ ] Tylko tokeny z sekcji 2 — brak surowych hexów i fontów w komponentach.
- [ ] `border-radius` = 0 wszędzie, brak gradientów, brak cieni poza dialogiem/menu.
- [ ] Każda para kolorów jest w tabeli z sekcji 3.
- [ ] Pełna obsługa klawiaturą; widoczny fokus 2 px w akcencie; logiczna kolejność Tab.
- [ ] Każde pole ma `<label>`; błędy powiązane przez `aria-describedby`.
- [ ] Cele dotyku ≥ 44 × 44 px.
- [ ] Stan nie jest przekazany wyłącznie kolorem.
- [ ] Działa przy 320 px szerokości i powiększeniu 200%.
- [ ] `prefers-reduced-motion` respektowany.
- [ ] Sprawdzone axe-core (0 naruszeń) i czytnikiem ekranu (NVDA lub VoiceOver) dla nowego przepływu.
- [ ] Żadnych zasobów z zewnętrznych CDN (fonty, ikony, skrypty).

## 12. Zakazy (odrzucamy w review)

- Zaokrąglone narożniki, gradienty, glassmorphism, kolorowe lewe belki w kartach.
- Centrowane nagłówki i etykiety przycisków.
- `#ec3013` jako kolor tekstu < 24 px.
- Placeholder zamiast etykiety; checkbox dla zgód i oświadczeń poza dedykowaną sekcją.
- Nowe kolory „na chwilę”, nowe fonty, ikony spoza Lucide.
- Modyfikacje znaku (kolor, proporcje, krój, animacja).
