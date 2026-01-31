from typing import List, Optional
from sqlalchemy.orm import Session
from models.incidents import Incident
from models.hypotheses import Hypothesis, RootCauseAnalysis
from db.models import IncidentDB, IncidentHypothesisDB, CleanEventDB, IncidentClusterDB
from tools.llm_router import LLMRouter
from tools.knowledge_base import KnowledgeBase
from uuid import uuid4
from datetime import datetime
import json
import logging
import re
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Pydantic models for structured LLM output parsing
class HypothesisResponse(BaseModel):
    """Structured hypothesis from LLM."""
    type: str = Field(description="Type: merchant_config, migration_misstep, platform_regression, or docs_gap")
    claim: str = Field(description="Main claim of the hypothesis")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")
    evidence: List[str] = Field(description="Supporting evidence points")
    counterevidence: List[str] = Field(default_factory=list, description="Counter-evidence or limitations")
    unknowns: List[str] = Field(default_factory=list, description="Unknown factors to investigate")


class HypothesesResponse(BaseModel):
    """Structured response containing multiple hypotheses."""
    hypotheses: List[HypothesisResponse] = Field(description="List of ranked hypotheses by confidence")


class RootCauseAnalystAgent:
    """
    Root cause analysis agent with RAG enhancement.
    
    Responsibilities:
    - Gather evidence from incident cluster and sample events
    - Retrieve similar past incidents via RAG
    - Retrieve relevant migration documentation via RAG
    - Use LLM to generate ranked root cause hypotheses
    - Score hypotheses with confidence (0.0-1.0)
    - Store results in database for approval workflow
    
    Hypothesis types:
    - merchant_config: Merchant misconfigured something
    - migration_misstep: Migration process/guide issue
    - platform_regression: Platform bug or regression
    - docs_gap: Documentation unclear/missing
    """
    
    def __init__(self, llm_router: LLMRouter, knowledge_base: KnowledgeBase):
        """
        Initialize root cause analyst.
        
        Args:
            llm_router: LLMRouter for LLM access
            knowledge_base: KnowledgeBase for RAG
        """
        self.llm = llm_router
        self.kb = knowledge_base
        
        logger.info("[RootCauseAnalystAgent] Initialized with LLM router and knowledge base")
    
    def analyze_root_cause(self, incident: Incident, db: Session) -> RootCauseAnalysis:
        """
        Perform root cause analysis with RAG enhancement.
        
        Pipeline:
        1. Gather evidence from incident cluster
        2. Retrieve similar past incidents via RAG
        3. Retrieve relevant documentation via RAG
        4. Generate hypotheses using LLM + RAG context
        5. Store hypotheses in database
        
        Args:
            incident: Incident to analyze
            db: SQLAlchemy session
        
        Returns:
            RootCauseAnalysis with ranked hypotheses
        """
        logger.info(f"[RootCauseAnalystAgent] Analyzing incident: {incident.title}")
        
        # Step 1: Gather evidence
        logger.debug("[RootCauseAnalystAgent] Gathering evidence...")
        evidence_bundle = self._gather_evidence(incident, db)
        logger.debug(f"[RootCauseAnalystAgent] Gathered evidence with {len(evidence_bundle['sample_events'])} sample events")
        
        # Step 2: RAG retrieval - similar past incidents
        logger.debug("[RootCauseAnalystAgent] Retrieving similar past incidents via RAG...")
        past_incidents = self._retrieve_similar_incidents(incident)
        logger.info(f"[RootCauseAnalystAgent] Retrieved {len(past_incidents)} similar past incidents")
        
        # Step 3: RAG retrieval - relevant documentation
        logger.debug("[RootCauseAnalystAgent] Retrieving relevant migration documentation...")
        relevant_docs = self._retrieve_relevant_docs(incident, evidence_bundle)
        logger.info(f"[RootCauseAnalystAgent] Retrieved {len(relevant_docs)} relevant documentation")
        
        # Step 4: Generate hypotheses using LLM
        logger.debug("[RootCauseAnalystAgent] Generating hypotheses via LLM...")
        hypotheses = self._generate_hypotheses(
            incident=incident,
            evidence=evidence_bundle,
            past_incidents=past_incidents,
            relevant_docs=relevant_docs
        )
        logger.info(f"[RootCauseAnalystAgent] Generated {len(hypotheses)} hypotheses")
        
        # Step 5: Store hypotheses in database
        self._store_hypotheses(hypotheses, incident.incident_id, db)
        
        # Create analysis result
        analysis = RootCauseAnalysis(
            incident_id=incident.incident_id,
            analysis_timestamp=datetime.utcnow(),
            hypotheses=hypotheses,
            recommended_next_steps=self._generate_next_steps(hypotheses, incident),
            rag_sources_used=len(past_incidents) + len(relevant_docs)
        )
        
        logger.info(f"[RootCauseAnalystAgent] Analysis complete: {len(analysis.hypotheses)} hypotheses, {analysis.rag_sources_used} RAG sources")
        return analysis
    
    def _gather_evidence(self, incident: Incident, db: Session) -> dict:
        """
        Collect all evidence related to the incident.
        
        Gathers:
        - Cluster statistics
        - Stage and component distributions
        - Sample events with context
        - Business impact assessment
        
        Args:
            incident: Incident to gather evidence for
            db: SQLAlchemy session
        
        Returns:
            Dictionary with comprehensive evidence bundle
        """
        # Get the cluster
        cluster = db.query(IncidentClusterDB).filter(
            IncidentClusterDB.cluster_id == incident.cluster_id
        ).first()
        
        if not cluster:
            logger.warning(f"[RootCauseAnalystAgent] Cluster not found: {incident.cluster_id}")
            return {}
        
        # Get sample events for detailed inspection
        sample_events = db.query(CleanEventDB).filter(
            CleanEventDB.signature == cluster.primary_signature
        ).limit(10).all()
        
        evidence = {
            "signature": cluster.primary_signature,
            "merchant_count": cluster.merchant_count,
            "event_count": cluster.event_count,
            "rate": cluster.rate_per_hour,
            "baseline": cluster.baseline_rate,
            "spike_factor": cluster.rate_per_hour / max(cluster.baseline_rate, 0.1),
            "trend": cluster.trend,
            "stage_distribution": json.loads(cluster.stage_distribution),
            "component_distribution": json.loads(cluster.component_distribution),
            "sample_events": [
                {
                    "merchant_id": e.merchant_id,
                    "stage": e.migration_stage,
                    "component": e.component,
                    "error_code": e.error_code,
                    "severity": e.severity_hint,
                    "summary": e.raw_text_summary
                }
                for e in sample_events
            ],
            "impacts_checkout": incident.impacts_checkout,
            "impacts_revenue": incident.impacts_revenue,
            "affected_merchants": incident.affected_merchants[:5]  # Top 5 for context
        }
        
        logger.debug(f"[RootCauseAnalystAgent] Evidence: {evidence['merchant_count']} merchants, {evidence['event_count']} events, {evidence['spike_factor']:.1f}x spike")
        return evidence
    
    def _retrieve_similar_incidents(self, incident: Incident) -> List[dict]:
        """
        RAG: Retrieve similar past incidents.
        
        Searches knowledge base for incidents with similar patterns,
        limited to resolved incidents for learning from solutions.
        
        Args:
            incident: Current incident
        
        Returns:
            List of similar past incidents
        """
        query = f"{incident.title} incident resolution"
        
        try:
            results = self.kb.search(
                query=query,
                k=5,
                filter_by={"type": "incident", "status": "resolved"}
            )
            
            past_incidents = []
            for doc in results:
                past_incidents.append({
                    "content": doc.page_content,
                    "incident_id": doc.metadata.get("incident_id", "unknown"),
                    "title": doc.metadata.get("title", "unknown"),
                    "outcome": doc.metadata.get("outcome", "resolved")
                })
            
            logger.debug(f"[RootCauseAnalystAgent] RAG: Found {len(past_incidents)} similar past incidents")
            return past_incidents
        
        except Exception as e:
            logger.warning(f"[RootCauseAnalystAgent] RAG retrieval failed: {e}")
            return []
    
    def _retrieve_relevant_docs(self, incident: Incident, evidence: dict) -> List[dict]:
        """
        RAG: Retrieve relevant migration documentation.
        
        Searches for documentation related to affected stages and components.
        
        Args:
            incident: Current incident
            evidence: Evidence bundle with stage distribution
        
        Returns:
            List of relevant documentation
        """
        # Extract dominant stage from evidence
        stage_dist = evidence.get("stage_distribution", {})
        dominant_stage = max(stage_dist.items(), key=lambda x: x[1])[0] if stage_dist else 1
        
        # Build query from incident and evidence
        component = evidence.get("signature", "").split("::")[0]
        query = f"Stage {dominant_stage} {component} migration setup configuration"
        
        try:
            results = self.kb.search(
                query=query,
                k=5,
                filter_by={"type": "migration_guide"}
            )
            
            docs = []
            for doc in results:
                docs.append({
                    "content": doc.page_content,
                    "title": doc.metadata.get("doc_title", "unknown"),
                    "stage": doc.metadata.get("stage", 0)
                })
            
            logger.debug(f"[RootCauseAnalystAgent] RAG: Found {len(docs)} relevant migration guides")
            return docs
        
        except Exception as e:
            logger.warning(f"[RootCauseAnalystAgent] Doc retrieval failed: {e}")
            return []
    
    def _generate_hypotheses(
        self,
        incident: Incident,
        evidence: dict,
        past_incidents: List[dict],
        relevant_docs: List[dict]
    ) -> List[Hypothesis]:
        """
        Use LLM with structured output to generate ranked hypotheses.
        
        Uses RAG context to enhance hypothesis generation with:
        - Similar historical incidents
        - Relevant migration documentation
        - Past resolutions
        
        Args:
            incident: Incident being analyzed
            evidence: Evidence bundle
            past_incidents: Similar past incidents from RAG
            relevant_docs: Relevant documentation from RAG
        
        Returns:
            List of Hypothesis objects ranked by confidence
        """
        # Format context from RAG
        past_context = "\n\n".join([
            f"Past Incident: {inc['incident_id']}\n{inc['content']}"
            for inc in past_incidents[:3]
        ]) if past_incidents else "No similar past incidents found."
        
        docs_context = "\n\n".join([
            f"Documentation: {doc['title']}\n{doc['content']}"
            for doc in relevant_docs[:3]
        ]) if relevant_docs else "No relevant documentation found."
        
        system_prompt = """You are an expert root cause analyst for a SaaS e-commerce platform migration.
Analyze incidents and generate ranked hypotheses about root causes.

You MUST classify each cause into exactly ONE of these 4 categories:
1. merchant_config - Merchant misconfigured their setup
2. migration_misstep - Migration process/guide has an issue
3. platform_regression - Platform bug or regression
4. docs_gap - Documentation is unclear or missing

For each hypothesis:
- Provide a clear, specific claim
- Rate confidence 0.0-1.0 based on evidence strength (higher is more confident)
- List 2-3 supporting evidence items
- List 0-2 counterevidence items if any
- List 1-2 unknowns that need investigation

Return 2-4 hypotheses ranked by confidence (highest first).
Emphasize evidence quality over quantity in confidence scoring.
"""
        
        user_prompt = f"""
Analyze this incident for root cause:

INCIDENT:
- Title: {incident.title}
- Severity: {incident.severity}
- Status: {incident.status}

EVIDENCE:
- Signature: {evidence.get('signature', 'unknown')}
- Affected Merchants: {evidence.get('merchant_count', 0)}
- Event Count: {evidence.get('event_count', 0)}
- Event Rate: {evidence.get('rate', 0):.1f}/hr (baseline: {evidence.get('baseline', 0):.1f}/hr)
- Spike Factor: {evidence.get('spike_factor', 0):.1f}x baseline
- Trend: {evidence.get('trend', 'unknown')}
- Stage Distribution: {evidence.get('stage_distribution', {})}
- Component Distribution: {evidence.get('component_distribution', {})}
- Impacts Checkout: {evidence.get('impacts_checkout', False)}
- Impacts Revenue: {evidence.get('impacts_revenue', False)}

SAMPLE EVENTS:
{json.dumps(evidence.get('sample_events', [])[:2], indent=2)}

HISTORICAL CONTEXT (Similar Past Incidents):
{past_context}

RELEVANT DOCUMENTATION:
{docs_context}

Generate 2-4 ranked root cause hypotheses.
Focus on the most likely causes given the evidence and context.
Return hypotheses ranked by confidence (highest first).
"""
        
        logger.debug("[RootCauseAnalystAgent] Invoking LLM for hypothesis generation...")
        
        # Create format instructions for JSON output
        format_instructions = """Respond ONLY with valid JSON in this format:
{
  "hypotheses": [
    {
      "type": "merchant_config|migration_misstep|platform_regression|docs_gap",
      "claim": "main hypothesis claim",
      "confidence": 0.85,
      "evidence": ["evidence point 1", "evidence point 2"],
      "counterevidence": ["counter point"],
      "unknowns": ["unknown factor"]
    }
  ]
}"""
        
        # Add format instructions to prompt
        full_prompt = f"""{user_prompt}

{format_instructions}"""
        
        # Use LLM to get validated hypotheses
        response_text = self.llm.invoke(
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.5,
            max_tokens=2000
        )
        
        # Parse response into hypotheses
        hypotheses = self._parse_hypothesis_response(response_text, past_incidents, relevant_docs)
        
        if hypotheses:
            logger.info(f"[RootCauseAnalystAgent] LLM generated {len(hypotheses)} hypotheses")
            return hypotheses
        else:
            logger.error(f"[RootCauseAnalystAgent] Failed to parse response: {response_text[:500]}")
            raise ValueError(
                "Failed to parse LLM response into hypotheses. "
                "Ensure LLM API is configured and returning valid output."
            )
    
    def _parse_hypothesis_response(
        self,
        response_text: str,
        past_incidents: List[dict],
        relevant_docs: List[dict]
    ) -> List[Hypothesis]:
        """
        Parse LLM response into structured hypotheses using JSON extraction.
        
        Args:
            response_text: Raw LLM response (should contain JSON)
            past_incidents: RAG sources
            relevant_docs: RAG sources
        
        Returns:
            List of parsed Hypothesis objects
        """
        hypotheses = []
        
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = response_text
            
            # Try to extract JSON from markdown code block
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                json_text = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    json_text = json_match.group(0)
            
            # Parse JSON
            parsed_data = json.loads(json_text)
            
            # Convert parsed data to Hypothesis objects
            hypotheses_list = parsed_data.get('hypotheses', [])
            for hyp_data in hypotheses_list:
                hypothesis = Hypothesis(
                    hypothesis_id=uuid4(),
                    type=hyp_data.get('type', 'unknown'),
                    claim=hyp_data.get('claim', ''),
                    confidence=min(1.0, max(0.0, float(hyp_data.get('confidence', 0.5)))),
                    evidence=hyp_data.get('evidence', []),
                    counterevidence=hyp_data.get('counterevidence', []),
                    unknowns=hyp_data.get('unknowns', []) or ["Need more investigation"],
                    similar_past_incidents=[inc.get("incident_id", "unknown") for inc in past_incidents[:2]],
                    relevant_docs=[doc.get("title", "unknown") for doc in relevant_docs[:2]]
                )
                hypotheses.append(hypothesis)
            
            logger.info(f"[RootCauseAnalystAgent] Successfully parsed {len(hypotheses)} hypotheses")
            
        except json.JSONDecodeError as e:
            logger.error(f"[RootCauseAnalystAgent] Failed to parse JSON: {e}")
            logger.debug(f"Response was: {response_text[:300]}")
            return []
        except Exception as e:
            logger.error(f"[RootCauseAnalystAgent] Error parsing response: {e}")
            logger.debug(f"Response was: {response_text[:300]}")
            return []
        
        # Sort by confidence (highest first)
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses
    
    def _generate_next_steps(self, hypotheses: List[Hypothesis], incident: Incident) -> List[str]:
        """
        Generate recommended investigation steps.
        
        Args:
            hypotheses: Generated hypotheses (ranked by confidence)
            incident: The incident
        
        Returns:
            List of recommended next steps
        """
        steps = []
        
        top_hypothesis = hypotheses[0] if hypotheses else None
        
        if top_hypothesis:
            if top_hypothesis.type == "migration_misstep":
                steps.append("Review Stage-specific migration guide for affected component")
                steps.append("Verify affected merchants completed all required setup steps")
                steps.append("Check if validation/testing happens post-migration")
            elif top_hypothesis.type == "platform_regression":
                steps.append("Check recent deployments and release notes")
                steps.append("Review internal error logs for affected component")
                steps.append("Compare event patterns before/after suspected deployment")
            elif top_hypothesis.type == "merchant_config":
                steps.append("Verify merchant configurations in admin panel")
                steps.append("Check if merchants followed setup documentation")
                steps.append("Contact affected merchants to verify their configuration")
            elif top_hypothesis.type == "docs_gap":
                steps.append("Review documentation for clarity and completeness")
                steps.append("Check support tickets for related questions")
                steps.append("Identify specific steps that need better explanation")
        
        steps.append(f"Contact sample of affected merchants: {', '.join(incident.affected_merchants[:3])}")
        steps.append("Validate hypothesis with evidence from investigation")
        
        return steps
    
    def _store_hypotheses(self, hypotheses: List[Hypothesis], incident_id: str, db: Session):
        """
        Store hypotheses in database.
        
        Args:
            hypotheses: Hypotheses to store
            incident_id: Associated incident ID
            db: SQLAlchemy session
        """
        for hypothesis in hypotheses:
            db_hypothesis = IncidentHypothesisDB(
                hypothesis_id=hypothesis.hypothesis_id,
                incident_id=incident_id,
                type=hypothesis.type,
                claim=hypothesis.claim,
                confidence=hypothesis.confidence,
                evidence=json.dumps(hypothesis.evidence),
                counterevidence=json.dumps(hypothesis.counterevidence),
                unknowns=json.dumps(hypothesis.unknowns),
                similar_past_incidents=json.dumps(hypothesis.similar_past_incidents),
                relevant_docs=json.dumps(hypothesis.relevant_docs)
            )
            db.add(db_hypothesis)
        
        db.commit()
        logger.info(f"[RootCauseAnalystAgent] Stored {len(hypotheses)} hypotheses for incident {incident_id}")
