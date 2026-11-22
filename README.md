# DICOM Sonifier (Desktop)
Keyboard-only desktop app that turns DICOM images into sound, row by row.
Low density = low pitch, high density = high pitch (30 Hz - 14 kHz, log scale, 48 kHz / 24-bit export).
Language follows the OS: Arabic if Windows is Arabic, otherwise English.

Run locally: `pip install -r requirements.txt && python main.py`
Build: push to GitHub; the workflow builds the Windows exe, runs it for 30 s, and uploads it as an artifact.

## Keyboard
- Tab moves between buttons, **Enter** presses the selected button. **Space** is only play/pause, wherever the focus is.
- Letter shortcuts are the English letters (R, W, Ctrl+O, Ctrl+S); switch the keyboard to English. They also work with Caps Lock.
- In a settings field, arrows/Home/End edit the text, Enter applies, Arabic digits are accepted.
- Escape cancels a WAV export.

## Opening files
Two kinds of file are accepted:
- **.dcm** - one DICOM file. One slice, or several slices if the file holds several frames.
- **.zip** - a ZIP file with many DICOM files, one per slice. The program reads them straight from the ZIP
  (nothing is unpacked to disk), skips anything that is not a scan image, and sorts the slices by their
  position in the body (then by image number, then by file name). It starts on slice 1.

The program only reads the file you choose; it never looks at other files in the same folder.
Loading and WAV export run in the background with spoken progress, so the window never freezes.

Tests: `pip install pytest && python -m pytest tests`

## Voice
Spoken announcements use **gTTS** (Google voice, natural Arabic and English, needs internet).
Without internet the Windows built-in voice is used automatically. Try both with `python try_voice.py`.
