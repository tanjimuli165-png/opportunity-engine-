from collections import Counter
from typing import Dict, List
from app.database.models import Evidence

GAP_TERMS = {"confusing": "clarity", "outdated": "freshness", "expensive": "affordability", "generic": "specificity", "template": "implementation", "overwhelming": "simplicity", "missing": "coverage", "slow": "speed", "complex": "simplicity"}


def detect_gaps(evidence: List[Evidence]) -> Dict[str, object]:
    counts = Counter()
    examples = {}
    for item in evidence:
        text = f"{item.title} {item.text}".lower()
        for term, gap in GAP_TERMS.items():
            if term in text:
                counts[gap] += 1
                examples.setdefault(gap, item.text[:240])
    if not counts:
        counts.update({"specificity": 1, "implementation": 1, "clarity": 1})
        examples.update({"specificity": "Existing results may not reflect the user's exact context.", "implementation": "A step-by-step system can close the action gap.", "clarity": "A concise workflow can reduce research overload."})
    return {"gaps": [{"gap": gap, "mentions": count, "example": examples[gap]} for gap, count in counts.most_common()], "score": round(min(1.0, sum(counts.values()) / max(4, len(evidence))), 2)}
