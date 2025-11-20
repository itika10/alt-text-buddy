# Contributing

## Run locally
```bash
python -m venv venv
# Windows: venv\Scripts\activate   # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
streamlit run ui/app.py
