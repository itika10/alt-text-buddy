import os
from typing import List
from google.cloud import vision
from .base import VisionFinding

class GoogleVision:
    def __init__(self):
        # Auth comes from GOOGLE_APPLICATION_CREDENTIALS
        self.client = vision.ImageAnnotatorClient()

    def analyze_image(self, image_bytes: bytes) -> VisionFinding:
        img = vision.Image(content=image_bytes)

        # labels
        lr = self.client.label_detection(image=img)
        labels = lr.label_annotations or []
        kept = [l for l in labels if (l.score or 0) >= 0.6]
        tags : List[str] = [l.description.lower() for l in kept]

        # Naive caption from top labels
        caption = ", ".join([l.description.lower() for l in kept[:3]]) if kept else ""

        # OCR
        tr = self.client.text_detection(image=img)
        ocr_lines: List[str] = []
        # Prefer PAGE/LINE like content via full_text_annotation if present
        if tr.full_text_annotation and tr.full_text_annotation.text:
            # Split by lines, strip empties, keep short lines
            for line in tr.full_text_annotation.text.splitlines():
                line = (line or "").strip()
                if line and not line.isnumeric():
                    ocr_lines.append(line)
        else:
            # Fallback to text_annotations (first is the full text)
            for ent in tr.text_annotations[1:]:
                txt = (ent.description or "").strip()
                if txt and not txt.isnumeric():
                    ocr_lines.append(txt)

        return VisionFinding(
            caption=caption,
            tags=tags,
            ocr_lines=ocr_lines,
            meta={"labels_raw": lr, "text_raw": tr},
        )





 