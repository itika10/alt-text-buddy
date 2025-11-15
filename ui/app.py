import streamlit as st
import requests, hashlib
from components import render_result
from metrics import compute_metrics, render_metrics

st.set_page_config(page_title="Alt Text Buddy", page_icon="🖼️")
st.title("Alt Text Buddy")

# --- Sidebar: API + providers ---
st.sidebar.header("API")
API_BASE = st.sidebar.text_input("API base URL", "http://localhost:8000").rstrip("/")

st.sidebar.header("Providers")
use_azure = st.sidebar.checkbox("Azure Vision", value=True)
use_aws = st.sidebar.checkbox("AWS Rekognition", value=True)
use_azure_gpt = st.sidebar.checkbox("Azure + GPT (reasoned)", value=True)

st.sidebar.header("Generation options")
use_case = st.sidebar.selectbox("Use case", ["web","ecommerce","news","education","docs"])
tone = st.sidebar.selectbox("Tone", ["neutral","friendly","professional","informative"])
max_len = st.sidebar.slider("Max alt-text length", 60, 300, 160)

show_debug = st.sidebar.checkbox("Show debug", value=False)
def debug_dump(title, payload):
    if show_debug:
        with st.expander(title):
            st.write(payload)

# ---- Main: file upload + preview ----
file = st.file_uploader("Upload an image", type=["png","jpg","jpeg","webp"])
img_bytes = None
if file is not None:
    img_bytes = file.getvalue()
    st.image(img_bytes, caption=f"Preview: {file.name}", width=220)

# ---- Cache /inspect per image ----
def img_hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

@st.cache_data(show_spinner=False)
def cached_inspect(api_base: str, name: str, mime: str, bytes_: bytes):
    try:
        r = requests.post(f"{api_base}/inspect", files={"image": (name, bytes_, mime)}, timeout=60)
        return r.json() if r.ok else None
    except Exception:
        return None

ocr_info = cached_inspect(API_BASE, file.name, file.type, img_bytes) if img_bytes else None

# ---- Generate button ----
clicked = st.button("Generate")
if clicked and not (use_azure or use_azure_gpt or use_aws):
    st.warning("Select at least one provider on the left.")

elif clicked and file and img_bytes:
    # --- Azure (raw) ---
    if use_azure:
        with st.spinner("Azure analyzing…"):
            r = requests.post(
                f"{API_BASE}/analyze-azure",
                files={"image": (file.name, img_bytes, file.type)},
                timeout=90
            )
        if r.ok:
            out = r.json()
            debug_dump("Azure raw response", out)
            render_result(
                title="Azure (raw)",
                alt_text=out.get("alt_text", ""),
                tags=out.get("tags", []),
            )
            if ocr_info:
                m = compute_metrics(
                    alt_text=out.get("alt_text", ""),
                    tags=out.get("tags", []),
                    ocr_lines=ocr_info.get("ocr_lines", []),
                )
                render_metrics("Metrics", m)
        
        else:
            st.error(f"Azure error: {r.status_code} - {r.text[:500]}")

    # --- AWS Rekognition ---
    if use_aws:
        with st.spinner("AWS Rekognition anlyzing..."):
            r = requests.post(
                f"{API_BASE}/analyze-aws",
                files={"image": (file.name, img_bytes, file.type)},
                timeout=90
            )

        if r.ok:
            out = r.json()
            render_result(
                title="AWS Rekognition",
                alt_text=out.get("alt_text", ""),
                tags=out.get("tags", [])
            )
            if ocr_info:
                m = compute_metrics(
                    alt_text=out.get("alt_text", ""),
                    tags=out.get("tags", []),          # grounding tags from inspect
                    ocr_lines=ocr_info.get("ocr_lines", []),
                )
                render_metrics("Metrics", m)
        
        else:
            st.error(f"AWS error: {r.status_code} - {r.text[:500]}")


    # --- Azure + GPT (reasoned) ---
    if use_azure_gpt:
        with st.spinner("Azure + GPT generating..."):
            r = requests.post(
                f"{API_BASE}/generate",
                files={"image": (file.name, img_bytes, file.type)},
                data={
                    "use_case": use_case,
                    "tone": tone,
                    "max_len": str(max_len),
                },
                timeout=120
            )
        if r.ok:
            out = r.json()
            debug_dump("Azure + GPT response", out)
            render_result(
            "Azure + GPT",
            alt_text=out.get("alt_text",""),
            tags=out.get("tags", []),
            explain_why=out.get("explain_why","")
        )
            if ocr_info:
                m = compute_metrics(
                    alt_text=out.get("alt_text", ""),
                    tags=out.get("tags", []),          # grounding tags from inspect
                    ocr_lines=ocr_info.get("ocr_lines", []),
                )
                render_metrics("Metrics", m)
        else:
            st.error(f"Azure + GPT error: {r.status_code} - {r.text[:500]}")
