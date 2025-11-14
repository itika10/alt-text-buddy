from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json
from openai import OpenAI
from app.config import AZURE_VISION_ENDPOINT, AZURE_VISION_KEY, PORT
from app.providers.azure_vision import AzureVision
from app.gpt.reasoner import build_prompt
from app.cache import FINDINGS_CACHE
from app.utils import image_sha256

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

app = FastAPI(title="Alt Text Buddy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

vision = AzureVision(AZURE_VISION_ENDPOINT, AZURE_VISION_KEY)

def get_findings(image_bytes: bytes):
    key = image_sha256(image_bytes)
    if key in FINDINGS_CACHE:
        return FINDINGS_CACHE[key]
    findings = vision.analyze_image(image_bytes)
    FINDINGS_CACHE[key] = findings
    return findings

class AzureOutput(BaseModel):
    alt_text: str
    tags: list[str]
    provider: str = "azure"

class ReasonedOutput(BaseModel):
    alt_text: str
    explain_why: str
    tags: list[str]
    provider: str = "azure+gpt"

class InspectOutput(BaseModel):
    alt_text: str
    tags: list[str]
    ocr_lines: list[str]
    provider: str = "azure"

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/analyze", response_model=AzureOutput)
async def generate_alt_text(image: UploadFile = File(...)):
    image_bytes = await image.read()
    findings = get_findings(image_bytes)
    return {"alt_text":findings.caption, "tags":findings.tags, "provider":"azure"}

@app.post("/generate", response_model=ReasonedOutput)
async def generate_reasoned_alt_text(
    image: UploadFile = File(...),
    use_case: str = Form("web"),
    tone: str = Form("neutral"),
    max_len: int = Form(160),
):
    image_bytes = await image.read()
    findings = get_findings(image_bytes)

    prompt = build_prompt(
        findings={"caption": findings.caption,
                  "tags": findings.tags,
                  "ocr_lines": findings.ocr_lines,
                  },
        use_case=use_case,
        tone=tone,
        max_len=max_len,
    )

    rsp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = rsp.choices[0].message.content

    data = json.loads(content)

    return {
        "alt_text": data.get("alt_text", findings.caption),
        "explain_why": data.get("explain_why", ""),
        "tags": data.get("tags", findings.tags),
        "provider": "azure+gpt",
    }

@app.post("/inspect", response_model=InspectOutput)
async def inspect_image(image: UploadFile = File(...)):
    image_bytes = await image.read()
    findings = get_findings(image_bytes)
    return {
        "alt_text": findings.caption,
        "tags": findings.tags,
        "ocr_lines": findings.ocr_lines,
        "provider": "azure",
    }