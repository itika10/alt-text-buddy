from typing import Callable, Dict, Any
from .cache import FINDINGS_CACHE
from .utils import image_sha256

Runner = Callable[[bytes], Any]

def _cache_key(image_bytes: bytes, provider: str) -> str:
    return f"{image_sha256(image_bytes)}::{provider}"

def cache_get(image_bytes: bytes, provider: str):
    return FINDINGS_CACHE.get(_cache_key(image_bytes, provider))

def cache_put(image_bytes: bytes, provider: str, value: Any):
    FINDINGS_CACHE[_cache_key(image_bytes, provider)] = value
    return value

def get_or_run(provider: str, image_bytes: bytes, runners: Dict[str, Runner]):
    """
    Generic cached runner:
      - provider: key like 'azure', 'aws', 'google'
      - image_bytes: the uploaded image
      - runners: dict mapping provider -> function(bytes) -> VisionFinding
    """
    hit = cache_get(image_bytes, provider)
    if hit is not None:
        return hit
    if provider not in runners:
        raise ValueError(f"Unknown provider: {provider}")
    result = runners[provider](image_bytes)
    return cache_put(image_bytes, provider, result)