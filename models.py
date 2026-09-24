from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Evidence(BaseModel):
    source: str
    title: str
    text: str
    url: str = ""
    published_at: Optional[str] = None
    score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProblemSignal(BaseModel):
    problem: str
    customer_language: List[str] = Field(default_factory=list)
    frequency: int = 1
    evidence_urls: List[str] = Field(default_factory=list)
    urgency: float = 0.0
    objection_bucket: str = "Complexity/Confusion Friction"


class Opportunity(BaseModel):
    name: str
    audience: str
    promise: str
    format: List[str]
    problem_fit: float
    willingness_to_pay: float
    competition_gap: float
    evidence_strength: float
    validation_score: float
    pricing: Dict[str, str]
    pricing_rationale: str = ""
    value_hook: str = ""
    objection_bucket: str = "Complexity/Confusion Friction"
    components: List[str]
    differentiation: List[str]
    risks: List[str]
    next_steps: List[str]


class MarketplaceGap(BaseModel):
    marketplace: str
    title: str
    url: str = ""
    price: str = "Not found"
    format: str = "Unknown"
    rating: str = "Not found"
    review_insights: List[str] = Field(default_factory=list)
    gap_signal: str = "Requires validation"


class Report(BaseModel):
    id: str
    topic: str
    user_id: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    evidence: List[Evidence] = Field(default_factory=list)
    problems: List[ProblemSignal] = Field(default_factory=list)
    opportunities: List[Opportunity] = Field(default_factory=list)
    objection_matrix: Dict[str, List[str]] = Field(default_factory=dict)
    sales_hooks: List[str] = Field(default_factory=list)
    marketplace_gaps: List[MarketplaceGap] = Field(default_factory=list)
    product_blueprint: Dict[str, Any] = Field(default_factory=dict)
    launch_kit: Dict[str, Any] = Field(default_factory=dict)
    executive_summary: str = ""
    collection_notes: List[str] = Field(default_factory=list)
