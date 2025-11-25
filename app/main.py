from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Callable
from dataclasses import asdict
import os, json, asyncio, logging
from openai import OpenAI
from app.config import AZURE_VISION_ENDPOINT, AZURE_VISION_KEY, AWS_REGION
from app.providers.base import VisionFinding
from app.providers.azure_vision import AzureVision
from app.providers.aws_rekognition import AWSRekognition
from app.providers.google_vision import GoogleVision
from app.metrics.token_usage import TokenUsage, cost_from_usage
from app.gpt.reasoner import build_prompt
from app.utils_http import read_image_or_raise
from app.cache_helpers import get_or_run

# --- FastAPI app setup ---
app = FastAPI(title="Alt Text Buddy", version="1.0.0")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize providers and clients ---
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

OPENAI_INPUT_PRICE_PER_1M_TOKENS = float(os.environ.get("OPENAI_INPUT_PRICE_PER_1M_TOKENS", "0.15"))
OPENAI_OUTPUT_PRICE_PER_1M_TOKENS = float(os.environ.get("OPENAI_OUTPUT_PRICE_PER_1M_TOKENS", "0.60"))

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
    raw_caption: Optional[str] = None
    llm_usage: Optional[dict] = None

# --- Pipeline models ---
class PipelineRaw(BaseModel):
    alt_text: str
    tags: list[str]
    ocr_lines: list[str]
    provider: str

class PipelineReasoned(BaseModel):
    alt_text: str
    explain_why: str
    tags: list[str]
    provider: str = "gpt"

class PipelineOut(BaseModel):
    results: dict[str, dict]  # { provider_id: {"raw": PipelineRaw, "reasoned": PipelineReasoned | None} }

@app.get("/health")
def health():
    return {
        "ok": True,
        "providers": {
            "azure_configured": bool(os.getenv("AZURE_VISION_KEY") and os.getenv("AZURE_VISION_ENDPOINT")),
            "aws_configured":   bool(os.getenv("AWS_REGION")),
            "google_configured": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
        },
        "model": OPENAI_MODEL,
        "version": "1.0.0",
    }

# --- Pipeline endpoint ---
@app.post("/pipeline", response_model=PipelineOut)
async def pipeline(
    image: UploadFile = File(...),
    providers: str = Form("azure,aws,google"),
    reason: bool = Form(False),
    use_case: str = Form("web"),
    tone: str = Form("neutral"),
    max_len: int = Form(160),
):
    b = await read_image_or_raise(image)

    seen = set()
    req = []

    for p in (providers or "").split(","):
        pid = p.strip().lower()
        if pid in RUNNERS and pid not in seen:
            seen.add(pid)
            req.append(pid)

    if not req:
        return {"results": {}}
    
    async def run_provider(pid: str):
        try:
            # Run CV provider via cache
            finding = await asyncio.to_thread(get_or_run, pid, b, RUNNERS)
            raw = PipelineRaw(
                alt_text=finding.caption,
                tags=finding.tags,
                ocr_lines=finding.ocr_lines,
                provider=pid,
            )

            # Optionally reason
            reasoned = None
            if reason:
                prompt = build_prompt(
                    findings={"caption": raw.alt_text, "tags": raw.tags, "ocr_lines": raw.ocr_lines},
                    use_case=use_case, tone=tone, max_len=max_len,
                )
                rsp = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )

                # --- Token + cost tracking (pipeline) ---
                usage = getattr(rsp, "usage", None)
                if usage is not None:
                    input_tokens = getattr(usage, "prompt_tokens", 0)
                    output_tokens = getattr(usage, "completion_tokens", 0)
                    total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens)

                    cost_usd = cost_from_usage(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        input_price_per_1k=OPENAI_INPUT_PRICE_PER_1M_TOKENS,
                        output_price_per_1k=OPENAI_OUTPUT_PRICE_PER_1M_TOKENS,
                    )

                    token_usage = TokenUsage(
                        provider="openai",
                        model=OPENAI_MODEL,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        cost_usd=cost_usd,
                        context="single_reasoner",
                    )

                    logger.info(f"Token usage for provider '{pid}': {token_usage}")
                    
                try:
                    data = json.loads(rsp.choices[0].message.content)
                except Exception:
                    data = {"alt_text": raw.alt_text, "explain_why": "", "tags": raw.tags}

                reasoned = PipelineReasoned(
                    alt_text=data.get("alt_text", raw.alt_text),
                    explain_why=data.get("explain_why", ""),
                    tags=data.get("tags", raw.tags),
                )
            return pid, {"raw": raw.model_dump(), "reasoned": (reasoned.model_dump() if reasoned else None)}   
        
        except Exception as e:
            # surface a per-provider error instead of failing the whole pipeline
            return pid, {"error": f"{type(e).__name__}: {str(e)[:200]}"}

    pairs = await asyncio.gather(*[run_provider(pid) for pid in req])
    return {"results": dict(pairs)}

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

    # --- Token + cost tracking (single /reason endpoint) ---
    llm_usage_dict = None
    
    usage = getattr(rsp, "usage", None)
    if usage is not None:
        input_tokens = getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "completion_tokens", 0)
        total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens)

        cost_usd = cost_from_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_price_per_1k=OPENAI_INPUT_PRICE_PER_1M_TOKENS,
            output_price_per_1k=OPENAI_OUTPUT_PRICE_PER_1M_TOKENS,
        )

        token_usage = TokenUsage(
            provider="openai",
            model=OPENAI_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            context="single_reasoner",
        )
        logger.info("Single /reason token usage: %s", token_usage)
        logger.info(f"Token cost input: {OPENAI_INPUT_PRICE_PER_1M_TOKENS}")
        logger.info (f"Token cost output: {OPENAI_OUTPUT_PRICE_PER_1M_TOKENS}")

        # Make it JSON serializable
        llm_usage_dict = asdict(token_usage)

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
        "raw_caption": cap,
        "llm_usage": llm_usage_dict,
    }