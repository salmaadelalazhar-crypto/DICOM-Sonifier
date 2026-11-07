"""DICOM Sonifier - desktop app for blind users. Keyboard-driven, row-by-row playback."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np

from speech import Speaker

from i18n import LANG, t
import sonify


class App:
    def __init__(self, root):
        self.root = root
        root.title(t("title"))
        root.geometry("640x520")
        self.vol = None
        self.slice = 0
        self.row = 0
        self.playing = False
        self.play_id = 0
        self.sd = None
        self.speaker = Speaker(LANG)
        anchor = "e" if LANG == "ar" else "w"
        side = "right" if LANG == "ar" else "left"

        self.status = tk.StringVar(value=t("no_file"))
        tk.Label(root, textvariable=self.status, font=("Segoe UI", 14), wraplength=600,
                 justify=side, anchor=anchor).pack(fill="x", padx=12, pady=10)

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
        for i, (k, v) in enumerate([("fmin", 30), ("fmax", 14000), ("vmin", -1000),
                                    ("vmax", 3000), ("tone_ms", 15), ("step", 2), ("parts", 10)]):
            ttk.Label(box, text=t(k)).grid(row=i, column=1 if LANG == "ar" else 0, sticky=anchor, padx=4)
            var = tk.StringVar(value=str(v))
            ttk.Entry(box, textvariable=var, width=10).grid(row=i, column=0 if LANG == "ar" else 1, padx=4, pady=1)
            self.vars[k] = var
        ttk.Button(box, text=t("apply"), command=self.apply).grid(row=7, column=0, columnspan=2, pady=4)

        ttk.Label(root, text=t("help"), wraplength=600, justify=side).pack(fill="x", padx=12)

        for seq, fn in [("<Control-o>", self.open_file), ("<space>", self.toggle_play),
                        ("<Left>", lambda: self.move(-1)), ("<Right>", lambda: self.move(1)),
                        ("<Up>", lambda: self.move_part(-1)), ("<Down>", lambda: self.move_part(1)),
                        ("<r>", self.play_row_once), ("<w>", self.announce),
                        ("<Home>", lambda: self.goto(0)), ("<End>", lambda: self.goto(10**9)),
                        ("<Prior>", lambda: self.change_slice(-1)), ("<Next>", lambda: self.change_slice(1)),
                        ("<Control-s>", self.export)]:
            root.bind(seq, lambda e, f=fn: (f(), "break")[1])
        root.protocol("WM_DELETE_WINDOW", self.close)

        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            self.load(sys.argv[1])

    # ---------- settings ----------
    def params(self):
        try:
            p = {k: float(v.get()) for k, v in self.vars.items()}
        except ValueError:
            p = {"fmin": 30, "fmax": 14000, "vmin": -1000, "vmax": 3000, "tone_ms": 15, "step": 2, "parts": 10}
        p["fmin"] = max(20.0, p["fmin"])
        p["fmax"] = max(p["fmin"] + 1, min(20000.0, p["fmax"]))
        p["tone_ms"] = max(1.0, p["tone_ms"])
        p["step"] = max(1, int(p["step"]))
        p["parts"] = max(1, int(p["parts"]))
        return p

    def apply(self):
        self.update_status()

    # ---------- file ----------
    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("DICOM", "*.dcm *.dicom *"), ("All", "*")])
        if path:
            self.load(path)

    def load(self, path):
        try:
            self.stop()
            self.vol = sonify.load_dicom(path)
            self.slice = self.vol.shape[0] // 2
            self.row = 0
            lo, hi = np.percentile(self.vol, [0.5, 99.5])
            self.vars["vmin"].set(f"{lo:.0f}")
            self.vars["vmax"].set(f"{hi:.0f}")
            msg = t("loaded", name=os.path.basename(path), rows=self.vol.shape[1], slices=self.vol.shape[0])
            self.status.set(msg)
            self.speaker.say(msg)
        except Exception as e:
            messagebox.showerror(t("error"), str(e))

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
        if self.vol is None:
            return
        self.row = int(np.clip(r, 0, self.vol.shape[1] - 1))
        if speak:
            self.speaker.say(speak, block=True)
        was = self.playing
        self.stop()
        if was:
            self.start()
        else:
            self.update_status()
            self.play_row_once()

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
            self.root.after(0, self.update_status, t("playing"))
            try:
                sd.play(self.row_audio(self.row), sonify.SAMPLE_RATE)
                sd.wait()
            except Exception as e:
                self.root.after(0, self.status.set, t("audio_err", e=e))
                self.playing = False
                return
            if not self.playing or my_id != self.play_id:
                return
            if self.row >= self.vol.shape[1] - 1:
                self.playing = False
                self.root.after(0, self.update_status, t("end"))
                self.speaker.say(t("end"))
                return
            self.row += 1

    def stop(self):
        self.playing = False
        self.play_id += 1
        if self.sd is not None:
            try:
                self.sd.stop()
            except Exception:
                pass
        self.update_status(t("paused"))

    def export(self):
        if self.vol is None:
            return
        path = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV", "*.wav")])
        if not path:
            return
        try:
            audio = np.concatenate([self.row_audio(r) for r in range(self.vol.shape[1])])
            sonify.save_wav(path, audio)
            self.status.set(t("saved", path=path))
        except Exception as e:
            messagebox.showerror(t("error"), str(e))

    def close(self):
        self.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
