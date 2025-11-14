from cachetools import TTLCache

# keep last 256 images for 30 minutes
FINDINGS_CACHE = TTLCache(maxsize=256, ttl=1800)
