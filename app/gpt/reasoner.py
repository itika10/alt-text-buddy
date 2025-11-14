from typing import Dict

ALT_GUIDE = (
    "Write concise, descriptive alt text for someone who cannot see the image. "
    "Do not start with 'Image of'. Avoid filler words like 'photo' or 'picture'. "
    "Prefer exact product names, brand text, claims, and flavor from OCR when present."
)

def build_prompt(findings: Dict, use_case: str, tone: str, max_len: int) -> str:
    return f"""
You are an accessibility writer. {ALT_GUIDE}
Use case: {use_case}. Tone: {tone}. Max length: {max_len} characters.

Findings (structured):
- Caption hint: {findings.get('caption')}
- Tags: {findings.get('tags')}
- OCR lines (highest-confidence first): {findings.get('ocr_lines')}

Return JSON with keys:
- alt_text: a single sentence <= {max_len} chars
- explain_why: 1-2 sentences explaining why the image matters in the given use case
- tags: 3-8 short tags
"""