# DICOM Sonifier (Desktop)
Keyboard-only desktop app that turns DICOM images into sound, row by row.
Low density = low pitch, high density = high pitch (30 Hz - 14 kHz, log scale, 48 kHz / 24-bit export).
Language follows the OS: Arabic if Windows is Arabic, otherwise English.

Run locally: `pip install -r requirements.txt && python main.py`
Build: push to GitHub; the workflow builds the Windows exe, runs it for 30 s, and uploads it as an artifact.
