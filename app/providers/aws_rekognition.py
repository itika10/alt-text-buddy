import os
import boto3
from .base import VisionFinding
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

class AWSRekognition:
    def __init__(self, region_name: str | None = None):
        self.client = boto3.client("rekognition", region_name=region_name or os.getenv("AWS_REGION"))

    def analyse_image(self, image_bytes: bytes) -> VisionFinding:
        labels = self.client.detect_labels(Image={"Bytes": image_bytes}, MaxLabels=25, MinConfidence=60)
        label_names = [l["Name"].lower() for l in labels.get("Labels", [])]

        text = self.client.detect_text(Image={"Bytes": image_bytes})
        ocr_lines = [d["DetectedText"] for d in text.get("TextDetections", []) if d["Type"] == "LINE" and d.get("confidence", 0) >= 70]

        caption = ", ".join(label_names[:3]) if label_names else ""
        print("AWS Rekognition caption:", caption)
        print("AWS Rekognition labels:", label_names)
        print("AWS Rekognition OCR lines:", ocr_lines)

        return VisionFinding(caption=caption, tags=label_names, ocr_lines=ocr_lines,
                             meta={"raw_labels": labels, "raw_text": text})

