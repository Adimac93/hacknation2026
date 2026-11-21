# ruff: noqa: E501, RUF001  (real legal titles with en dashes)
import pytest
from eli import (
    NON_FORM_TITLE,
    Features,
    attachment_starts,
    fix_legacy_text,
    segments,
    text_features,
)


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        (["Dziennik Ustaw – 2 – Poz. 1\n§ 1. Określa się wzór wniosku"], []),
        (
            [
                "ROZPORZĄDZENIE\n§ 1. Wzór określa załącznik do rozporządzenia.",
                "Dziennik Ustaw – 2 – Poz. 1\nZałącznik do rozporządzenia Ministra",
                "WNIOSEK ciąg dalszy",
            ],
            [1],
        ),
        (
            [
                "ROZPORZĄDZENIE",
                "Dziennik Ustaw\nZałączniki do rozporządzenia\nZałącznik nr 1",
                "Załącznik nr 2\nWZÓR",
            ],
            [1, 2],
        ),
        # A label in running text is not an attachment label.
        (["\n".join(["linia"] * 10 + ["Załącznik nr 1 zawiera wzór"])], []),
        # Designed forms put the label anywhere and repeat it on every page.
        (
            [
                "ROZPORZĄDZENIE\nstanowiący załącznik nr 1",
                "Imię\r\nNazwisko\r\nZałącznik nr 1\r\nWZÓR",
                "Ulica\r\nZałącznik nr 1\r\n7. Załączniki\r\nZałączniki",
                "Pola wyboru\r\nZałącznik nr 2\r\nWZÓR",
            ],
            [1, 3],
        ),
        (
            [
                "§ 5. Rozporządzenie wchodzi w życie",
                "Załącznik do rozporządzenia Ministra",
                "Załącznik do rozporządzenia Ministra\nciąg dalszy",
            ],
            [1],
        ),
        # Raster pages: label doubled and split mid-number, gaps without text,
        # an upper-case label, and a form that cites its own attachment.
        (
            [
                "Dziennik Ustaw – 24\r\nZałącznik nr 13 \r\nZałącznik nr 13",
                "Dziennik Ustaw – 25\r\nZałącznik nr 14 Załącznik nr 14",
                "Dziennik Ustaw – 26",
                "Dziennik Ustaw – 27\r\nZałącznik nr 1\r\n5\r\nZałącznik nr 15",
                "Dziennik Ustaw – 34\r\nZałącznik nr Załącznik nr 18 18",
                "Dziennik Ustaw – 38\r\nZałącznik nr 2 Załącznik nr 20 0",
                " ZAŁĄCZNIK nr 24\r\nKODY",
                "Do wniosku dołączam:\r\nZałącznik nr 25 do wniosku",
            ],
            [0, 1, 3, 4, 5, 6],
        ),
    ],
)
def test_attachment_starts(pages: list[str], expected: list[int]) -> None:
    assert attachment_starts(pages) == expected


def test_segments_split_until_next_start() -> None:
    assert segments([2, 5], 8) == [range(2, 5), range(5, 8)]
    assert segments([], 3) == []


def test_text_features_counts_form_markers() -> None:
    text = "WNIOSEK\nImię ..............\n□ tak □ nie\n\uf06f inne\nczytelny podpis"
    f = text_features(text)
    assert (f.leaders, f.boxes, f.signature) == (1, 3, True)
    assert f.form_words == ["WNIOSEK"]


@pytest.mark.parametrize(
    ("feats", "expected"),
    [
        (Features(pages=1, text_chars=900, leaders=12), True),
        (Features(pages=1, text_chars=900, paths=60), True),
        (Features(pages=2, text_chars=4000, leaders=1, paths=60), False),
        (Features(pages=1, text_chars=900, signature=True, form_words=["WZÓR"]), True),
        (Features(pages=3, text_chars=150, images=3), True),
        (Features(pages=1, text_chars=0), False),
    ],
)
def test_is_form_candidate(feats: Features, expected: bool) -> None:
    assert feats.is_form_candidate is expected


def test_is_raster_needs_images_and_little_text() -> None:
    assert Features(pages=2, text_chars=120, images=2).is_raster
    assert not Features(pages=2, text_chars=120).is_raster
    assert not Features(pages=1, text_chars=2000, images=1).is_raster


def test_non_form_titles_filtered() -> None:
    assert NON_FORM_TITLE.search("w sprawie wzoru legitymacji służbowej")
    assert not NON_FORM_TITLE.search("w sprawie wzoru wniosku o wydanie zezwolenia")


def test_fix_legacy_text_repairs_old_journal_glyphs() -> None:
    old = "Za\u220f\u00e0czniki do rozporz\u00e0\ufffedzenia\nNale\u02ddy wype\u220fni\u00e7, okre\u00cala si\u00b4, pa\u0192stwa"
    assert (
        fix_legacy_text(old)
        == "Załączniki do rozporządzenia\nNależy wypełnić, określa się, państwa"
    )
    assert attachment_starts([fix_legacy_text(old)]) == [0]


def test_fix_legacy_text_leaves_correct_text_alone() -> None:
    text = "Voilà: Załącznik nr 1 – ´"
    assert fix_legacy_text(text) == text
