import streamlit as st
import requests, hashlib
from components import render_result
from metrics import compute_metrics, render_metrics
from services import analyze, fetch_inspect, call_reasoner

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

def run_provider(provider_id: str, title: str):
    # analyze
    with st.spinner(f"{title} analyzing…"):
        r = analyze(API_BASE, provider_id, file.name, file.type, img_bytes)
    if not r.ok:
        try:
            detail = r.json().get("detail")
            if isinstance(detail, dict):
                detail = detail.get("message") or str(detail)
        except Exception:
            detail = r.text[:500]
        st.error(f"{title} error: {detail}")
        return

    out = r.json()
    st.session_state[f"{provider_id}_raw"] = out
    debug_dump(f"{title} raw response", out)

    for k in [
        "azure_raw", "azure_inspect", "azure_reasoned",
        "aws_raw",   "aws_inspect",   "aws_reasoned",
        "google_raw","google_inspect","google_reasoned",
    ]:
        st.session_state.pop(k, None)

    render_result(
        title=title,
        alt_text=out.get("alt_text",""),
        tags=out.get("tags", []),
    )

    # inspect
    insp = fetch_inspect(API_BASE, provider_id, file.name, file.type, img_bytes)
    st.session_state[f"{provider_id}_inspect"] = insp
    if insp:
        debug_dump(f"{title} inspect", insp)
        m = compute_metrics(
            alt_text=out.get("alt_text",""),
            tags=out.get("tags", []),
            ocr_lines=insp.get("ocr_lines", []),
        )
        render_metrics("Metrics", m)

    # reason (GPT)
    if use_gpt:
        rr = call_reasoner(
            API_BASE,
            alt_text=out.get("alt_text",""),
            tags=out.get("tags", []),
            ocr_lines=(insp or {}).get("ocr_lines", []),
            use_case=use_case,
            tone=tone,
            max_len=max_len,
        )
        if rr.ok:
            rout = rr.json()
            st.session_state[f"{provider_id}_reasoned"] = rout
            debug_dump(f"Reasoned (from {title.split()[0]})", rout)
            render_result(
                title=f"GPT reasoning based on {title} results",
                alt_text=rout.get("alt_text",""),
                tags=rout.get("tags", []),
                explain_why=rout.get("explain_why",""),
            )
            if insp:
                m = compute_metrics(
                    alt_text=rout.get("alt_text",""),
                    tags=rout.get("tags", []),
                    ocr_lines=insp.get("ocr_lines", []),
                )
                render_metrics("Metrics", m)
        else:
            st.error(f"Reasoner ({title.split()[0]}) error: {rr.status_code} - {rr.text[:500]}")

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
        ]:
            st.session_state.pop(k, None)

# ---- Generate button ----
clicked = st.button("Generate", disabled=(file is None))
if clicked and not (use_azure or use_aws or use_google):
    st.warning("Select at least one provider on the left.")

elif clicked and file and img_bytes:
    if use_azure:
        run_provider("azure", "Azure (raw)")
    if use_aws:
        run_provider("aws", "AWS Rekognition")
    if use_google:
        run_provider("google", "Google Vision")