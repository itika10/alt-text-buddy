# Contributing

## Run locally
```
python -m venv venv
# Windows: venv\Scripts\activate   # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
streamlit run ui/app.py
```

## Branch & tag model
- main: per-provider version (released as vX.Y.Z-per-provider)
- feat/pipeline-only-cleanup: pipeline version (released as vX.Y.Z-pipeline)
- Use feature branches: feat/<topic>, fix/<topic>

## PR checklist
- black/ruff clean
- README updated if UI/endpoint changes
- Works with .env.example
- Screenshots updated if UI changes

