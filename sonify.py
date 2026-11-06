"""المحرك الأساسي: قراءة DICOM وتحويل الكثافات إلى أصوات عالية الدقة."""
import io
import numpy as np
import pydicom
import soundfile as sf

SR = 48000


def load_dicom(file):
    ds = pydicom.dcmread(file, force=True)
    px = ds.pixel_array.astype(np.float64)
    if px.ndim == 3 and px.shape[-1] in (3, 4):
        px = px[..., :3] @ np.array([0.299, 0.587, 0.114])
        frames = None
    elif px.ndim == 3:
        frames = px
        px = px[px.shape[0] // 2]
    else:
        frames = None
    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    inter = float(getattr(ds, "RescaleIntercept", 0) or 0)
    fix = lambda a: a * slope + inter
    px = fix(px)
    if frames is not None:
        frames = fix(frames)
    if str(getattr(ds, "PhotometricInterpretation", "")) == "MONOCHROME1":
        px = px.max() - px + px.min()
    return ds, px, frames


def default_window(ds, px):
    try:
        wc, ww = ds.WindowCenter, ds.WindowWidth
        wc = float(wc[0] if isinstance(wc, pydicom.multival.MultiValue) else wc)
        ww = float(ww[0] if isinstance(ww, pydicom.multival.MultiValue) else ww)
        return wc - ww / 2, wc + ww / 2
    except Exception:
        lo, hi = np.percentile(px, [0.5, 99.5])
        return float(lo), float(hi)


class Mapper:
    """تحويل أُسّي: خطوات كثافة متساوية = فواصل موسيقية متساوية."""
    def __init__(self, vmin, vmax, fmin=30.0, fmax=14000.0, quant=65536):
        self.vmin, self.vmax, self.fmin, self.fmax, self.quant = vmin, vmax, fmin, fmax, quant

    def norm(self, v):
        n = (np.asarray(v, dtype=np.float64) - self.vmin) / max(self.vmax - self.vmin, 1e-9)
        n = np.clip(n, 0, 1)
        return np.round(n * (self.quant - 1)) / (self.quant - 1)

    def freq(self, v):
        return self.fmin * (self.fmax / self.fmin) ** self.norm(v)


def loudness_comp(f):
    """تعويض تقريبي لمنحنيات الجهارة المتساوية (ISO 226)."""
    lf = np.log10(np.maximum(np.asarray(f, float), 20) / 1000.0)
    g = 1 + 0.9 * np.maximum(-lf, 0) ** 1.3 + 0.6 * np.maximum(lf - 0.5, 0) ** 1.5
    return np.clip(g / 2.2, 0.2, 1.0)


def synth(freqs, dur_each, sr=SR):
    n = max(int(dur_each * sr), 1)
    f = np.repeat(np.asarray(freqs, float), n)
    k = max(int(0.002 * sr), 1)
    if k > 1 and len(f) > k:
        f = np.convolve(np.pad(f, (k // 2, k - k // 2 - 1), mode="edge"), np.ones(k) / k, mode="valid")
    sig = np.sin(2 * np.pi * np.cumsum(f) / sr) * loudness_comp(f)
    fade = min(int(0.01 * sr), len(sig) // 2)
    if fade:
        r = np.linspace(0, 1, fade)
        sig[:fade] *= r
        sig[-fade:] *= r[::-1]
    return (0.8 * sig).astype(np.float32)


def scan_image(px, mapper, step=4, dur=0.004, row_gap=0.03):
    gap = np.zeros(int(row_gap * SR), np.float32)
    out = []
    for i, row in enumerate(px[::step, ::step]):
        if i % 2:
            row = row[::-1]
        out += [synth(mapper.freq(row), dur), gap]
    return np.concatenate(out)


def point_tone(px, mapper, x, y, dur=1.5, r=1):
    v = float(px[max(y - r, 0):y + r + 1, max(x - r, 0):x + r + 1].mean())
    f = float(mapper.freq(v))
    return v, f, synth([f], dur)


def to_wav_bytes(sig):
    buf = io.BytesIO()
    sf.write(buf, sig, SR, format="WAV", subtype="PCM_24")
    return buf.getvalue()
