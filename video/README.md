# Film o Biurokratce

Film (93 s, 1920×1080, 30 kl./s, bez lektora) składany kodem w [Remotion](https://www.remotion.dev/), tak jak film zespołu w projekcie AED. Nie jest częścią usługi ani obrazów Docker.

## Jak powstaje

1. `node video/capture.mjs [URL]` (z katalogu głównego repozytorium) robi zrzuty ekranu działającej usługi przez Playwright z `web/node_modules`. Domyślnie z publicznego demo `https://formularze.heckyeah.pl`: wybiera przykładowy blankiet formularza 6 z listy przykładów, czeka na wynik i fotografuje kolejkę, widok „Dokument i formularz”, JSON, raport i odrzucony zły plik. Zrzuty trafiają do `video/public/zrzuty/` (1600×900 @2x).
2. `src/Pitch.tsx` składa 13 scen: problem, potok, animowane przeciągnięcie pliku do strefy uploadu, przykłady COI, kolejne kroki pracy urzędnika na zrzutach, przypadek negatywny, liczby, wymienny model, bezpieczeństwo, zakończenie. Logo pochodzi z `logo-pack/` (kopia w `public/logo/`), kolory i fonty z `DESIGN.md`.
3. Liczby na ekranie pochodzą z repozytorium: lista przykładów z `web/public/samples/index.json` (import), pozostałe stałe w `N` mają w komentarzu plik źródłowy (`research/08`, `outputs/README.md`, `research/10`, wyniki testów). Przed renderem sprawdź, czy się nie zmieniły.

```sh
cd video
npm install
npm run studio     # podgląd w przeglądarce
npm run render     # out/biurokratka-pitch.mp4
```

## Licencja Remotion

Remotion nie jest open source w rozumieniu `CLAUDE.md` (zasada 1): ma własną licencję, darmową dla osób prywatnych i firm do 3 osób. Dlatego żyje w osobnym katalogu `video/`, poza `api/` i `web/`, nie trafia do obrazów Docker i nie jest objęty bramką licencji (`devtools/check_licenses.py`). To narzędzie do zrobienia materiału na obronę, nie zależność rozwiązania.
