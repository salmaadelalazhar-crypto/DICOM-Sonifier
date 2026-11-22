"""Shortcuts use the English letters only. Run: python -m pytest tests"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keys import action_for  # noqa: E402


def test_space_is_play_pause():
    assert action_for("space", " ") == "play"


def test_r_and_w_work_with_and_without_caps_lock():
    assert action_for("r", "r") == "replay"
    assert action_for("R", "R") == "replay"   # Caps Lock / Shift
    assert action_for("w", "w") == "where"
    assert action_for("W", "W") == "where"


def test_ctrl_o_open_and_ctrl_s_export():
    assert action_for("o", "\x0f", ctrl=True) == "open"
    assert action_for("s", "\x13", ctrl=True) == "export"
    assert action_for("O", "\x0f", ctrl=True) == "open"   # Caps Lock


def test_arabic_letters_are_not_shortcuts():
    assert action_for("Arabic_qaf", "ق") is None
    assert action_for("??", "ص") is None
    assert action_for("Arabic_khah", "خ", ctrl=True) is None


def test_plain_o_and_s_do_nothing_and_ctrl_r_does_nothing():
    assert action_for("o", "o") is None
    assert action_for("s", "s") is None
    assert action_for("r", "\x12", ctrl=True) is None


def test_navigation_keys():
    assert action_for("Right") == "next"
    assert action_for("Left") == "prev"
    assert action_for("Down") == "part_next"
    assert action_for("Up") == "part_prev"
    assert action_for("Next") == "slice_next"
    assert action_for("Prior") == "slice_prev"
    assert action_for("Escape") == "cancel"
