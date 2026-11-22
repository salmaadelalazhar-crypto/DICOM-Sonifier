"""Settings defaults and number parsing (accepts Arabic-Indic digits)."""
import math

DEFAULTS = {"fmin": 30.0, "fmax": 14000.0, "vmin": -1000.0, "vmax": 3000.0,
            "tone_ms": 15.0, "step": 2.0, "parts": 10.0}
ORDER = ["fmin", "fmax", "vmin", "vmax", "tone_ms", "step", "parts"]

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬−", "01234567890123456789.,-")


def parse_number(text):
    """Return a float, or None when the text is not a valid number."""
    s = str(text).strip().translate(_DIGITS).replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def clean(p):
    """Keep values in a safe range."""
    p = dict(p)
    p["fmin"] = max(20.0, p["fmin"])
    p["fmax"] = max(p["fmin"] + 1, min(20000.0, p["fmax"]))
    p["tone_ms"] = max(1.0, p["tone_ms"])
    p["step"] = max(1, int(p["step"]))
    p["parts"] = max(1, int(p["parts"]))
    return p


def fmt(v):
    return f"{v:g}"
