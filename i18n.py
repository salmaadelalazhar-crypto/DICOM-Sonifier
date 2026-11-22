"""Language detection: Arabic if the OS language is Arabic, otherwise English."""
import locale
import os
import sys

STRINGS = {
    "en": {
        "title": "DICOM Sonifier",
        "open": "Open DICOM or ZIP file (Ctrl+O)",
        "file_types": "DICOM or ZIP files",
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
        "no_file": "No file loaded. Press Ctrl+O to open a DICOM file or a ZIP file of DICOM files.",
        "loaded": "Loaded: {name}. {rows} rows, {slices} slices.",
        "status": "Slice {s} of {ns}. Row {r} of {nr}.",
        "playing": "Playing",
        "paused": "Paused",
        "end": "End of slice reached.",
        "saved": "Saved: {path}",
        "error": "Error",
        "audio_err": "Audio device not available: {e}",
        "speech_err": "Spoken announcements are not working on this computer: {e}",
        "speech_offline": "No internet for the Google voice, using the Windows voice instead.",
        "invalid": "Invalid value in \u201c{field}\u201d. Kept {value}.",
        "applied": "Settings applied.",
        "loading_pct": "Loading {pct}%",
        "loading_one": "Loading...",
        "busy": "Please wait, the program is busy.",
        "exporting": "Exporting: about {minutes} minutes of sound, {mb} MB. Press Escape to cancel.",
        "export_pct": "Exporting {pct}%",
        "export_cancel": "Export cancelled.",
        "skipped": "Files skipped inside the ZIP: {n}, because they are not scan images or are damaged.",
        "zip_bad": "This ZIP file is damaged and cannot be opened.",
        "zip_empty": "This ZIP file has no DICOM scan images inside.",
        "zip_password": "This ZIP file is protected with a password. Please use a ZIP without a password.",
        "zip_too_big": "This ZIP file is too big to open (more than 10000 files or 8 GB).",
        "not_dicom": "This file is not a DICOM scan image. Please choose a .dcm file or a .zip file.",
        "help": "Tab moves between buttons and Enter presses the selected button. Space is only for play/pause. Escape cancels an export. Open a .dcm file, or a .zip file with one .dcm file per slice. Letter shortcuts need the English keyboard: Ctrl+O open, Space play/pause, Left/Right previous/next row, Up/Down previous/next part, R repeat row, W where am I, Home/End first/last row, Page Up/Down change slice, Ctrl+S export WAV.",
    },
    "ar": {
        "title": "محوّل الأشعة إلى صوت",
        "open": "فتح ملف أشعة أو ملف مضغوط (Ctrl+O)",
        "file_types": "ملفات أشعة أو ملفات مضغوطة",
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
        "no_file": "لا يوجد ملف. اضغط Ctrl+O لفتح ملف أشعة أو ملف مضغوط فيه ملفات أشعة.",
        "loaded": "تم التحميل: {name}. {rows} صف، {slices} شريحة.",
        "status": "الشريحة {s} من {ns}. الصف {r} من {nr}.",
        "playing": "جارٍ التشغيل",
        "paused": "متوقف",
        "end": "انتهت الشريحة.",
        "saved": "تم الحفظ: {path}",
        "error": "خطأ",
        "audio_err": "جهاز الصوت غير متاح: {e}",
        "speech_err": "الصوت المنطوق لا يعمل على هذا الجهاز: {e}",
        "speech_offline": "لا يوجد إنترنت لصوت جوجل، سيُستخدم صوت ويندوز بدلًا منه.",
        "invalid": "قيمة غير صحيحة في «{field}». تم الإبقاء على {value}.",
        "applied": "تم تطبيق الإعدادات.",
        "loading_pct": "جارٍ التحميل {pct}٪",
        "loading_one": "جارٍ التحميل...",
        "busy": "انتظر قليلًا، البرنامج مشغول.",
        "exporting": "جارٍ التصدير: حوالي {minutes} دقيقة صوت، {mb} ميجابايت. اضغط Escape للإلغاء.",
        "export_pct": "جارٍ التصدير {pct}٪",
        "export_cancel": "تم إلغاء التصدير.",
        "skipped": "عدد الملفات التي تم تخطيها داخل الملف المضغوط: {n}، لأنها ليست صور أشعة أو تالفة.",
        "zip_bad": "هذا الملف المضغوط تالف ولا يمكن فتحه.",
        "zip_empty": "هذا الملف المضغوط لا يحتوي على صور أشعة DICOM.",
        "zip_password": "هذا الملف المضغوط محمي بكلمة سر. استخدم ملفًا مضغوطًا بدون كلمة سر.",
        "zip_too_big": "هذا الملف المضغوط كبير جدًا (أكثر من 10000 ملف أو 8 جيجابايت).",
        "not_dicom": "هذا الملف ليس صورة أشعة DICOM. اختر ملف ‎.dcm أو ملفًا مضغوطًا ‎.zip.",
        "help": "Tab للتنقل بين الأزرار وEnter لتفعيل الزر المحدد. المسافة للتشغيل والإيقاف فقط. Escape لإلغاء التصدير. افتح ملف ‎.dcm أو ملفًا مضغوطًا ‎.zip فيه ملف ‎.dcm لكل شريحة. اختصارات الحروف تحتاج الكيبورد الإنجليزي: Ctrl+O فتح، المسافة تشغيل/إيقاف، يمين/يسار الصف التالي/السابق، أعلى/أسفل الجزء السابق/التالي، R إعادة الصف، W أين أنا، Home/End أول/آخر صف، Page Up/Down تغيير الشريحة، Ctrl+S تصدير.",
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
