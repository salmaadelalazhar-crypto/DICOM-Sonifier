"""Speech engine behaviour, without internet or a sound card."""
import os
import sys
import threading
import time
import types

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import speech  # noqa: E402

played = []


class FakeStream:
    def __init__(self, samplerate, channels, dtype):
        self.sr = samplerate

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def write(self, chunk):
        played.append(len(chunk))
        time.sleep(len(chunk) / self.sr)  # real-time, like a sound card


sys.modules["sounddevice"] = types.SimpleNamespace(OutputStream=FakeStream)


def fake_gtts_audio(calls):
    def audio(self, text):
        calls.append(text)
        return np.ones(2400, np.float32) * 0.5, 24000
    return audio


def wait_done(sp, text):
    done = threading.Event()
    sp.say(text, on_done=done.set)
    assert done.wait(5)


def test_google_voice_is_used_first(monkeypatch):
    calls, windows = [], []
    monkeypatch.setattr(speech.Speaker, "_gtts_audio", fake_gtts_audio(calls))
    monkeypatch.setattr(speech.Speaker, "_windows_say", lambda self, t: windows.append(t))
    played.clear()
    wait_done(speech.Speaker("ar"), "الصف 1")
    assert calls == ["الصف 1"] and windows == [] and sum(played) == 2400


def test_falls_back_to_windows_voice_without_internet(monkeypatch):
    windows, notices = [], []

    def offline(self, text):
        raise OSError("no internet")
    monkeypatch.setattr(speech.Speaker, "_gtts_audio", offline)
    monkeypatch.setattr(speech.Speaker, "_windows_say", lambda self, t: windows.append(t))
    sp = speech.Speaker("en", on_notice=notices.append)
    wait_done(sp, "Row 1")
    wait_done(sp, "Row 2")
    assert windows == ["Row 1", "Row 2"] and len(notices) == 1  # told once only


def test_reports_error_when_no_voice_works(monkeypatch):
    errors = []

    def fail(self, text):
        raise OSError("broken")
    monkeypatch.setattr(speech.Speaker, "_gtts_audio", fail)
    monkeypatch.setattr(speech.Speaker, "_windows_say", fail)
    sp = speech.Speaker("en", on_error=errors.append)
    wait_done(sp, "a")
    wait_done(sp, "b")
    assert len(errors) == 1


def test_sentences_are_cached(monkeypatch):
    import io
    calls = []

    class FakeTTS:
        def __init__(self, text, lang):
            calls.append((text, lang))

        def write_to_fp(self, fp):
            import soundfile as sf
            sf.write(fp, np.r_[np.zeros(2400), np.ones(2400) * 0.5, np.zeros(2400)].astype(np.float32),
                     24000, format="WAV")
    monkeypatch.setattr(speech, "gtts", types.SimpleNamespace(gTTS=FakeTTS))
    sp = speech.Speaker("ar")
    a = sp._gtts_audio("مرحبا")
    b = sp._gtts_audio("مرحبا")
    assert calls == [("مرحبا", "ar")] and a[0] is b[0]
    assert len(a[0]) < 2400 + 2 * 24000 * 0.03 + 2  # silence trimmed


def test_new_announcement_interrupts_current(monkeypatch):
    monkeypatch.setattr(speech.Speaker, "_gtts_audio",
                        lambda self, t: (np.ones(24000 * (5 if t == "long sentence" else 1), np.float32), 24000))
    played.clear()
    sp = speech.Speaker("en")
    first = threading.Event()
    sp.say("long sentence", on_done=first.set)
    time.sleep(0.2)
    t0 = time.time()
    wait_done(sp, "newer")
    assert first.is_set() and time.time() - t0 < 2.5  # did not wait for the 5-second sentence
    assert sum(played) < 24000 * 2
