"""Spoken announcements (Windows SAPI via pyttsx3). Silently disabled if unavailable."""
import threading


class Speaker:
    def __init__(self, lang):
        self.lang = lang
        self.lock = threading.Lock()

    def _speak(self, text):
        with self.lock:
            try:
                import pyttsx3
                eng = pyttsx3.init()
                for v in eng.getProperty("voices"):
                    name = (v.name + " " + str(v.languages) + " " + v.id).lower()
                    if (self.lang == "ar" and ("arab" in name or "ar-" in name or "naayf" in name or "hoda" in name)) or \
                       (self.lang == "en" and ("english" in name or "en-" in name or "zira" in name or "david" in name)):
                        eng.setProperty("voice", v.id)
                        break
                eng.setProperty("rate", 190)
                eng.say(text)
                eng.runAndWait()
                eng.stop()
            except Exception:
                pass

    def say(self, text, block=False):
        if block:
            self._speak(text)
        else:
            threading.Thread(target=self._speak, args=(text,), daemon=True).start()
