## Alt-Text Buddy (Azure + GPT)

Generate concise, high-quality alt text for images. Compare **raw Azure Image Analysis** vs **Azure + GPT reasoning** via a Streamlit UI and FastAPI backend.

![UI Screenshot](screenshots/ui.png)
![Docs Screenshot](screenshots/docs_endpoints.png)

## Requirements

See [`requirements.txt`](./requirements.txt).  
Create and activate a virtual environment, then install:

```bash```
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

## Config
Create .env from the example and fill your keys:
cp .env.example .env

## Quick start

# Run backend
uvicorn app.main:app --reload --port 8000
- Health: http://localhost:8000/health
- Docs:   http://localhost:8000/docs

# Run UI
streamlit run ui/app.py
- In the sidebar, set API base: http://localhost:8000

## Endpoints
- POST /analyze → { alt_text, tags, provider }
- POST /generate → { alt_text, explain_why, tags, provider }
- POST /inspect → { alt_text, caption, tags, ocr_lines, provider }

# Convention: public responses use alt_text. The internal Azure caption is kept as caption and only exposed via /inspect for debugging.

## Project structure
alt-text-buddy/
├─ app/
│  ├─ __init__.py
│  ├─ main.py              # FastAPI app + endpoints
│  ├─ config.py            # env loading
│  ├─ cache.py             # TTL cache for findings (sha256-keyed)
│  ├─ utils.py             # helpers (image sha256)
│  ├─ providers/
│  │  ├─ __init__.py
│  │  ├─ base.py           # VisionFinding dataclass
│  │  ├─ azure_vision.py   # Azure Image Analysis adapter
│  │  ├─ aws_rekognition.py # (stub/coming soon)
│  │  └─ google_vision.py   # (stub/coming soon)
│  └─ gpt/
│     ├─ __init__.py
│     └─ reasoner.py       # prompt builder for GPT
├─ ui/
│  ├─ __init__.py
│  ├─ app.py               # Streamlit UI
│  ├─ components.py        # render helpers
│  └─ metrics.py           # phrase-aware metrics
├─ screenshots/
│  ├─ ui.png
│  └─ docs_endpoints.png
├─ requirements.txt
├─ .env.example
├─ LICENSE
└─ README.md

## Notes
- Caching by image hash: backend caches Azure findings in-memory (TTLCache) keyed by SHA-256 of the image bytes to reduce cost/latency across endpoints.
- Consistent naming: outward-facing JSON uses alt_text; Azure’s raw caption remains internal and is shown only in /inspect.
- Metrics: UI computes:
  - character/word counts
  - phrase-aware tag hit-rate (handles multi-word tags like “cream & onion”)
  - OCR hit-rate (overlap between Azure READ text and alt text)

## Roadmap
✅ Azure Image Analysis + GPT reasoning (this repo)
⏩ Add providers and compare in the same UI:
  - AWS Rekognition (labels + text)
  - Google Vision (labels + text detection)
  - Local LLM (e.g., LLaVA via Ollama)
⏩ Sidebar metric pickers & weighted scoring
⏩ One-shot /pipeline endpoint returning all provider results at once
⏩ Download results (JSON/CSV) for batch evaluation

## License

MIT – see [LICENSE](./LICENSE).