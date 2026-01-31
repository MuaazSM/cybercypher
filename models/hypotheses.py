from pydantic import BaseModel, Field, ConfigDict
from typing import List, Literal, Optional
from datetime import datetime
from uuid import UUID, uuid4


class Hypothesis(BaseModel):
    """
    A potential root cause hypothesis for an incident.
    
    Represents one theory about why an incident occurred,
    with evidence, counterevidence, and confidence scoring.
    """
    
    hypothesis_id: UUID = Field(default_factory=uuid4, description="Unique hypothesis ID")
    type: Literal["merchant_config", "migration_misstep", "platform_regression", "docs_gap"] = Field(
        description="Category of root cause"
    )
    claim: str = Field(description="Clear statement of the hypothesis")
    confidence: float = Field(
        description="Confidence score 0.0-1.0",
        ge=0.0,
        le=1.0
    )
    
    # Evidence supporting this hypothesis
    evidence: List[str] = Field(description="Supporting evidence items")
    counterevidence: List[str] = Field(description="Facts that argue against this hypothesis")
    unknowns: List[str] = Field(description="Missing information needed to validate")
    
    # RAG source references
    similar_past_incidents: List[str] = Field(default_factory=list, description="IDs of similar past incidents")
    relevant_docs: List[str] = Field(default_factory=list, description="Titles of relevant documentation")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hypothesis_id": "750e8400-e29b-41d4-a716-446655440030",
                "type": "migration_misstep",
                "claim": "Stage 2 merchants didn't complete webhook configuration step",
                "confidence": 0.85,
                "evidence": [
                    "All 17 affected merchants are in Stage 2",
                    "Signature: WEBHOOK::DELIVERY_FAIL indicates webhook delivery issue",
                    "Stage 2 guide requires webhook endpoint configuration",
                    "Rate is 7.3x baseline - indicates new misconfiguration, not gradual regression"
                ],
                "counterevidence": [
                    "Past incidents show most merchants complete this step correctly"
                ],
                "unknowns": [
                    "Were merchants provided clear step-by-step instructions?",
                    "Did any validation happen after merchant setup?"
                ],
                "similar_past_incidents": ["incident_001", "incident_042"],
                "relevant_docs": ["Stage-2-Webhook-Setup.md", "Common-Migration-Issues.md"]
            }
        }
    )


class AlternativeHypothesis(BaseModel):
    """
    Counter-hypothesis that challenges the primary explanation.
    
    Priority 6 Enhancement: Multi-Agent Debate / Intellectual Humility
    
    Represents alternative explanations that the AI intentionally generates
    to avoid confirmation bias and demonstrate intellectual humility.
    
    Example: If top hypothesis is "platform_regression", alternative might be
    "merchant_config" with reasoning about why we might be wrong.
    """
    
    alternative_id: UUID = Field(default_factory=uuid4, description="Unique alternative ID")
    type: Literal["merchant_config", "migration_misstep", "platform_regression", "docs_gap"] = Field(
        description="Category of alternative root cause"
    )
    claim: str = Field(description="Counter-claim challenging the primary hypothesis")
    plausibility: float = Field(
        description="Plausibility score 0.0-1.0 (typically lower than primary)",
        ge=0.0,
        le=1.0
    )
    
    # Evidence supporting the alternative explanation
    contradicting_evidence: List[str] = Field(
        description="Evidence from the same data that supports this alternative"
    )
    explanatory_power: str = Field(
        description="How well this alternative explains the observations"
    )
    
    # Comparative reasoning
    why_we_might_be_wrong: str = Field(
        description="Explicit reasoning about how our primary hypothesis could be incorrect"
    )
    why_primary_is_stronger: str = Field(
        description="Why the primary hypothesis is still more likely (for transparency)"
    )
    
    # What would validate this alternative
    what_would_prove_this: List[str] = Field(
        description="Evidence that would increase confidence in this alternative"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alternative_id": "850e8400-e29b-41d4-a716-446655440040",
                "type": "merchant_config",
                "claim": "Merchants misconfigured webhook URLs, not a migration guide issue",
                "plausibility": 0.35,
                "contradicting_evidence": [
                    "Even experienced technical merchants are affected",
                    "Multiple merchants failing at same time suggests common cause",
                    "Webhook URL format is clearly documented"
                ],
                "explanatory_power": "Could explain why only Stage 2 merchants are affected if they all use same setup flow",
                "why_we_might_be_wrong": "If merchants independently made the same mistake, it suggests the documentation is misleading them systematically - which would actually support the migration_misstep hypothesis",
                "why_primary_is_stronger": "17/17 merchants in Stage 2 suggests systematic issue with migration process, not independent merchant errors. Historical data shows merchants usually get this right.",
                "what_would_prove_this": [
                    "Merchant account inspection shows incorrect webhook URL format",
                    "Merchants confirm they didn't follow documentation exactly",
                    "Similar issues appearing in Stage 3/4 (different setup flows)"
                ]
            }
        }
    )


class RootCauseAnalysis(BaseModel):
    """
    Complete root cause analysis for an incident.
    
    Contains ranked hypotheses, recommended next steps,
    and metadata about the analysis process.
    
    Priority 6 Enhancement: Now includes alternative_explanations
    to demonstrate intellectual humility and adversarial thinking.
    """
    
    incident_id: UUID = Field(description="The incident being analyzed")
    analysis_timestamp: datetime = Field(description="When analysis was performed")
    
    # Hypotheses ranked by confidence
    hypotheses: List[Hypothesis] = Field(
        description="Root cause hypotheses ranked by confidence (highest first)"
    )
    
    # Priority 6: Alternative explanations (intellectual humility)
    alternative_explanations: List[AlternativeHypothesis] = Field(
        default_factory=list,
        description="Counter-hypotheses that challenge our primary explanation"
    )
    debate_summary: Optional[str] = Field(
        default=None,
        description="Summary of why primary hypothesis was chosen over alternatives"
    )
    
    # Recommendations
    recommended_next_steps: List[str] = Field(
        description="Suggested actions to validate top hypothesis or investigate further"
    )
    
    # Analysis metadata
    rag_sources_used: int = Field(
        description="Total number of RAG sources (past incidents + docs) used in analysis"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "603248b9-1bac-4639-9c51-e94ab2631a4d",
                "analysis_timestamp": "2026-01-31T15:15:00Z",
                "hypotheses": [
                    {
                        "hypothesis_id": "750e8400-e29b-41d4-a716-446655440030",
                        "type": "migration_misstep",
                        "claim": "Stage 2 webhook configuration incomplete",
                        "confidence": 0.85,
                        "evidence": ["All Stage 2", "Signature matches", "Rate spike typical of misconfiguration"],
                        "counterevidence": [],
                        "unknowns": ["Exact step merchants missed"],
                        "similar_past_incidents": ["incident_001"],
                        "relevant_docs": ["Stage-2-Setup.md"]
                    }
                ],
                "recommended_next_steps": [
                    "Review Stage 2 migration guide for webhook setup clarity",
                    "Check if merchants completed all required steps",
                    "Verify hypothesis with sample merchant account"
                ],
                "rag_sources_used": 3
            }
        }
    )
