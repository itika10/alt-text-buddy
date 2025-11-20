import streamlit as st
import requests, hashlib
from components import render_result
from metrics import compute_metrics, render_metrics
from services import call_pipeline

st.set_page_config(page_title="Alt Text Buddy", page_icon="🖼️")
st.title("Alt Text Buddy")

# --- Sidebar: API + providers ---
st.sidebar.header("API")
API_BASE = st.sidebar.text_input("API base URL", "http://localhost:8000").rstrip("/")

st.sidebar.header("Vision Providers")
use_azure = st.sidebar.checkbox("Azure Vision", value=False)
use_aws = st.sidebar.checkbox("AWS Rekognition", value=True)
use_google = st.sidebar.checkbox("Google Vision", value=True)

st.sidebar.header("Reasoning engine")
use_gpt = st.sidebar.checkbox("Refine with GPT", value=True)

st.sidebar.header("Reasoning options")
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

    # reset per-provider scratch state when the image changes
    cur_hash = hashlib.sha256(img_bytes).hexdigest()
    if st.session_state.get("last_img_hash") != cur_hash:
        st.session_state["last_img_hash"] = cur_hash
        # clear any stale payloads from previous image
        for k in [
            "azure_raw", "azure_inspect", "azure_reasoned",
            "aws_raw",   "aws_inspect",   "aws_reasoned",
            "google_raw","google_inspect","google_reasoned",
        ]:
            st.session_state.pop(k, None)

# ---- Generate button ----
clicked = st.button("Generate", disabled=(file is None))
if clicked and not (use_azure or use_aws or use_google):
    st.warning("Select at least one provider on the left.")

elif clicked and file and img_bytes:
    selected = []
    if use_azure: selected.append("azure")
    if use_aws:   selected.append("aws")
    if use_google: selected.append("google")

    with st.spinner("Running providers…"):
        r = call_pipeline(API_BASE, selected, file.name, file.type, img_bytes,
                          reason=use_gpt, use_case=use_case, tone=tone, max_len=max_len)

    if not r.ok:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text[:500]
        st.error(f"Pipeline error: {detail}")
    else:
        bundle = r.json().get("results", {})
        title_map = {"azure": "Azure Vision", "aws": "AWS Rekognition", "google": "Google Vision"}
        for pid, data in bundle.items():
            title = title_map.get(pid, pid)

            if isinstance(data, dict) and "error" in data:
                st.error(f"{title} error: {data['error']}")
                continue

            raw = data.get("raw") or {}
            reasoned = data.get("reasoned")

            # Raw
            debug_dump(f"{title} raw", raw)
            render_result(title=f"{title} (raw)",
                          alt_text=raw.get("alt_text",""),
                          tags=raw.get("tags", []))
            m = compute_metrics(
                alt_text=raw.get("alt_text",""),
                tags=raw.get("tags", []),
                ocr_lines=(raw.get("ocr_lines") or []),
            )
            render_metrics("Metrics", m)

            # Reasoned (if present)
            if reasoned:
                debug_dump(f"{title} reasoned", reasoned)
                render_result(title=f"{title} + GPT",
                              alt_text=reasoned.get("alt_text",""),
                              tags=reasoned.get("tags", []),
                              explain_why=reasoned.get("explain_why",""))
                m2 = compute_metrics(
                    alt_text=reasoned.get("alt_text",""),
                    tags=reasoned.get("tags", []),
                    ocr_lines=(raw.get("ocr_lines") or []),
                )
                render_metrics("Metrics (reasoned)", m2)