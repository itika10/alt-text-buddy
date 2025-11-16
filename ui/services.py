from __future__ import annotations
import requests
import streamlit as st
from typing import Dict, Any

# Cache inspect per (api_base, provider, image-hash) for 5 minutes
@st.cache_data(ttl=300, show_spinner=False)
def fetch_inspect(api_base: str, provider: str, name: str, mime: str, img_bytes: bytes) -> Dict[str, Any] | None:
    ep = "/inspect-azure" if provider == "azure" else "/inspect-aws"
    try:
        r = requests.post(f"{api_base.rstrip('/')}{ep}",
                          files={"image": (name, img_bytes, mime)}, timeout=60)
        return r.json() if r.ok else None
    except Exception:
        return None
    
def analyze(api_base: str, provider: str, name: str, mime: str, img_bytes: bytes) -> requests.Response:
    ep = "/analyze-azure" if provider == "azure" else "/analyze-aws"
    return requests.post(f"{api_base.rstrip('/')}{ep}",
                         files={"image": (name, img_bytes, mime)}, timeout=90)

def call_reasoner(api_base: str, *, alt_text: str, tags: list[str], ocr_lines: list[str],
                  use_case: str, tone: str, max_len: int) -> requests.Response:
    return requests.post(f"{api_base.rstrip('/')}/reason",
                         json={"alt_text": alt_text, "tags": tags, "ocr_lines": ocr_lines,
                               "use_case": use_case, "tone": tone, "max_len": max_len},
                         timeout=120)