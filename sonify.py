"""DICOM loading and high-resolution pixel-to-tone conversion."""
import numpy as np
import pydicom

SAMPLE_RATE = 48000


def load_dicom(path):
    ds = pydicom.dcmread(path, force=True)
    arr = ds.pixel_array.astype(np.float64)
    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    inter = float(getattr(ds, "RescaleIntercept", 0) or 0)
    arr = arr * slope + inter
    spp = int(getattr(ds, "SamplesPerPixel", 1) or 1)
    if spp > 1:  # color -> grayscale
        arr = arr[..., :3].mean(axis=-1)
    if arr.ndim == 2:
        arr = arr[None, ...]
    return arr  # (slices, rows, cols)


def row_to_audio(row, vmin, vmax, fmin, fmax, tone_ms, step=1):
    """Low density -> low pitch, high density -> high pitch (log scale, continuous phase)."""
    vals = np.asarray(row, dtype=np.float64)[::max(1, int(step))]
    norm = np.clip((vals - vmin) / max(vmax - vmin, 1e-9), 0.0, 1.0)
    freqs = fmin * (fmax / fmin) ** norm
    n = max(1, int(SAMPLE_RATE * tone_ms / 1000.0))
    f_inst = np.repeat(freqs, n)
    # smooth the frequency jumps slightly (~2 ms) to avoid clicks
    k = max(1, int(SAMPLE_RATE * 0.002))
    if k > 1 and f_inst.size > k:
        f_inst = np.convolve(f_inst, np.ones(k) / k, mode="same")
    phase = 2 * np.pi * np.cumsum(f_inst) / SAMPLE_RATE
    # equal-loudness-ish compensation: soften very high tones
    amp = 0.6 / (1 + (f_inst / 6000.0) ** 2) ** 0.25
    sig = amp * np.sin(phase)
    fade = min(int(SAMPLE_RATE * 0.005), sig.size // 2)
    if fade > 0:
        ramp = np.linspace(0, 1, fade)
        sig[:fade] *= ramp
        sig[-fade:] *= ramp[::-1]
    return sig.astype(np.float32)


def save_wav(path, audio):
    import soundfile as sf
    sf.write(path, audio, SAMPLE_RATE, subtype="PCM_24")
