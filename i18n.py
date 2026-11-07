"""Language detection: Arabic if the OS language is Arabic, otherwise English."""
import locale
import os
import sys

STRINGS = {
    "en": {
        "title": "DICOM Sonifier",
        "open": "Open DICOM file (Ctrl+O)",
        "play": "Play / Pause (Space)",
        "prev": "Previous row (Left)",
        "next": "Next row (Right)",
        "back10": "Previous part (Up)",
        "fwd10": "Next part (Down)",
        "parts": "Number of parts per slice",
        "replay": "Repeat current row (R)",
        "where": "Where am I? (W)",
        "part_status": "Part {p} of {np}.",
        "prev_slice": "Previous slice (Page Up)",
        "next_slice": "Next slice (Page Down)",
        "export": "Export WAV (Ctrl+S)",
        "settings": "Settings",
        "fmin": "Lowest frequency (Hz)",
        "fmax": "Highest frequency (Hz)",
        "vmin": "Lowest density",
        "vmax": "Highest density",
        "tone_ms": "Tone duration per pixel (ms)",
        "step": "Pixel step",
        "apply": "Apply",
        "no_file": "No file loaded. Press Ctrl+O to open a DICOM file.",
        "loaded": "Loaded: {name}. {rows} rows, {slices} slices.",
        "status": "Slice {s} of {ns}. Row {r} of {nr}.",
        "playing": "Playing",
        "paused": "Paused",
        "end": "End of slice reached.",
        "saved": "Saved: {path}",
        "error": "Error",
        "audio_err": "Audio device not available: {e}",
        "help": "Keys: Ctrl+O open, Space play/pause, Left/Right previous/next row, Up/Down previous/next part, R repeat row, W where am I, Home/End first/last row, Page Up/Down change slice, Ctrl+S export WAV.",
    },
    "ar": {
        "title": "محوّل الأشعة إلى صوت",
        "open": "فتح ملف أشعة (Ctrl+O)",
        "play": "تشغيل / إيقاف (مسافة)",
        "prev": "الصف السابق (يسار)",
        "next": "الصف التالي (يمين)",
        "back10": "الجزء السابق (أعلى)",
        "fwd10": "الجزء التالي (أسفل)",
        "parts": "عدد أجزاء الشريحة",
        "replay": "إعادة الصف الحالي (R)",
        "where": "أين أنا؟ (W)",
        "part_status": "الجزء {p} من {np}.",
        "prev_slice": "الشريحة السابقة (Page Up)",
        "next_slice": "الشريحة التالية (Page Down)",
        "export": "تصدير WAV (Ctrl+S)",
        "settings": "الإعدادات",
        "fmin": "أدنى تردد (هرتز)",
        "fmax": "أعلى تردد (هرتز)",
        "vmin": "أدنى كثافة",
        "vmax": "أعلى كثافة",
        "tone_ms": "مدة نغمة كل نقطة (مللي ثانية)",
        "step": "خطوة النقاط",
        "apply": "تطبيق",
        "no_file": "لا يوجد ملف. اضغط Ctrl+O لفتح ملف أشعة.",
        "loaded": "تم التحميل: {name}. {rows} صف، {slices} شريحة.",
        "status": "الشريحة {s} من {ns}. الصف {r} من {nr}.",
        "playing": "جارٍ التشغيل",
        "paused": "متوقف",
        "end": "انتهت الشريحة.",
        "saved": "تم الحفظ: {path}",
        "error": "خطأ",
        "audio_err": "جهاز الصوت غير متاح: {e}",
        "help": "الأزرار: Ctrl+O فتح، المسافة تشغيل/إيقاف، يمين/يسار الصف التالي/السابق، أعلى/أسفل الجزء السابق/التالي، R إعادة الصف، W أين أنا، Home/End أول/آخر صف، Page Up/Down تغيير الشريحة، Ctrl+S تصدير.",
    },
}


def detect_language() -> str:
    codes = []
    if sys.platform.startswith("win"):
        try:
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if (lang_id & 0x3FF) == 0x01:  # LANG_ARABIC primary id
                return "ar"
            codes.append(locale.windows_locale.get(lang_id, ""))
        except Exception:
            pass
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        codes.append(os.environ.get(var, ""))
    try:
        codes.append(locale.getlocale()[0] or "")
    except Exception:
        pass
    for c in codes:
        if c and c.lower().startswith(("ar", "arabic")):
            return "ar"
    return "en"


LANG = detect_language()


def t(key: str, **kw) -> str:
    return STRINGS[LANG][key].format(**kw)
