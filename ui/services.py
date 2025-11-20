from __future__ import annotations
import requests

def call_pipeline(api_base: str, providers: list[str], name: str, mime: str, img_bytes: bytes,
                  *, reason: bool, use_case: str, tone: str, max_len: int):
    return requests.post(
        f"{api_base.rstrip('/')}/pipeline",
        data={
            "providers": ",".join(providers),
            "reason": str(bool(reason)).lower(),  # "true"/"false"
            "use_case": use_case,
            "tone": tone,
            "max_len": str(max_len),
        },
        files={"image": (name, img_bytes, mime)},
        timeout=180,
    )
