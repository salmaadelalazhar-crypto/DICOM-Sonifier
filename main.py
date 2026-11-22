"""DICOM Sonifier - desktop app for blind users. Keyboard-driven, row-by-row playback."""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np

from speech import Speaker

from i18n import LANG, t
import keys
import settings
import sonify


class App:
    def __init__(self, root):
        self.root = root
        root.title(t("title"))
        root.geometry("640x560")
        self.vol = None
        self.slice = 0
        self.row = 0
        self.playing = False
        self.play_id = 0
        self.nav_id = 0
        self.sd = None
        self.loading = False
        self.export_cancel = None  # threading.Event while an export is running
        self.good = dict(settings.DEFAULTS)  # last valid value of each setting
        # Background threads never touch the window directly; they post here.
        self.ui_q = queue.Queue()
        self.speaker = Speaker(LANG,
                               on_error=lambda e: self.post(self.status.set, t("speech_err", e=e)),
                               on_notice=lambda e: self.post(self.status.set, t("speech_offline")))
        anchor = "e" if LANG == "ar" else "w"
        side = "right" if LANG == "ar" else "left"

        self.status = tk.StringVar(value=t("no_file"))
        tk.Label(root, textvariable=self.status, font=("Segoe UI", 14), wraplength=600,
                 justify=side, anchor=anchor).pack(fill="x", padx=12, pady=10)

        # Buttons are pressed with Enter. Space never presses a button: it is
        # reserved for play/pause, wherever the focus is.
        root.unbind_class("TButton", "<Key-space>")
        for seq in ("<Return>", "<KP_Enter>"):
            root.bind_class("TButton", seq, self._press_button)

        btns = ttk.Frame(root)
        btns.pack(fill="x", padx=12)
        for key, cmd in [("open", self.open_file), ("play", self.toggle_play),
                         ("prev", lambda: self.move(-1)), ("next", lambda: self.move(1)),
                         ("back10", lambda: self.move_part(-1)), ("fwd10", lambda: self.move_part(1)),
                         ("replay", self.play_row_once), ("where", self.announce),
                         ("prev_slice", lambda: self.change_slice(-1)),
                         ("next_slice", lambda: self.change_slice(1)), ("export", self.export)]:
            ttk.Button(btns, text=t(key), command=cmd).pack(fill="x", pady=2)

        box = ttk.LabelFrame(root, text=t("settings"))
        box.pack(fill="x", padx=12, pady=10)
        self.vars = {}
        # In a settings field: Space = play/pause, Enter = apply. Arrows,
        # Home/End and letters keep their normal typing behaviour.
        root.bind_class("SettingsField", "<space>", lambda e: (self.toggle_play(), "break")[1])
        root.bind_class("SettingsField", "<Return>", lambda e: (self.apply(), "break")[1])
        root.bind_class("SettingsField", "<KP_Enter>", lambda e: (self.apply(), "break")[1])
        for i, k in enumerate(settings.ORDER):
            ttk.Label(box, text=t(k)).grid(row=i, column=1 if LANG == "ar" else 0, sticky=anchor, padx=4)
            var = tk.StringVar(value=settings.fmt(settings.DEFAULTS[k]))
            entry = ttk.Entry(box, textvariable=var, width=10)
            entry.bindtags(("SettingsField",) + entry.bindtags())
            entry.grid(row=i, column=0 if LANG == "ar" else 1, padx=4, pady=1)
            self.vars[k] = var
        ttk.Button(box, text=t("apply"), command=self.apply).grid(row=len(settings.ORDER), column=0, columnspan=2, pady=4)

        ttk.Label(root, text=t("help"), wraplength=600, justify=side).pack(fill="x", padx=12)

        # One handler for every shortcut. Letter shortcuts are the English
        # letters (R, W, Ctrl+O, Ctrl+S) and also work with Caps Lock.
        root.bind("<KeyPress>", self.on_key)
        self.actions = {
            "open": self.open_file, "play": self.toggle_play,
            "prev": lambda: self.move(-1), "next": lambda: self.move(1),
            "part_prev": lambda: self.move_part(-1), "part_next": lambda: self.move_part(1),
            "replay": self.play_row_once, "where": self.announce,
            "first": lambda: self.goto(0), "last": lambda: self.goto(10**9),
            "slice_prev": lambda: self.change_slice(-1), "slice_next": lambda: self.change_slice(1),
            "export": self.export, "cancel": self.cancel,
        }
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(30, self._pump)

        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            self.load(sys.argv[1])

    # ---------- keyboard ----------
    def _press_button(self, event):
        try:
            self.root.tk.call("ttk::button::activate", str(event.widget))
        except tk.TclError:
            event.widget.invoke()
        return "break"

    def on_key(self, event):
        ctrl = bool(event.state & 0x0004)
        action = keys.action_for(event.keysym, event.char, ctrl)
        if action is None:
            return None
        focus = self.root.focus_get()
        if isinstance(focus, tk.Entry) and action in keys.TYPING_KEYS:
            return None  # let the user edit the settings field normally
        self.actions[action]()
        return "break"

    # ---------- thread-safe UI updates ----------
    def post(self, fn, *args):
        self.ui_q.put((fn, args))

    def _pump(self):
        try:
            while True:
                fn, args = self.ui_q.get_nowait()
                try:
                    fn(*args)
                except Exception as e:
                    self.status.set(str(e))
        except queue.Empty:
            pass
        try:
            self.root.after(30, self._pump)
        except tk.TclError:
            pass

    # ---------- settings ----------
    def params(self):
        """Current settings. A field with an invalid value keeps its last valid value."""
        p = {}
        for k, var in self.vars.items():
            v = settings.parse_number(var.get())
            if v is not None:
                self.good[k] = v
            p[k] = self.good[k]
        return settings.clean(p)

    def apply(self):
        bad = []
        for k in settings.ORDER:
            v = settings.parse_number(self.vars[k].get())
            if v is None:
                bad.append(k)
                self.vars[k].set(settings.fmt(self.good[k]))
            else:
                self.good[k] = v
        if bad:
            msg = " ".join(t("invalid", field=t(k), value=settings.fmt(self.good[k])) for k in bad)
        else:
            msg = t("applied")
        self.status.set(msg)
        self.speaker.say(msg)

    def set_setting(self, k, v):
        self.good[k] = float(v)
        self.vars[k].set(f"{v:.0f}")

    # ---------- file ----------
    def open_file(self):
        if self.loading or self.export_cancel is not None:
            self.speaker.say(t("busy"))
            return
        path = filedialog.askopenfilename(
            filetypes=[(t("file_types"), "*.dcm *.dicom *.zip"), ("DICOM", "*.dcm *.dicom"), ("ZIP", "*.zip")])
        if path:
            self.load(path)

    def load(self, path):
        """Load the chosen file in the background: a .dcm file (one or more slices)
        or a .zip holding many .dcm files, one per slice. Other files in the
        same folder are never looked at."""
        self.stop()
        self.loading = True
        self.status.set(t("loading_one"))
        self.speaker.say(t("loading_one"))
        threading.Thread(target=self._load_worker, args=(path,), daemon=True).start()

    def _load_worker(self, path):
        last = [-1]

        def progress(done, total):
            pct = done * 100 // total
            if pct // 10 != last[0]:
                last[0] = pct // 10
                self.post(self.status.set, t("loading_pct", pct=pct))
        try:
            vol, skipped = sonify.load_file(path, progress)
            is_zip = path.lower().endswith(".zip")
            start = 0 if is_zip else vol.shape[0] // 2  # a ZIP starts at its first slice
            lo, hi = sonify.density_range(vol)
            self.post(self._loaded, path, vol, start, lo, hi, skipped)
        except sonify.LoadError as e:
            self.post(self._load_failed, t(e.key))
        except Exception as e:
            self.post(self._load_failed, str(e))

    def _loaded(self, path, vol, start, lo, hi, skipped=0):
        self.loading = False
        self.vol = vol
        self.slice = start
        self.row = 0
        self.set_setting("vmin", lo)
        self.set_setting("vmax", hi)
        msg = t("loaded", name=os.path.basename(path), rows=vol.shape[1], slices=vol.shape[0])
        if skipped:
            msg += " " + t("skipped", n=skipped)
        self.status.set(msg)
        self.speaker.say(msg)

    def _load_failed(self, msg):
        self.loading = False
        self.status.set(t("no_file") if self.vol is None else self.position_text())
        self.speaker.say(msg)
        messagebox.showerror(t("error"), msg)

    # ---------- navigation ----------
    def update_status(self, extra=""):
        if self.vol is None:
            return
        self.status.set(f"{self.position_text()} {extra}".strip())

    # ---------- parts ----------
    def part_bounds(self):
        """Split the slice rows into N equal parts; returns list of start rows."""
        n = min(self.params()["parts"], self.vol.shape[1])
        return [int(round(i * self.vol.shape[1] / n)) for i in range(n)]

    def current_part(self):
        starts = self.part_bounds()
        return max(i for i, st in enumerate(starts) if st <= self.row), len(starts)

    def position_text(self):
        p, np_ = self.current_part()
        return (t("status", s=self.slice + 1, ns=self.vol.shape[0], r=self.row + 1, nr=self.vol.shape[1])
                + " " + t("part_status", p=p + 1, np=np_))

    def announce(self):
        if self.vol is not None:
            self.speaker.say(self.position_text())

    def move_part(self, d):
        if self.vol is None:
            return
        starts = self.part_bounds()
        p, n = self.current_part()
        p = int(np.clip(p + d, 0, n - 1))
        self.goto(starts[p], speak=t("part_status", p=p + 1, np=n))

    def goto(self, r, speak=None):
        """Move to a row. If there is something to say, the row sound starts
        after the sentence ends - without freezing the window meanwhile."""
        if self.vol is None:
            return
        self.row = int(np.clip(r, 0, self.vol.shape[1] - 1))
        was = self.playing
        self.stop(update=False)
        self.nav_id += 1
        my_nav = self.nav_id
        self.update_status(t("playing") if was else "")

        def resume():
            if my_nav != self.nav_id or self.vol is None:
                return  # the user already did something else
            if was:
                self.start()
            else:
                self.play_row_once()

        if speak:
            self.speaker.say(speak, on_done=lambda: self.post(resume))
        else:
            resume()

    def move(self, d):
        if self.vol is not None:
            self.goto(self.row + d)

    def change_slice(self, d):
        if self.vol is None:
            return
        self.slice = int(np.clip(self.slice + d, 0, self.vol.shape[0] - 1))
        self.goto(self.row, speak=t("status", s=self.slice + 1, ns=self.vol.shape[0], r=self.row + 1, nr=self.vol.shape[1]))

    # ---------- audio ----------
    def audio_mod(self):
        if self.sd is None:
            try:
                import sounddevice as sd
                self.sd = sd
            except Exception as e:
                self.status.set(t("audio_err", e=e))
                return None
        return self.sd

    def row_audio(self, r):
        p = self.params()
        return sonify.row_to_audio(self.vol[self.slice, r], p["vmin"], p["vmax"],
                                   p["fmin"], p["fmax"], p["tone_ms"], p["step"])

    def play_row_once(self):
        if self.vol is None:
            return
        sd = self.audio_mod()
        if sd is None:
            return
        try:
            sd.stop()
            sd.play(self.row_audio(self.row), sonify.SAMPLE_RATE)
        except Exception as e:
            self.status.set(t("audio_err", e=e))

    def toggle_play(self):
        if self.vol is None:
            return
        self.nav_id += 1  # cancel a row sound still waiting for speech to finish
        self.stop() if self.playing else self.start()

    def start(self):
        sd = self.audio_mod()
        if sd is None:
            return
        self.playing = True
        self.play_id += 1
        my_id = self.play_id
        threading.Thread(target=self._loop, args=(my_id,), daemon=True).start()

    def _loop(self, my_id):
        sd = self.sd
        while self.playing and my_id == self.play_id:
            self.post(self.update_status, t("playing"))
            try:
                sd.play(self.row_audio(self.row), sonify.SAMPLE_RATE)
                sd.wait()
            except Exception as e:
                self.post(self.status.set, t("audio_err", e=e))
                self.playing = False
                return
            if not self.playing or my_id != self.play_id:
                return
            if self.row >= self.vol.shape[1] - 1:
                self.playing = False
                self.post(self.update_status, t("end"))
                self.speaker.say(t("end"))
                return
            self.row += 1

    def stop(self, update=True):
        self.playing = False
        self.play_id += 1
        if self.sd is not None:
            try:
                self.sd.stop()
            except Exception:
                pass
        if update:
            self.update_status(t("paused"))

    # ---------- export ----------
    def export(self):
        """Save the current slice as WAV in the background, with spoken progress.
        Escape cancels. The window keeps responding the whole time."""
        if self.vol is None:
            return
        if self.export_cancel is not None or self.loading:
            self.speaker.say(t("busy"))
            return
        path = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV", "*.wav")])
        if not path:
            return
        p = self.params()
        image = self.vol[self.slice]
        seconds, size = sonify.estimate_export(image.shape[0], image.shape[1], p["tone_ms"], p["step"])
        msg = t("exporting", minutes=max(1, round(seconds / 60)), mb=max(1, round(size / 1e6)))
        self.status.set(msg)
        self.speaker.say(msg)
        self.export_cancel = threading.Event()
        threading.Thread(target=self._export_worker, args=(path, image, p, self.export_cancel),
                         daemon=True).start()

    def _export_worker(self, path, image, p, cancel):
        last = [0]

        def progress(done, total):
            pct = done * 100 // total
            if pct != last[0]:
                if pct // 25 > last[0] // 25 and pct < 100:
                    self.speaker.say(t("export_pct", pct=pct))
                last[0] = pct
                self.post(self.status.set, t("export_pct", pct=pct))
        try:
            ok = sonify.export_slice_wav(path, image, p["vmin"], p["vmax"], p["fmin"], p["fmax"],
                                         p["tone_ms"], p["step"], progress, cancel)
            self.post(self._export_done, path, ok, None)
        except Exception as e:
            self.post(self._export_done, path, False, e)

    def _export_done(self, path, ok, error):
        self.export_cancel = None
        if error is not None:
            messagebox.showerror(t("error"), str(error))
            return
        msg = t("saved", path=path) if ok else t("export_cancel")
        self.status.set(msg)
        self.speaker.say(msg)

    def cancel(self):
        if self.export_cancel is not None:
            self.export_cancel.set()

    def close(self):
        self.cancel()
        self.stop(update=False)
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
