from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class VisionFinding:
    caption: str
    tags: List[str]
    ocr_lines: List[str]
    meta: Dict[str, Any]

