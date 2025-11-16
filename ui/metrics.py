import re
import streamlit as st
from typing import Iterable, List, Set

# Common stopwords
STOPWORDS: Set[str] = {
    "a","an","the","and","or","in","on","of","with","for","to","from","by","at","as"
}

def normalize(text: str) -> str:
    """
    Lowercase; normalize symbols (& -> 'and'); collapse whitespace; keep letters/numbers.
    """
    if not text:
        return ""
    t = text.lower()
    t = t.replace("&", " and ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def tokenize(text: str) -> List[str]:
    """Unigram tokens with stopwords removed."""
    t = normalize(text)
    toks = t.split()
    return [w for w in toks if w not in STOPWORDS]

def make_ngrams(tokens: List[str], n: int = 2) -> Set[str]:
    """
    Returns set of 1-grams and up to n-grams:
      e.g., ["cream","and","onion"] -> {"cream","onion","cream and","and onion","cream and onion"}
    """
    toks = tokens
    grams = set(toks)
    for k in range(2, n + 1):
        grams.update(" ".join(toks[i:i+k]) for i in range(0, len(toks) - k + 1))
    return grams

def phrase_hit_rate(tag_phrases: Iterable[str], alt_tokens: List[str]) -> float:
    """
    Count a tag phrase as 'hit' if all its content words appear in the alt text
    (order not required), OR the phrase exists as an n-gram.
    """
    if not tag_phrases:
        return 0.0
    alt_set = set(alt_tokens)
    alt_ngrams = make_ngrams(alt_tokens, n=3)

    hits, total = 0, 0
    for phrase in tag_phrases:
        total += 1
        p_norm = normalize(phrase)
        if not p_norm:
            continue
        p_tokens = [w for w in p_norm.split() if w not in STOPWORDS]

        # exact phrase match via n-grams OR all tokens present (set subset)
        if (p_norm in alt_ngrams) or set(p_tokens).issubset(alt_set):
            hits += 1

    return round(100.0 * hits / total, 1)

def compute_metrics(alt_text: str, tags: list[str], ocr_lines: list[str]):
    """
    - chars / words
    - tag_hit_rate_% : phrase-aware (handles 'cream & onion' and 'nutty palate')
    - ocr_hit_rate_% : overlap of OCR tokens vs alt tokens
    """
    alt_tokens = tokenize(alt_text)
    # phrase-aware tag hit (don’t split tags into naive words)
    tag_hit = phrase_hit_rate(tags, alt_tokens)

    # OCR tokens: build a light vocabulary and ignore short words/stopwords
    ocr_text = " ".join(ocr_lines[:80])
    ocr_tokens_all = tokenize(ocr_text)
    ocr_tokens = [t for t in ocr_tokens_all if len(t) >= 3]
    # treat OCR hit as token-level recall of the top-N tokens
    ocr_ref = set(ocr_tokens[:30])
    ocr_hit = round(100.0 * len(ocr_ref & set(alt_tokens)) / (len(ocr_ref) or 1), 1)

    return {
        "chars": len(alt_text or ""),
        "words": len(alt_tokens),
        "tag_hit_rate_%": tag_hit,
        "ocr_hit_rate_%": ocr_hit,
    }

def render_metrics(title: str, m: dict):
    st.caption(
        f"**{title}** — chars: {m['chars']} · words: {m['words']} · "
        f"tag hit: {m['tag_hit_rate_%']}% · OCR hit: {m['ocr_hit_rate_%']}%"
    )
