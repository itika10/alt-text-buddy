import os
import boto3
from botocore.config import Config
from .base import VisionFinding

class AWSRekognition:
    def __init__(self, region_name: str | None = None):

        cfg = Config(
            retries={"max_attempts": 4, "mode": "standard"},
            read_timeout=20,
            connect_timeout=5,
        )
        session = boto3.Session(region_name=region_name or os.getenv("AWS_REGION", "us-east-1"))
        self.client = session.client("rekognition", config=cfg)
       
    def analyze_image(self, image_bytes: bytes) -> VisionFinding:
        lr = self.client.detect_labels(
            Image={"Bytes": image_bytes},
            MaxLabels=25,
            MinConfidence=60,
        )
        labels = lr.get("Labels", [])
        tags = [l.get("Name", "").lower() for l in labels if l.get("Confidence", 0) >= 60]

        # naive caption from top labels
        caption = ", ".join([l.get("Name", "").lower() for l in labels[:3]]) if labels else ""

        # ------- Text (OCR) -------
        tr = self.client.detect_text(Image={"Bytes": image_bytes})
        ocr_lines: list[str] = []

        # Prefer LINE nodes
        for det in tr.get("TextDetections", []):
            if det.get("Type") == "LINE" and det.get("Confidence", 0) >= 70:
                txt = (det.get("DetectedText") or "").strip()
                if txt and not txt.isnumeric():
                    ocr_lines.append(txt)

        # Fallback: build short lines from WORDs when LINEs are missing
        if not ocr_lines:
            words = [
                (det.get("DetectedText") or "").strip()
                for det in tr.get("TextDetections", [])
                if det.get("Type") == "WORD" and det.get("Confidence", 0) >= 80
            ]
            # chunk WORDs into phrases (~6 words) so GPT gets something meaningful
            buf, CHUNK = [], 6
            for w in words:
                if w and not w.isnumeric():
                    buf.append(w)
                    if len(buf) >= CHUNK:
                        ocr_lines.append(" ".join(buf))
                        buf = []
            if buf:
                ocr_lines.append(" ".join(buf))

        return VisionFinding(caption=caption, tags=tags, ocr_lines=ocr_lines,
                             meta={"labels_raw": lr, "text_raw": tr})

