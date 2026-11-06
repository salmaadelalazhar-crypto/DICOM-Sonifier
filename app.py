import numpy as np
import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates
from sonify import load_dicom, default_window, Mapper, scan_image, point_tone, to_wav_bytes

st.set_page_config(page_title="DICOM Sonifier - سماع الأشعة", page_icon="🩻", layout="wide")
st.markdown("<style>body, .stMarkdown {direction: rtl; text-align: right;}</style>", unsafe_allow_html=True)
st.title("🩻 سماع الأشعة الطبية (DICOM → صوت)")
st.caption("الكثافة المنخفضة = نغمة غليظة • الكثافة المرتفعة = نغمة حادة")

up = st.file_uploader("ارفع ملف DICOM", type=None)
if not up:
    st.info("ارفع ملف أشعة بصيغة DICOM للبدء.")
    st.stop()

try:
    ds, px, frames = load_dicom(up)
except Exception as e:
    st.error(f"تعذرت قراءة الملف: {e}")
    st.stop()

if frames is not None:
    idx = st.slider("الشريحة", 0, frames.shape[0] - 1, frames.shape[0] // 2)
    px = frames[idx]

lo0, hi0 = default_window(ds, px)
with st.sidebar:
    st.header("الإعدادات")
    fmin = st.number_input("أدنى تردد (Hz)", 20.0, 2000.0, 30.0)
    fmax = st.number_input("أعلى تردد (Hz)", 1000.0, 20000.0, 14000.0)
    lo = st.number_input("أدنى كثافة", value=round(lo0, 1))
    hi = st.number_input("أعلى كثافة", value=round(hi0, 1))
    step = st.slider("دقة المسح (كل كم بكسل)", 1, 16, 4)
    dur = st.slider("مدة كل نغمة (ms)", 1, 20, 4) / 1000
    tone_len = st.slider("مدة نغمة النقطة (ث)", 0.3, 5.0, 1.5)

mapper = Mapper(lo, hi, fmin, fmax)
st.write(f"**النوع:** {getattr(ds, 'Modality', '?')} • **الأبعاد:** {px.shape[1]}×{px.shape[0]} • "
         f"**المدى:** {px.min():.0f} .. {px.max():.0f}")

c1, c2 = st.columns([3, 2])
with c1:
    img = Image.fromarray((mapper.norm(px) * 255).astype(np.uint8))
    w = min(700, img.width)
    st.write("اضغط على أي نقطة في الصورة لسماع نغمتها:")
    click = streamlit_image_coordinates(img, width=w, key="img")

with c2:
    if click:
        s = img.width / click["width"]
        x, y = int(click["x"] * s), int(click["y"] * s)
        x, y = min(x, px.shape[1] - 1), min(y, px.shape[0] - 1)
        v, f, sig = point_tone(px, mapper, x, y, tone_len)
        st.metric("الموضع", f"({x}, {y})")
        st.metric("الكثافة", f"{v:.1f}")
        st.metric("التردد", f"{f:.2f} Hz")
        st.audio(to_wav_bytes(sig), format="audio/wav", autoplay=True)

    st.divider()
    if st.button("▶ مسح الصورة كاملة صوتياً", use_container_width=True):
        with st.spinner("جارٍ توليد الصوت..."):
            st.session_state.scan = to_wav_bytes(scan_image(px, mapper, step, dur))
    if "scan" in st.session_state:
        st.audio(st.session_state.scan, format="audio/wav")
        st.download_button("⬇ تحميل WAV (48kHz/24bit)", st.session_state.scan,
                           "dicom_sound.wav", "audio/wav", use_container_width=True)
