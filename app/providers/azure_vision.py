import requests
from .base import VisionFinding

class AzureVision:
    def __init__(self, endpoint: str, key: str):
        self.url = (
            f"{endpoint.rstrip('/')}/computervision/imageanalysis:analyze"
             "?api-version=2023-10-01&features=caption,tags,objects,read&model-version=latest&language=en"
        )
        self.key = key

    def analyze_image(self, image_bytes: bytes) -> VisionFinding:
        headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Content-Type": "application/octet-stream",
        }

        r = requests.post(self.url, headers=headers, data=image_bytes, timeout=30)
        r.raise_for_status()
        data = r.json()
        caption = data.get("captionResult", {}).get("text", "") or ""
        tags = [t.get("name") for t in (data.get("tagsResult") or {}).get("values", [])]

        # --- OCR extraction (simple + effective) ---
        ocr_lines: list[str] = []
        read = data.get("readResult") or {}
        for block in read.get("blocks", []):
            for line in block.get("lines", []):
                txt = (line.get("text") or "").strip()
                conf = line.get("confidence", 1.0)
                if txt and conf >= 0.6:              # filter weak lines
                    ocr_lines.append(txt)

        return VisionFinding(caption=caption, tags=tags, ocr_lines=ocr_lines, meta={"raw": data})
    