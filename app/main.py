from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Callable
import os, json
from openai import OpenAI
from app.config import AZURE_VISION_ENDPOINT, AZURE_VISION_KEY, PORT, AWS_REGION
from app.providers.base import VisionFinding
from app.providers.azure_vision import AzureVision
from app.providers.aws_rekognition import AWSRekognition
from app.providers.google_vision import GoogleVision
from app.gpt.reasoner import build_prompt
from app.utils_http import read_image_or_raise
from app.cache_helpers import get_or_run

# --- FastAPI app setup ---
app = FastAPI(title="Alt Text Buddy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize providers and clients ---
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
vision = AzureVision(AZURE_VISION_ENDPOINT, AZURE_VISION_KEY)
aws = AWSRekognition(region_name=AWS_REGION)
google = GoogleVision()

# --- Cached runners ---
RUNNERS: Dict[str, Callable[[bytes], VisionFinding]] = {
    "azure": lambda b: vision.analyze_image(b),
    "aws":   lambda b: aws.analyze_image(b),
    "google": lambda b: google.analyze_image(b),
}

# --- Pydantic models ---
class AzureOutput(BaseModel):
    alt_text: str
    tags: list[str]
    provider: str = "azure"

class AWSOutput(BaseModel):
    alt_text: str
    tags: list[str]
    provider: str = "aws"

class GoogleOutput(BaseModel):
    alt_text: str
    tags: list[str]
    provider: str = "google"

class ReasonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    caption: Optional[str] = None  
    alt_text: Optional[str] = None
    tags: List[str] = []
    ocr_lines: List[str] = []
    use_case: str = "web"
    tone: str = "neutral"
    max_len: int = 160

class ReasonedOutput(BaseModel):
    alt_text: str
    explain_why: str
    tags: list[str]
    provider: str = "gpt"

class InspectOutput(BaseModel):
    alt_text: str
    tags: list[str]
    ocr_lines: list[str]
    provider: str

@app.get("/health")
def health():
    return {
        "ok": True,
        "providers": {
            "azure": bool(os.getenv("AZURE_VISION_KEY") and os.getenv("AZURE_VISION_ENDPOINT")),
            "aws":   bool(os.getenv("AWS_REGION")),
            "google": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
        },
        "model": OPENAI_MODEL,
        "version": "1.0.0",
    }

# --- Azure Vision endpoint ---
@app.post("/analyze-azure", response_model=AzureOutput)
async def analyze_azure(image: UploadFile = File(...)):
    b = await read_image_or_raise(image)
    try:
        f = get_or_run("azure", b, RUNNERS)
    except Exception as e:
        # redact details but keep a clear message
        raise HTTPException(status_code=502, detail=f"Azure Vision error: {type(e).__name__}")
    return {"alt_text":f.caption, "tags":f.tags, "provider":"azure"}

# --- AWS Rekognition endpoint ---
@app.post("/analyze-aws", response_model=AWSOutput)
async def analyze_aws(image: UploadFile = File(...)):
    b = await read_image_or_raise(image)
    try:
        f = get_or_run("aws", b, RUNNERS)
    except Exception as e:
        # redact details but keep a clear message
        raise HTTPException(status_code=502, detail=f"AWS Rekognition error: {type(e).__name__}")
    return {"alt_text":f.caption, "tags":f.tags, "provider":"aws"}

@app.post("/analyze-google", response_model=GoogleOutput)
async def analyze_google(image: UploadFile = File(...)):
    b = await read_image_or_raise(image)
    try:
        f = get_or_run("google", b, RUNNERS)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Google Vision error: {type(e).__name__}")
    return {"alt_text": f.caption, "tags": f.tags, "provider": "google"}

# --- Inspection endpoints for OCR + tags ---
@app.post("/inspect-azure", response_model=InspectOutput)
async def inspect_azure(image: UploadFile = File(...)):
    b = await read_image_or_raise(image)
    try:
        f = get_or_run("azure", b, RUNNERS)
    except Exception as e:
        # redact details but keep a clear message
        raise HTTPException(status_code=502, detail=f"Azure Vision error: {type(e).__name__}")
    return {
        "alt_text": f.caption,
        "tags": f.tags,
        "ocr_lines": f.ocr_lines,
        "provider": "azure",
    }

@app.post("/inspect-aws", response_model=InspectOutput)
async def inspect_aws(image: UploadFile = File(...)):
    b = await read_image_or_raise(image)
    try:
        f = get_or_run("aws", b, RUNNERS)
    except Exception as e:
        # redact details but keep a clear message
        raise HTTPException(status_code=502, detail=f"AWS Rekognition error: {type(e).__name__}")
    return {
        "alt_text": f.caption,
        "tags": f.tags,
        "ocr_lines": f.ocr_lines,
        "provider": "aws",
    }

@app.post("/inspect-google", response_model=InspectOutput)
async def inspect_google(image: UploadFile = File(...)):
    b = await read_image_or_raise(image)
    try:
        f = get_or_run("google", b, RUNNERS)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Google Vision error: {type(e).__name__}")
    return {
        "alt_text": f.caption,
        "tags": f.tags,
        "ocr_lines": f.ocr_lines,
        "provider": "google",
    }

# -- GPT Reasoning endpoint ---
@app.post("/reason", response_model=ReasonedOutput)
async def reason(payload: ReasonInput):
    cap = (payload.caption or payload.alt_text or "").strip()

    prompt = build_prompt(
        findings={"caption": cap,
                  "tags": payload.tags,
                  "ocr_lines": payload.ocr_lines,
                  },
        use_case=payload.use_case,
        tone=payload.tone,
        max_len=payload.max_len,
    )

    rsp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    try:
        data = json.loads(rsp.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError, IndexError):
        data = {
            "alt_text": (cap or "")[:payload.max_len],
            "explain_why": "",
            "tags": payload.tags,
        }

    return {
        "alt_text": data.get("alt_text", cap),
        "explain_why": data.get("explain_why", ""),
        "tags": data.get("tags", payload.tags),
        "provider": "gpt",
    }