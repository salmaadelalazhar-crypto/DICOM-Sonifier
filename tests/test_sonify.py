import os
import sys
import threading

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sonify  # noqa: E402


def test_streamed_export_matches_joined_rows(tmp_path):
    import soundfile as sf
    img = np.random.default_rng(0).uniform(-1000, 3000, (6, 40)).astype(np.float32)
    path = str(tmp_path / "out.wav")
    assert sonify.export_slice_wav(path, img, -1000, 3000, 30, 14000, 15, 2)
    data, sr = sf.read(path, dtype="float32")
    expected = np.concatenate([sonify.row_to_audio(r, -1000, 3000, 30, 14000, 15, 2) for r in img])
    info = sf.info(path)
    assert sr == 48000 and info.subtype == "PCM_24"
    assert data.shape == expected.shape and np.abs(data - expected).max() < 1e-5


def test_cancelled_export_leaves_no_file(tmp_path):
    cancel = threading.Event()
    cancel.set()
    path = str(tmp_path / "out.wav")
    assert sonify.export_slice_wav(path, np.zeros((4, 10)), 0, 1, 30, 14000, 15, 1, cancel=cancel) is False
    assert os.listdir(tmp_path) == []


def test_estimate_512_slice():
    seconds, size = sonify.estimate_export(512, 512, 15, 2)
    assert round(seconds / 60) == 33 and round(size / 1e6) == 283


def _write_slice(path, z, inst, uid, value):
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset(path, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SeriesInstanceUID = uid
    ds.InstanceNumber = inst
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.ImagePositionPatient = [0, 0, z]
    ds.Rows, ds.Columns = 4, 5
    ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
    ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 16, 15, 0
    ds.PixelData = np.full((4, 5), value, np.uint16).tobytes()
    ds.save_as(path, enforce_file_format=True)


def _zip(path, files):
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        for name, src in files:
            if src is None:
                z.writestr(name, "hello")
            else:
                z.write(src, name)


def test_zip_slices_are_sorted_by_scan_position_not_file_name(tmp_path):
    uid = "1.2.3.4"
    _write_slice(str(tmp_path / "b.dcm"), 10.0, 3, uid, 30)
    _write_slice(str(tmp_path / "a.dcm"), 0.0, 1, uid, 10)
    _write_slice(str(tmp_path / "c.dcm"), 5.0, 2, uid, 20)
    zp = str(tmp_path / "scan.zip")
    # no-extension DICOM file inside a sub-folder, a text file and Mac leftovers
    _zip(zp, [("scan/IM3", str(tmp_path / "b.dcm")), ("scan/x1.dcm", str(tmp_path / "a.dcm")),
              ("scan/x2.dcm", str(tmp_path / "c.dcm")), ("scan/notes.txt", None),
              ("__MACOSX/scan/._x1.dcm", None)])
    vol, skipped = sonify.load_file(zp)
    assert vol.shape == (3, 4, 5)
    assert [float(vol[i, 0, 0]) for i in range(3)] == [10, 20, 30]
    assert skipped == 1  # notes.txt


def test_zip_falls_back_to_instance_number(tmp_path):
    from pydicom import dcmread
    for z, inst, v in [(0, 2, 20), (0, 1, 10)]:
        p = str(tmp_path / f"{v}.dcm")
        _write_slice(p, z, inst, "1.2", v)
        ds = dcmread(p)
        del ds.ImagePositionPatient
        ds.save_as(p)
    zp = str(tmp_path / "s.zip")
    _zip(zp, [("a.dcm", str(tmp_path / "20.dcm")), ("b.dcm", str(tmp_path / "10.dcm"))])
    vol, _ = sonify.load_file(zp)
    assert [float(vol[i, 0, 0]) for i in range(2)] == [10, 20]


def test_zip_without_dicom_gives_clear_message(tmp_path):
    zp = str(tmp_path / "x.zip")
    _zip(zp, [("a.txt", None)])
    try:
        sonify.load_file(zp)
        assert False
    except sonify.LoadError as e:
        assert e.key == "zip_empty"


def test_single_dcm_has_one_slice_and_other_files_in_folder_are_ignored(tmp_path):
    _write_slice(str(tmp_path / "a.dcm"), 0.0, 1, "1.2", 10)
    _write_slice(str(tmp_path / "b.dcm"), 5.0, 2, "1.2", 20)  # same scan, same folder
    vol, skipped = sonify.load_file(str(tmp_path / "a.dcm"))
    assert vol.shape == (1, 4, 5) and skipped == 0


def test_multi_frame_dcm_keeps_all_slices_in_order(tmp_path):
    from pydicom import dcmread
    p = str(tmp_path / "m.dcm")
    _write_slice(p, 0.0, 1, "1.2", 0)
    ds = dcmread(p)
    ds.NumberOfFrames = 3
    ds.PixelData = np.stack([np.full((4, 5), v, np.uint16) for v in (1, 2, 3)]).tobytes()
    ds.save_as(p)
    vol, _ = sonify.load_file(p)
    assert [float(vol[i, 0, 0]) for i in range(3)] == [1, 2, 3]


def test_text_file_is_not_dicom(tmp_path):
    p = tmp_path / "notes.dcm"
    p.write_text("hello")
    try:
        sonify.load_file(str(p))
        assert False
    except sonify.LoadError as e:
        assert e.key == "not_dicom"
