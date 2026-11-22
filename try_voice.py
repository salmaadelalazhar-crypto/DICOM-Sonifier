"""Try the spoken voice: python try_voice.py
Says a test sentence in Arabic and English with gTTS (internet), then with
the Windows built-in voice (offline), and prints what worked."""
import threading
import time

from speech import Speaker

TESTS = [
    ("ar", "مرحبًا، هذا اختبار الصوت. الشريحة 1 من 10. الصف 5 من 64."),
    ("en", "Hello, this is a voice test. Slice 1 of 10. Row 5 of 64."),
]


def run(engine):
    for lang, text in TESTS:
        done = threading.Event()
        problems = []
        sp = Speaker(lang, engine=engine, on_error=problems.append, on_notice=problems.append)
        t0 = time.time()
        sp.say(text, on_done=done.set)
        done.wait(60)
        result = "OK" if not problems else f"FAILED: {problems[0]}"
        print(f"[{engine}] {lang}: {result} ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    print("1) Google voice (gTTS, needs internet)")
    run("gtts")
    print("2) Windows built-in voice (offline)")
    run("windows")
