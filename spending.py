import re
from typing import Dict, List
from app.database.models import Evidence

PRICE_PATTERNS = [r"\$\s?\d+(?:\.\d+)?", r"\b\d+\s?(?:usd|dollars|per month|/mo)\b", r"(?:buy|paid|pay|cost|price|budget|worth|invest)"]


def analyze_spending(evidence: List[Evidence]) -> Dict[str, object]:
    matches = []
    for item in evidence:
        text = f"{item.title} {item.text}"
        if any(re.search(pattern, text, re.I) for pattern in PRICE_PATTERNS):
            matches.append({"source": item.source, "text": text[:350], "url": item.url})
    signal = min(1.0, (len(matches) / max(3, len(evidence))) * 2.0)
    return {"score": round(signal, 2), "signals": matches[:10], "interpretation": "Direct price or purchase language was detected." if matches else "No direct price language was detected; validate pricing with interviews or a pre-sale."}
