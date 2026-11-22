"""Spoken announcements.

Main voice: gTTS (Google Text-to-Speech) - natural Arabic and English voices,
installed with a simple `pip install gTTS`. It needs an internet connection.
Without internet, the Windows built-in voices (pyttsx3) are used instead.

All speech runs on ONE background thread, so the window never freezes.
A new announcement interrupts the one being spoken, so fast key presses
always hear the latest position. Sentences already spoken are kept in
memory and replay instantly.
"""
import io
import queue
import threading
from collections import OrderedDict

import numpy as np

try:  # imported here (not only inside a function) so the Windows .exe build includes it
    import gtts
except ImportError:
    gtts = None

CHUNK_SECONDS = 0.05
CACHE_SIZE = 300


class Speaker:
    def __init__(self, lang, on_error=None, on_notice=None, engine="auto"):
        """engine: "auto" (gTTS, then Windows voices), "gtts", or "windows"."""
        self.lang = lang
        self.on_error = on_error
        self.on_notice = on_notice
        self.engine = engine
        self.q = queue.Queue()
        self.cache = OrderedDict()
        self.voice_id = None
        self.offline_noticed = False
        self.failures = 0
        self.disabled = False
        threading.Thread(target=self._worker, daemon=True).start()

    def say(self, text, on_done=None):
        """Queue text to be spoken. on_done runs (on the speech thread) when finished or interrupted."""
        self.q.put((text, on_done))

    # ----- speech thread -----
    def _worker(self):
        self._prepare_com()
        while True:
            items = [self.q.get()]
            while True:  # skip announcements that are already out of date
                try:
                    items.append(self.q.get_nowait())
                except queue.Empty:
                    break
            for _, cb in items[:-1]:
                self._call(cb)
            text, cb = items[-1]
            self._speak(text)
            self._call(cb)

    @staticmethod
    def _call(cb):
        if cb:
            try:
                cb()
            except Exception:
                pass

    def _speak(self, text):
        if self.disabled or not text:
            return
        errors = []
        if self.engine in ("auto", "gtts"):
            try:
                self._play(*self._gtts_audio(text))
                self.failures = 0
                return
            except Exception as e:
                errors.append(e)
                if self.engine == "auto" and not self.offline_noticed:
                    self.offline_noticed = True
                    self._call(self.on_notice and (lambda: self.on_notice(e)))
        if self.engine in ("auto", "windows"):
            try:
                self._windows_say(text)
                self.failures = 0
                return
            except Exception as e:
                errors.append(e)
        self.failures += 1
        if self.failures >= 2:
            self.disabled = True
            self._call(self.on_error and (lambda: self.on_error(errors[-1])))

    # ----- gTTS -----
    def _gtts_audio(self, text):
        key = (self.lang, text)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        if gtts is None:
            raise RuntimeError("gTTS is not installed (pip install gTTS)")
        import soundfile as sf
        buf = io.BytesIO()
        gtts.gTTS(text, lang="ar" if self.lang == "ar" else "en").write_to_fp(buf)
        buf.seek(0)
        data, sr = sf.read(buf, dtype="float32")  # MP3 decoding needs soundfile >= 0.12
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = trim_silence(data, sr)
        self.cache[key] = (data, sr)
        if len(self.cache) > CACHE_SIZE:
            self.cache.popitem(last=False)
        return data, sr

    def _play(self, data, sr):
        """Play on its own audio stream (separate from the image tones), stopping early
        if a newer announcement arrives."""
        import sounddevice as sd
        step = max(1, int(sr * CHUNK_SECONDS))
        with sd.OutputStream(samplerate=sr, channels=1, dtype="float32") as stream:
            for i in range(0, len(data), step):
                if not self.q.empty():
                    return
                stream.write(data[i:i + step].reshape(-1, 1))

    # ----- Windows voices (offline fallback) -----
    @staticmethod
    def _prepare_com():
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass

    def _pick_voice(self, eng):
        for v in eng.getProperty("voices"):
            name = (str(v.name) + " " + str(v.languages) + " " + str(v.id)).lower()
            if (self.lang == "ar" and ("arab" in name or "ar-" in name or "naayf" in name or "hoda" in name)) or \
               (self.lang == "en" and ("english" in name or "en-" in name or "zira" in name or "david" in name)):
                return v.id
        return ""

    def _windows_say(self, text):
        import pyttsx3
        eng = pyttsx3.init()
        if self.voice_id is None:
            self.voice_id = self._pick_voice(eng)
        if self.voice_id:
            eng.setProperty("voice", self.voice_id)
        eng.setProperty("rate", 190)
        eng.say(text)
        eng.runAndWait()
        eng.stop()
        del eng


def trim_silence(data, sr, threshold=0.01, keep_seconds=0.03):
    """Cut the silence gTTS adds before and after a sentence, so speech starts sooner."""
    loud = np.flatnonzero(np.abs(data) > threshold)
    if loud.size == 0:
        return data
    pad = int(sr * keep_seconds)
    return data[max(0, loud[0] - pad):min(len(data), loud[-1] + pad)]
