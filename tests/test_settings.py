import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings import clean, parse_number, DEFAULTS  # noqa: E402


def test_accepts_arabic_digits_and_comma():
    assert parse_number("١٥") == 15
    assert parse_number("-١٠٠٠") == -1000
    assert parse_number("2,5") == 2.5
    assert parse_number("٢٫٥") == 2.5


def test_rejects_letters_and_empty():
    assert parse_number("abc") is None
    assert parse_number("") is None
    assert parse_number("nan") is None


def test_limits():
    p = clean(dict(DEFAULTS, fmin=5, fmax=99999, tone_ms=0, step=0, parts=0))
    assert p["fmin"] == 20 and p["fmax"] == 20000 and p["tone_ms"] == 1 and p["step"] == 1 and p["parts"] == 1
