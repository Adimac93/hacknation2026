# 06. Porównanie modeli (decyzja D20)

Stan na 2026-11-21, ok. 19:40. Krok A (inwentarz pól, `api/src/formcompiler/llm.py`) uruchomiony przez EdenAI (endpoint UE) na formularzach referencyjnych 1 i 5. Narzędzie: `devtools/compare_models.py`. Łączny koszt: 0,0048 USD.

## Metoda

- Wzorzec: strony przedmiotu wniosku z dekompilacji referencyjnego JSON-a (`ir.pages[1:-2]`), adresat i flagi wnioskodawcy odczytane ręcznie.
- Tekst wejściowy: warstwa tekstowa PDF (`pdfplumber`).
- Wariant **loo** (leave-one-out): oceniany formularz nie występuje w przykładach few-shot. To jest miara uczciwa, bliska sytuacji z obrony.
- Wariant **full**: oceniany formularz jest w przykładach. Pokazuje tylko, czy model umie skopiować wzorzec; nie służy do wyboru.
- Pokrycie: dopasowanie etykiet po normalizacji (`difflib` ≥ 0,6). „Nadmiarowe”: pola spoza wzorca (w nawiasie: dublujące bibliotekę sekcji predefiniowanych).

## Wyniki

| Model | Formularz | Wariant | Pokrycie | Zgodność typów | Nadmiarowe (z biblioteki) | Flagi | Adresat | Czas [s] | Tokeny wej./wyj. | Koszt [USD] |
|---|---|---|---|---|---|---|---|---|---|---|
| `mistral/ministral-8b-2512@eu` | 1 | loo | 2/4 | 100% | 4 (0) | 2/3 | nie | 6,1 | 4014/651 | 0,00077 |
| `flexai/Qwen3.5-9B@eu` | 1 | loo | 4/4 | 100% | 0 (0) | 3/3 | nie | 2,5 | 3765/272 | 0,00042 |
| `mistral/ministral-8b-2512@eu` | 5 | loo | 3/7 | 67% | 6 (0) | 3/3 | tak | 7,2 | 2770/1075 | 0,00063 |
| `flexai/Qwen3.5-9B@eu` | 5 | loo | 2/7 | 100% | 5 (0) | 3/3 | nie | 4,6 | 2565/555 | 0,00034 |
| `mistral/ministral-8b-2512@eu` | 1 | full | 4/4 | 100% | 0 (0) | 3/3 | tak | 5,7 | 4614/457 | 0,00084 |
| `flexai/Qwen3.5-9B@eu` | 1 | full | 4/4 | 100% | 0 (0) | 3/3 | tak | 3,3 | 4312/273 | 0,00047 |
| `mistral/ministral-8b-2512@eu` | 5 | full | 5/7 | 100% | 9 (2) | 3/3 | tak | 9,9 | 3841/1648 | 0,00091 |
| `flexai/Qwen3.5-9B@eu` | 5 | full | 4/7 | 100% | 1 (0) | 3/3 | tak | 3,4 | 3535/450 | 0,00042 |

Suma dla wariantu loo:

| | Ministral-3-8B | Qwen3.5-9B |
|---|---|---|
| Pokrycie pól | 5/11 | 6/11 |
| Nadmiarowe pola | 10 | 5 |
| Flagi wnioskodawcy | 5/6 | 6/6 |
| Adresat | 1/2 | 0/2 |
| Średni czas | 6,7 s | 3,6 s |
| `seed` na liście parametrów EdenAI | tak | nie (lista pusta) |

## Wnioski

- Na dwóch formularzach (11 pól) różnica jest mała i statystycznie słaba. Qwen wypada nieco lepiej w pokryciu, nadmiarowych polach i flagach, jest dwa razy szybszy i tańszy.
- Ministral ma potwierdzone `seed`, czyli lepszą powtarzalność (wymóg z `CLAUDE.md`: temperatura 0, stałe ziarno).
- Adresata i tak ustala `heuristics.py`; model może go tylko poprawić.
- Pokrycie 5–6/11 na loo pokazuje, że prompt kroku A wymaga pracy niezależnie od modelu. Następna runda: złote IR formularzy 3–9 (D11) i ocena na nich, zamiast na dwóch referencjach.

## Decyzja (19:45)

Zostaje `Ministral-3-8B-Instruct-2512` (D20): potwierdzone `seed`, wyniki w granicach szumu. Porównanie powtórzymy na złotych IR formularzy 3–9.
