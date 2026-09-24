from collections import defaultdict
import re
from typing import List

from app.database.models import Evidence, ProblemSignal

# Terms that commonly introduce an explicit pain point, complaint, workaround, or unmet need.
PROBLEM_TERMS = (
    "how do i", "can't", "cannot", "struggle", "problem", "issue", "help", "confused",
    "difficult", "expensive", "waste", "wasting", "time-consuming", "need", "looking for",
    "wish", "frustrat", "annoy", "hate", "broken", " workaround", "instead", "manually",
    "keeps failing", "doesn't work", "does not work", "hard to", "unable to", "pain point",
)
FIRST_PERSON = re.compile(r"\b(i|we|my|our|me)\b", re.I)
STOP = {"this", "that", "with", "from", "have", "what", "when", "where", "which", "about", "there", "their", "would", "could", "should", "because", "really", "just"}


def _sentences(text: str) -> List[str]:
    # Split on actual whitespace after punctuation/newlines; keep the user's wording intact.
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|[\n\r]+", text or "") if part.strip()]


def _is_explicit_pain(sentence: str) -> bool:
    low = sentence.lower()
    has_term = any(term.strip() in low for term in PROBLEM_TERMS)
    has_first_person = bool(FIRST_PERSON.search(sentence))
    complaint_shape = any(marker in low for marker in ("but ", "however", "yet ", "tried ", "currently ", "every time ", "spent "))
    return len(sentence) >= 35 and has_term and (has_first_person or complaint_shape or "problem" in low or "issue" in low)


def _group_key(sentence: str) -> str:
    words = [w for w in re.findall(r"[a-zA-Z]{4,}", sentence.lower()) if w not in STOP]
    return " ".join(words[:7]) or sentence[:80].lower()


def mine_problems(evidence: List[Evidence], limit: int = 8) -> List[ProblemSignal]:
    """Extract only verbatim, explicit pain language; return [] when evidence is not explicit."""
    candidates = []
    for item in evidence:
        if item.metadata.get("error"):
            continue
        for sentence in _sentences(item.text):
            if _is_explicit_pain(sentence):
                candidates.append((sentence, item.url))

    groups = defaultdict(list)
    for text, url in candidates:
        groups[_group_key(text)].append((text, url))

    ranked = sorted(groups.items(), key=lambda pair: (len(pair[1]), max(len(x[0]) for x in pair[1])), reverse=True)[:limit]
    signals = []
    for _, items in ranked:
        exact_language = []
        for text, _ in items:
            if text not in exact_language:
                exact_language.append(text)
        # The label is a verbatim customer sentence, never a synthesized generic claim.
        label = exact_language[0]
        signals.append(
            ProblemSignal(
                problem=label,
                customer_language=exact_language[:3],
                frequency=len(items),
                evidence_urls=[url for _, url in items if url][:5],
                urgency=min(1.0, len(items) / 5),
            )
        )
    return signals


__all__ = ["mine_problems"]
