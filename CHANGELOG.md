# Changelog

## [v1.0.0-pipeline] - 2025-03-21
### Added
- One-shot `/pipeline` endpoint + parallel provider runs
- UI hooked to pipeline with optional GPT refine
- Per-provider error isolation in the pipeline response

## [v1.0.0-per-provider] - 2025-03-21
### Added
- Azure, AWS, Google adapters (+ OCR)
- `/reason` endpoint (GPT refine)
- Streamlit UI (per-provider runs, metrics, debug)
