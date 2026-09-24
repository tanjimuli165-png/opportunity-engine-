from typing import Dict, List

from app.database.models import Opportunity, ProblemSignal
from app.product.validator import validate
from app.processors.objection_framework import classify_objection, enrich_opportunity, pricing_rationale, value_hook

ARCHITECT_NAMES = ["Clarity Kit", "Action System", "Prompt & Template Lab", "Decision Playbook", "Workflow Sprint"]


def architect_opportunities(topic: str, problems: List[ProblemSignal], spending: Dict, gaps: Dict, evidence_count: int) -> List[Opportunity]:
    opportunities = []
    base_gap = min(1.0, 0.35 + gaps.get("score", 0.2))
    wtp = min(1.0, 0.35 + spending.get("score", 0.0))
    evidence_strength = min(1.0, evidence_count / 20)
    for idx, problem in enumerate(problems[:5]):
        bucket = problem.objection_bucket or classify_objection(problem.problem)
        problem.objection_bucket = bucket
        fit = min(1.0, 0.45 + problem.urgency * 0.35 + min(problem.frequency, 5) * 0.04)
        result = validate(fit, wtp, base_gap, evidence_strength)
        opportunity = Opportunity(
            name=f"{topic.title()} {ARCHITECT_NAMES[idx]}",
            audience=f"People working on {topic} who report: {problem.problem.lower()}",
            promise=f"Move from {problem.problem.lower()} to a repeatable next step with less research and rework.",
            format=["step-by-step guide", "Notion or spreadsheet workspace", "prompt library", "checklists"],
            problem_fit=round(fit, 2),
            willingness_to_pay=round(wtp, 2),
            competition_gap=round(base_gap, 2),
            evidence_strength=round(evidence_strength, 2),
            validation_score=result["score"],
            pricing={"starter": "$19", "core": "$29", "premium": "$49"},
            pricing_rationale=pricing_rationale(problem, bucket),
            value_hook=value_hook(problem, bucket),
            objection_bucket=bucket,
            components=["Quick-start diagnostic", "Modular implementation workflow", "Examples for three common scenarios", "Progress tracker and review checklist"],
            differentiation=[f"Built around the recurring customer language: {problem.problem.lower()}", "Short path from insight to implementation", "Evidence links included for every major assumption"],
            risks=["Heuristic extraction can miss nuance or sarcasm", "Price signals are directional rather than a demand forecast", "Search coverage depends on public endpoint availability"],
            next_steps=["Interview five people in the target audience", "Offer a paid pilot with the core workflow", "Measure activation, completion, and refund objections", result["label"]],
        )
        opportunities.append(enrich_opportunity(opportunity, problem))
    return sorted(opportunities, key=lambda item: item.validation_score, reverse=True)
