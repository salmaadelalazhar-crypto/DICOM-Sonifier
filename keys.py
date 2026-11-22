"""Keyboard shortcuts. Letter shortcuts use the English letters (R, W, Ctrl+O, Ctrl+S).

They work with Caps Lock on, and on an Arabic Windows as long as the keyboard
is switched to English. Letters typed with the Arabic keyboard layout are
not shortcuts.
"""

# Keys that are the same on every layout.
SPECIAL = {
    "space": "play",
    "left": "prev", "kp_left": "prev",
    "right": "next", "kp_right": "next",
    "up": "part_prev", "kp_up": "part_prev",
    "down": "part_next", "kp_down": "part_next",
    "home": "first", "kp_home": "first",
    "end": "last", "kp_end": "last",
    "prior": "slice_prev", "kp_prior": "slice_prev", "page_up": "slice_prev",
    "next": "slice_next", "kp_next": "slice_next", "page_down": "slice_next",
    "escape": "cancel",
}

# Letter shortcuts without and with Ctrl.
PLAIN = {"r": "replay", "w": "where"}
CTRL = {"o": "open", "s": "export"}

# Actions that must not fire while the user is typing in a settings field,
# because these keys move the text cursor or type characters there.
TYPING_KEYS = {"prev", "next", "first", "last", "replay", "where"}


def english_letter(keysym="", char=""):
    """Return the English letter of the key press (lower case), or None."""
    ks = (keysym or "").lower()
    if len(ks) == 1 and "a" <= ks <= "z":
        return ks
    c = (char or "").lower()
    if len(c) == 1:
        if "a" <= c <= "z":
            return c
        # Ctrl+letter produces a control character (Ctrl+O -> \x0f).
        if 1 <= ord(c) <= 26:
            return chr(ord(c) + 96)
    return None


def action_for(keysym="", char="", ctrl=False):
    """Map a key press to an action name, or None if it is not a shortcut."""
    ks = (keysym or "").lower()
    if ks in SPECIAL:
        return None if ctrl else SPECIAL[ks]
    letter = english_letter(keysym, char)
    if letter is None:
        return None
    return (CTRL if ctrl else PLAIN).get(letter)
