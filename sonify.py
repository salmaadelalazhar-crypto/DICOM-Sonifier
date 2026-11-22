"""DICOM loading and high-resolution pixel-to-tone conversion."""
import io
import os

import numpy as np
import pydicom

SAMPLE_RATE = 48000


def load_dicom(path):
    ds = pydicom.dcmread(path, force=True)
    arr = ds.pixel_array.astype(np.float32)
    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    inter = float(getattr(ds, "RescaleIntercept", 0) or 0)
    arr = arr * np.float32(slope) + np.float32(inter)
    spp = int(getattr(ds, "SamplesPerPixel", 1) or 1)
    if spp > 1:  # color -> grayscale
        arr = arr[..., :3].mean(axis=-1)
    if arr.ndim == 2:
        arr = arr[None, ...]
    return arr.astype(np.float32)  # (slices, rows, cols)


# ---------- ZIP file with one DICOM file per slice ----------
MAX_ZIP_ENTRIES = 10000
MAX_ZIP_BYTES = 8 * 1024 ** 3  # refuse archives that unpack to more than 8 GB


class LoadError(Exception):
    """A problem with the chosen file, explained in words for the user.

    `key` is a message name in i18n.STRINGS.
    """

    def __init__(self, key):
        super().__init__(key)
        self.key = key


def _position_key(ds, fallback):
    """Sort slices along the scan direction; fall back to InstanceNumber, then file name."""
    try:
        ori = [float(x) for x in ds.ImageOrientationPatient]
        pos = [float(x) for x in ds.ImagePositionPatient]
        normal = np.cross(ori[:3], ori[3:])
        return (0, float(np.dot(normal, pos)), fallback)
    except Exception:
        pass
    try:
        return (1, float(ds.InstanceNumber), fallback)
    except Exception:
        return (2, 0.0, fallback)


def _natural(name):
    """'IM2' before 'IM10'."""
    import re
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name)]


def _zip_dicom_entries(zf):
    """Read only the headers inside the ZIP and return the DICOM image entries, sorted.

    Folders, hidden files, Mac '__MACOSX' leftovers and files that are not
    DICOM images (text, PDF, DICOMDIR...) are skipped. When the ZIP holds
    more than one scan or image size, the biggest group is used.
    Returns (entries, skipped_count).
    """
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if len(infos) > MAX_ZIP_ENTRIES:
        raise LoadError("zip_too_big")
    if sum(i.file_size for i in infos) > MAX_ZIP_BYTES:
        raise LoadError("zip_too_big")
    groups = {}
    skipped = 0
    for info in infos:
        base = os.path.basename(info.filename)
        if info.filename.startswith("__MACOSX/") or base.startswith(".") or not base:
            continue
        if info.flag_bits & 0x1:
            raise LoadError("zip_password")
        try:
            with zf.open(info) as f:
                ds = pydicom.dcmread(f, stop_before_pixels=True, force=True)
            rows, cols = int(ds.Rows), int(ds.Columns)
        except Exception:
            skipped += 1  # not a DICOM image
            continue
        frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
        group = (str(getattr(ds, "SeriesInstanceUID", "")), rows, cols)
        groups.setdefault(group, []).append((_position_key(ds, _natural(info.filename)), info, frames))
    if not groups:
        raise LoadError("zip_empty")
    best = max(groups.values(), key=lambda g: sum(fr for _, _, fr in g))
    skipped += sum(len(g) for g in groups.values()) - len(best)
    best.sort(key=lambda x: x[0])
    return [info for _, info, _ in best], skipped


def load_zip(path, progress=None, cancel=None):
    """Load a ZIP of DICOM files as one volume: each file is a slice, in scan order.

    Files are unpacked one at a time in memory; nothing is written to disk.
    Returns (volume, skipped_count), or (None, 0) if cancelled.
    """
    import zipfile
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise LoadError("zip_bad")
    with zf:
        entries, skipped = _zip_dicom_entries(zf)
        slices = []
        error = None
        for i, info in enumerate(entries):
            if cancel is not None and cancel.is_set():
                return None, 0
            try:
                # a multi-frame file adds all of its frames
                slices.extend(load_dicom(io.BytesIO(zf.read(info))))
            except Exception as e:  # a damaged file is skipped, the rest still open
                error = error or e
                skipped += 1
            if progress:
                progress(i + 1, len(entries))
    if not slices:
        raise error or LoadError("zip_empty")
    return np.stack(slices).astype(np.float32), skipped


def load_file(path, progress=None, cancel=None):
    """Open a .zip (many DICOM files, one per slice) or a single DICOM file
    (one slice, or several slices in one multi-frame file).

    Returns (volume, skipped_count). Only the chosen file is
    read: the program never looks at other files in the same folder.
    """
    import zipfile
    lower = path.lower()
    if lower.endswith(".zip") or (not lower.endswith((".dcm", ".dicom")) and zipfile.is_zipfile(path)):
        return load_zip(path, progress, cancel)
    try:
        return load_dicom(path), 0
    except Exception:
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True, force=True)
            int(ds.Rows), int(ds.Columns)
        except Exception:
            raise LoadError("not_dicom")
        raise  # a real DICOM image that could not be decoded: keep the exact error


def density_range(vol, max_samples=4_000_000):
    """0.5% and 99.5% density percentiles (sampled on very large volumes so it stays fast)."""
    flat = vol.reshape(-1)
    step = max(1, flat.size // max_samples)
    lo, hi = np.percentile(flat[::step], [0.5, 99.5])
    return float(lo), float(hi)


# ---------- sound ----------
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


def estimate_export(rows, cols, tone_ms, step):
    """Return (seconds, bytes) of a whole-slice 24-bit WAV export."""
    n = max(1, int(SAMPLE_RATE * tone_ms / 1000.0))
    per_row = len(range(0, cols, max(1, int(step)))) * n
    samples = rows * per_row
    return samples / SAMPLE_RATE, samples * 3 + 44


def save_wav(path, audio):
    import soundfile as sf
    sf.write(path, audio, SAMPLE_RATE, subtype="PCM_24")


def export_slice_wav(path, image, vmin, vmax, fmin, fmax, tone_ms, step, progress=None, cancel=None):
    """Write one slice to a 48 kHz / 24-bit WAV, one row at a time.

    Rows are streamed to disk instead of being joined in memory first, so even
    a 300 MB file uses only a few MB of memory. The file is written under a
    temporary name and renamed at the end, so a cancelled or failed export
    never leaves a half-written WAV behind. Returns False if cancelled.
    """
    import soundfile as sf
    tmp = path + ".part"
    rows = image.shape[0]
    try:
        with sf.SoundFile(tmp, "w", SAMPLE_RATE, 1, subtype="PCM_24", format="WAV") as f:
            for r in range(rows):
                if cancel is not None and cancel.is_set():
                    break
                f.write(row_to_audio(image[r], vmin, vmax, fmin, fmax, tone_ms, step))
                if progress:
                    progress(r + 1, rows)
        if cancel is not None and cancel.is_set():
            os.remove(tmp)
            return False
        os.replace(tmp, path)
        return True
    except BaseException:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise
