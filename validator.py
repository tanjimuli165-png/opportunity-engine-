from typing import Dict


def validate(problem_fit: float, wtp: float, competition_gap: float, evidence_strength: float) -> Dict[str, object]:
    score = round((problem_fit * 0.35 + wtp * 0.2 + competition_gap * 0.2 + evidence_strength * 0.25) * 100)
    label = "Strong candidate" if score >= 70 else "Promising, needs validation" if score >= 50 else "Exploratory"
    return {"score": score, "label": label, "signals": {"problem_fit": problem_fit, "willingness_to_pay": wtp, "competition_gap": competition_gap, "evidence_strength": evidence_strength}}
