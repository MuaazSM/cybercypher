from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from models.incidents import Incident
from models.hypotheses import Hypothesis, RootCauseAnalysis, AlternativeHypothesis
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
        5. [Priority 6] Generate opposing hypotheses for intellectual debate
        6. Store hypotheses in database
        
        Args:
            incident: Incident to analyze
            db: SQLAlchemy session
        
        Returns:
            RootCauseAnalysis with ranked hypotheses and alternative explanations
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
        
        # Step 5: [Priority 6] Generate opposing hypotheses for intellectual debate
        logger.debug("[RootCauseAnalystAgent] Generating opposing hypotheses...")
        alternatives = self.generate_opposing_hypotheses(
            primary_hypotheses=hypotheses,
            incident=incident,
            evidence_bundle=evidence_bundle,
            db=db
        )
        logger.info(f"[RootCauseAnalystAgent] Generated {len(alternatives)} alternative explanations")
        
        # Generate debate summary
        debate_summary = None
        if hypotheses and alternatives:
            debate_summary = self.generate_debate_summary(hypotheses[0], alternatives)
            logger.debug("[RootCauseAnalystAgent] Generated debate summary")
        
        # Step 6: Store hypotheses in database
        self._store_hypotheses(hypotheses, incident.incident_id, db)
        
        # Create analysis result
        analysis = RootCauseAnalysis(
            incident_id=incident.incident_id,
            analysis_timestamp=datetime.utcnow(),
            hypotheses=hypotheses,
            alternative_explanations=alternatives,
            debate_summary=debate_summary,
            recommended_next_steps=self._generate_next_steps(hypotheses, incident),
            rag_sources_used=len(past_incidents) + len(relevant_docs)
        )
        
        logger.info(
            f"[RootCauseAnalystAgent] Analysis complete: {len(analysis.hypotheses)} hypotheses, "
            f"{len(analysis.alternative_explanations)} alternatives, {analysis.rag_sources_used} RAG sources"
        )
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
    
    def refine_hypotheses_with_evidence(
        self,
        hypotheses: List[Hypothesis],
        new_evidence: Dict[str, Any],
        db: Session
    ) -> List[Hypothesis]:
        """
        Update hypothesis confidences using Bayesian updating.
        
        Implements Bayes' Rule: P(H|E) = P(E|H) * P(H) / P(E)
        
        This is the key to showing adaptive reasoning - confidence scores
        update as new evidence arrives, not static from LLM generation.
        
        Args:
            hypotheses: Current hypotheses with prior confidence scores
            new_evidence: New evidence from RAG, logs, feedback, stage analysis
            db: SQLAlchemy session for data access
        
        Returns:
            Updated hypotheses with posterior confidence scores, sorted by confidence
        
        Example:
            Initial: migration_misstep (0.74), platform_regression (0.26)
            
            Evidence: Similar past incidents (3 cases of migration_misstep)
            - Likelihood for migration_misstep: 0.8 (matches 100% of cases)
            - Likelihood for platform_regression: 0.3 (matches 0% of cases)
            
            Updated:
            - migration_misstep: 0.8 * 0.74 / total = 0.85 (increased)
            - platform_regression: 0.3 * 0.26 / total = 0.15 (decreased)
        """
        print("[Root Cause] Refining hypotheses with Bayesian updating...")
        
        # Step 1: Calculate likelihood for each hypothesis
        # Likelihood = P(E|H): How likely is this evidence if the hypothesis is true?
        likelihoods = {}
        for hypothesis in hypotheses:
            likelihood = self._calculate_likelihood(hypothesis, new_evidence)
            likelihoods[hypothesis.hypothesis_id] = likelihood
            print(f"  Likelihood P(E|H) for {hypothesis.type}: {likelihood:.3f}")
        
        # Step 2: Calculate unnormalized posteriors
        # Unnormalized posterior = Likelihood * Prior
        # Prior = existing confidence
        refined = []
        unnormalized_posteriors = {}
        
        for hypothesis in hypotheses:
            prior = hypothesis.confidence
            likelihood = likelihoods[hypothesis.hypothesis_id]
            
            # Bayes' rule (unnormalized): P(H|E) ∝ P(E|H) * P(H)
            unnormalized_posterior = likelihood * prior
            unnormalized_posteriors[hypothesis.hypothesis_id] = unnormalized_posterior
            
            print(f"  Unnormalized posterior for {hypothesis.type}: {unnormalized_posterior:.4f}")
        
        # Step 3: Normalize to ensure probabilities sum to 1.0
        # This ensures P(E) normalization across all hypotheses
        total_posterior = sum(unnormalized_posteriors.values())
        
        for hypothesis in hypotheses:
            # Create updated copy
            updated_hypothesis = hypothesis.copy(deep=True)
            
            # Calculate normalized posterior
            if total_posterior > 0:
                posterior_confidence = unnormalized_posteriors[hypothesis.hypothesis_id] / total_posterior
            else:
                posterior_confidence = 1.0 / len(hypotheses)  # Uniform if all zero
            
            # Update confidence
            old_confidence = updated_hypothesis.confidence
            updated_hypothesis.confidence = round(posterior_confidence, 3)
            
            # Step 4: Update evidence lists based on likelihood
            if likelihoods[hypothesis.hypothesis_id] > 0.6:
                # Evidence supports this hypothesis
                supporting_evidence = self._extract_supporting_evidence(hypothesis, new_evidence)
                updated_hypothesis.evidence.extend(supporting_evidence)
                print(f"  ✓ Evidence supports {hypothesis.type}: +{len(supporting_evidence)} items")
            
            elif likelihoods[hypothesis.hypothesis_id] < 0.4:
                # Evidence contradicts this hypothesis
                contradicting_evidence = self._extract_contradicting_evidence(hypothesis, new_evidence)
                updated_hypothesis.counterevidence.extend(contradicting_evidence)
                print(f"  ✗ Evidence contradicts {hypothesis.type}: +{len(contradicting_evidence)} items")
            
            refined.append(updated_hypothesis)
            
            # Print confidence change
            confidence_change = updated_hypothesis.confidence - old_confidence
            direction = "↑" if confidence_change > 0 else "↓" if confidence_change < 0 else "→"
            print(f"  {direction} {hypothesis.type}: {old_confidence:.3f} → {updated_hypothesis.confidence:.3f} ({confidence_change:+.3f})")
        
        # Step 5: Re-sort by confidence (highest first)
        refined.sort(key=lambda h: h.confidence, reverse=True)
        
        print(f"[Root Cause] Hypothesis refinement complete. Final ranking:")
        for i, h in enumerate(refined, 1):
            print(f"  {i}. {h.type}: {h.confidence:.3f} ({len(h.evidence)} evidence items)")
        
        return refined
    
    def _calculate_likelihood(
        self,
        hypothesis: Hypothesis,
        evidence: Dict[str, Any]
    ) -> float:
        """
        Calculate P(E|H): likelihood of evidence given hypothesis.
        
        This is the core Bayesian component - how likely is this evidence
        if the hypothesis were true?
        
        Args:
            hypothesis: Hypothesis to evaluate
            evidence: New evidence to assess
        
        Returns:
            Likelihood score from 0.0 to 1.0
        """
        likelihood = 0.5  # Neutral baseline
        
        evidence_type = evidence.get("type", "")
        
        # ===== RAG Retrieval Evidence =====
        # Evidence from similar past incidents
        if evidence_type == "rag_retrieval":
            similar_incidents = evidence.get("similar_incidents", [])
            
            if similar_incidents:
                # Count how many past incidents had the same root cause
                matching_causes = sum(
                    1 for incident in similar_incidents
                    if incident.get("root_cause") == hypothesis.type
                )
                
                # Match rate: what fraction of similar incidents had this cause?
                match_rate = matching_causes / len(similar_incidents) if similar_incidents else 0
                
                # Likelihood = 0.3 + (match_rate * 0.5)
                # If 100% match: 0.3 + 0.5 = 0.8 (strong evidence)
                # If 0% match: 0.3 (weak evidence, but not impossible)
                likelihood = 0.3 + (match_rate * 0.5)
                logger.debug(
                    f"[Bayesian] RAG evidence for {hypothesis.type}: "
                    f"{matching_causes}/{len(similar_incidents)} similar incidents, "
                    f"likelihood={likelihood:.3f}"
                )
        
        # ===== Log Analysis Evidence =====
        # Evidence from system logs and diagnostics
        elif evidence_type == "log_analysis":
            log_findings = evidence.get("findings", [])
            
            if hypothesis.type == "platform_regression":
                # For regression hypothesis, look for deployment/release evidence
                regex_patterns = [r"deployment", r"release", r"push", r"update", r"version"]
                matching_findings = sum(
                    1 for finding in log_findings
                    if any(re.search(pattern, finding.lower()) for pattern in regex_patterns)
                )
                
                likelihood = 0.8 if matching_findings > 0 else 0.3
                logger.debug(
                    f"[Bayesian] Log analysis for platform_regression: "
                    f"{matching_findings} deployment-related findings, likelihood={likelihood:.3f}"
                )
            
            elif hypothesis.type == "merchant_config":
                # For config hypothesis, look for configuration errors
                config_keywords = [r"config", r"setup", r"initialization", r"parameter", r"setting"]
                matching_findings = sum(
                    1 for finding in log_findings
                    if any(re.search(pattern, finding.lower()) for pattern in config_keywords)
                )
                
                likelihood = 0.8 if matching_findings > 0 else 0.4
                logger.debug(
                    f"[Bayesian] Log analysis for merchant_config: "
                    f"{matching_findings} config-related findings, likelihood={likelihood:.3f}"
                )
        
        # ===== Merchant Feedback Evidence =====
        # Evidence from merchant reports and feedback
        elif evidence_type == "merchant_feedback":
            feedback_text = evidence.get("feedback", "").lower()
            
            if hypothesis.type == "docs_gap":
                # For docs gap, look for confusion/clarity keywords
                clarity_keywords = ["unclear", "confusing", "documentation", "how do i", "not clear", "missing"]
                keyword_matches = sum(
                    1 for keyword in clarity_keywords
                    if keyword in feedback_text
                )
                
                likelihood = 0.9 if keyword_matches > 0 else 0.3
                logger.debug(
                    f"[Bayesian] Merchant feedback for docs_gap: "
                    f"{keyword_matches} clarity keywords, likelihood={likelihood:.3f}"
                )
            
            elif hypothesis.type == "migration_misstep":
                # For migration issue, look for process/step-related keywords
                migration_keywords = ["migration", "stage", "step", "missed", "skipped", "forgot"]
                keyword_matches = sum(
                    1 for keyword in migration_keywords
                    if keyword in feedback_text
                )
                
                likelihood = 0.85 if keyword_matches > 0 else 0.4
                logger.debug(
                    f"[Bayesian] Merchant feedback for migration_misstep: "
                    f"{keyword_matches} migration keywords, likelihood={likelihood:.3f}"
                )
        
        # ===== Stage Analysis Evidence =====
        # Evidence from stage concentration patterns
        elif evidence_type == "stage_analysis":
            stage_concentration = evidence.get("stage_concentration", {})
            dominant_stage = evidence.get("dominant_stage")
            
            if stage_concentration and dominant_stage:
                # Get concentration percentage for dominant stage
                stage_pct = stage_concentration.get(str(dominant_stage), 0)
                
                if hypothesis.type == "migration_misstep":
                    # Migration issues often concentrate in one stage
                    # High concentration (>70%) suggests stage-specific problem
                    likelihood = 0.85 if stage_pct > 0.7 else 0.5
                    logger.debug(
                        f"[Bayesian] Stage analysis for migration_misstep: "
                        f"Stage {dominant_stage} = {stage_pct*100:.0f}%, likelihood={likelihood:.3f}"
                    )
        
        return max(0.0, min(1.0, likelihood))  # Clamp to [0, 1]
    
    def _extract_supporting_evidence(
        self,
        hypothesis: Hypothesis,
        evidence: Dict[str, Any]
    ) -> List[str]:
        """
        Extract specific supporting evidence statements.
        
        Adds new evidence to hypothesis.evidence list when evidence
        supports the hypothesis.
        
        Args:
            hypothesis: Hypothesis being evaluated
            evidence: Evidence bundle
        
        Returns:
            List of supporting evidence statements to add
        """
        supporting = []
        evidence_type = evidence.get("type", "")
        
        if evidence_type == "rag_retrieval":
            similar_incidents = evidence.get("similar_incidents", [])
            matching_count = sum(
                1 for inc in similar_incidents
                if inc.get("root_cause") == hypothesis.type
            )
            
            if matching_count > 0:
                supporting.append(
                    f"Found {matching_count}/{len(similar_incidents)} similar past incidents "
                    f"with root cause: {hypothesis.type}"
                )
        
        elif evidence_type == "log_analysis":
            findings = evidence.get("findings", [])
            if findings:
                supporting.append(f"Log analysis findings: {findings[0]}")
                if len(findings) > 1:
                    supporting.append(f"Additional log finding: {findings[1]}")
        
        elif evidence_type == "merchant_feedback":
            feedback_summary = evidence.get("summary", "")
            if feedback_summary:
                supporting.append(f"Merchant feedback confirms: {feedback_summary}")
        
        elif evidence_type == "stage_analysis":
            dominant_stage = evidence.get("dominant_stage")
            concentration_pct = evidence.get("stage_concentration", {}).get(str(dominant_stage), 0)
            
            if dominant_stage and concentration_pct > 0.7:
                supporting.append(
                    f"High concentration ({concentration_pct*100:.0f}%) in Stage {dominant_stage} "
                    f"suggests stage-specific issue"
                )
        
        return supporting
    
    def _extract_contradicting_evidence(
        self,
        hypothesis: Hypothesis,
        evidence: Dict[str, Any]
    ) -> List[str]:
        """
        Extract evidence that contradicts hypothesis.
        
        Adds counterevidence to hypothesis.counterevidence list when
        evidence does NOT support the hypothesis.
        
        Args:
            hypothesis: Hypothesis being evaluated
            evidence: Evidence bundle
        
        Returns:
            List of contradicting evidence statements to add
        """
        contradicting = []
        evidence_type = evidence.get("type", "")
        
        if evidence_type == "log_analysis":
            findings = evidence.get("findings", [])
            if findings and not any(
                hypothesis.type.lower() in finding.lower()
                for finding in findings
            ):
                contradicting.append(
                    f"Log analysis did not find patterns expected for {hypothesis.type}: "
                    f"{findings[0] if findings else 'no relevant findings'}"
                )
        
        elif evidence_type == "stage_analysis":
            # If evidence shows dispersed errors across stages,
            # contradicts migration_misstep hypothesis (which predicts stage concentration)
            stage_concentration = evidence.get("stage_concentration", {})
            max_concentration = max(stage_concentration.values()) if stage_concentration else 0
            
            if hypothesis.type == "migration_misstep" and max_concentration < 0.5:
                contradicting.append(
                    f"Errors dispersed across stages (max concentration {max_concentration*100:.0f}%) "
                    f"contradicts stage-specific migration issue"
                )
        
        return contradicting
    
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

    def generate_opposing_hypotheses(
        self,
        primary_hypotheses: List[Hypothesis],
        incident: Incident,
        evidence_bundle: Dict[str, Any],
        db: Session
    ) -> List[AlternativeHypothesis]:
        """
        Generate counter-hypotheses to challenge primary explanations.
        
        Priority 6 Enhancement: Multi-Agent Debate / Intellectual Humility
        
        For the top 2 primary hypotheses, intentionally generates opposing
        hypotheses that challenge our assumptions. This forces more rigorous
        reasoning through adversarial thinking.
        
        Questions asked:
        - "What if we're WRONG about the primary hypothesis?"
        - "What alternative explanation could fit the same data?"
        - "What evidence are we overlooking that contradicts our theory?"
        
        Args:
            primary_hypotheses: Top hypotheses from initial analysis
            incident: The incident being analyzed
            evidence_bundle: Evidence gathered during analysis
            db: Database session
        
        Returns:
            List of AlternativeHypothesis objects with plausibility scores
        """
        logger.info("[RootCauseAnalystAgent] Generating opposing hypotheses for intellectual debate...")
        
        # Take top 2 primary hypotheses to challenge
        hypotheses_to_challenge = primary_hypotheses[:2]
        alternatives = []
        
        for primary in hypotheses_to_challenge:
            logger.debug(f"[RootCauseAnalystAgent] Challenging hypothesis: {primary.type} ({primary.confidence:.2f})")
            
            # Build adversarial prompt
            prompt = self._build_adversarial_prompt(primary, incident, evidence_bundle)
            
            try:
                # Get LLM to generate counter-hypotheses
                response = self.llm.generate(
                    prompt=prompt,
                    model="gpt-4o",  # Use most capable model for nuanced reasoning
                    temperature=0.8,  # Higher temperature for creative alternatives
                    response_model=AlternativeHypothesesResponse
                )
                
                # Parse alternatives
                for alt_response in response.alternatives:
                    alternative = AlternativeHypothesis(
                        alternative_id=uuid4(),
                        type=alt_response.type,
                        claim=alt_response.claim,
                        plausibility=alt_response.plausibility,
                        contradicting_evidence=alt_response.contradicting_evidence,
                        explanatory_power=alt_response.explanatory_power,
                        why_we_might_be_wrong=alt_response.why_we_might_be_wrong,
                        why_primary_is_stronger=alt_response.why_primary_is_stronger,
                        what_would_prove_this=alt_response.what_would_prove_this
                    )
                    alternatives.append(alternative)
                    
                    logger.info(
                        f"[RootCauseAnalystAgent] Generated alternative: {alternative.type} "
                        f"(plausibility: {alternative.plausibility:.2f})"
                    )
            
            except Exception as e:
                logger.error(f"[RootCauseAnalystAgent] Failed to generate alternatives for {primary.type}: {e}")
                continue
        
        logger.info(f"[RootCauseAnalystAgent] Generated {len(alternatives)} alternative explanations")
        return alternatives
    
    def _build_adversarial_prompt(
        self,
        primary_hypothesis: Hypothesis,
        incident: Incident,
        evidence_bundle: Dict[str, Any]
    ) -> str:
        """Build prompt for generating counter-hypotheses."""
        
        # Format evidence
        evidence_str = "\n".join(f"- {e}" for e in evidence_bundle.get("observations", []))
        sample_events = evidence_bundle.get("sample_events", [])[:3]
        events_str = "\n".join(
            f"- Merchant {e.get('merchant_id')}: {e.get('error_type')} at {e.get('timestamp')}"
            for e in sample_events
        )
        
        prompt = f"""You are a critical analyst tasked with challenging a proposed root cause hypothesis.

**INCIDENT DETAILS:**
Title: {incident.title}
Severity: {incident.severity}
Affected merchants: {incident.blast_radius_estimate}
Stage distribution: {json.dumps(evidence_bundle.get('stage_distribution', {}))}

**CURRENT PRIMARY HYPOTHESIS:**
Type: {primary_hypothesis.type}
Claim: {primary_hypothesis.claim}
Confidence: {primary_hypothesis.confidence:.2f}

Evidence supporting primary:
{chr(10).join(f"  - {e}" for e in primary_hypothesis.evidence)}

**YOUR TASK: Challenge this hypothesis**

Generate 1-2 ALTERNATIVE explanations that could fit the same data.

Questions to explore:
1. What if we're WRONG about "{primary_hypothesis.type}"?
2. What alternative root cause type could explain these observations?
3. What evidence are we overlooking that contradicts our primary theory?
4. Could the data be misleading us in a systematic way?

**AVAILABLE EVIDENCE TO REINTERPRET:**
{evidence_str}

**SAMPLE EVENTS:**
{events_str}

**ALTERNATIVE HYPOTHESIS TYPES:**
- merchant_config: Merchants misconfigured something
- migration_misstep: Migration process/documentation issue
- platform_regression: Platform bug or code regression
- docs_gap: Documentation unclear or missing

For each alternative, provide:
1. **type**: One of the 4 types above (must be DIFFERENT from primary)
2. **claim**: Clear counter-claim challenging the primary
3. **plausibility**: Score 0.0-1.0 (typically lower than primary's {primary_hypothesis.confidence:.2f})
4. **contradicting_evidence**: Evidence from same data supporting this alternative
5. **explanatory_power**: How well this explains the observations
6. **why_we_might_be_wrong**: Reasoning about how primary could be incorrect
7. **why_primary_is_stronger**: Why primary is still more likely (be fair)
8. **what_would_prove_this**: Evidence that would validate this alternative

Be intellectually honest - generate plausible alternatives that force rigorous thinking.
"""
        
        return prompt
    
    def generate_debate_summary(
        self,
        primary_hypothesis: Hypothesis,
        alternatives: List[AlternativeHypothesis]
    ) -> str:
        """Generate summary of why primary was chosen over alternatives."""
        
        if not alternatives:
            return f"No significant alternatives identified. Primary hypothesis ({primary_hypothesis.type}) at {primary_hypothesis.confidence:.2f} confidence is clearly strongest."
        
        summary_parts = [
            f"**Primary Hypothesis:** {primary_hypothesis.type} ({primary_hypothesis.confidence:.2f} confidence)",
            f"**Claim:** {primary_hypothesis.claim}",
            "",
            "**Alternatives Considered:**"
        ]
        
        for idx, alt in enumerate(alternatives, 1):
            summary_parts.extend([
                f"{idx}. **{alt.type}** ({alt.plausibility:.2f} plausibility)",
                f"   Claim: {alt.claim}",
                f"   Why we might be wrong: {alt.why_we_might_be_wrong[:150]}...",
                f"   Why primary is stronger: {alt.why_primary_is_stronger[:150]}...",
                ""
            ])
        
        summary_parts.extend([
            "**Decision:**",
            f"Primary hypothesis ({primary_hypothesis.type}) remains most likely due to:",
            f"- Higher confidence score ({primary_hypothesis.confidence:.2f} vs {max(a.plausibility for a in alternatives):.2f})",
            f"- Stronger evidence alignment",
            f"- Better explanatory power for all observations",
            "",
            "However, alternatives have been documented for transparency and should be revisited if primary validation fails."
        ])
        
        return "\n".join(summary_parts)


# Pydantic models for adversarial LLM response parsing
class AlternativeHypothesisResponse(BaseModel):
    """Structured alternative hypothesis from LLM."""
    type: str = Field(description="Type: merchant_config, migration_misstep, platform_regression, or docs_gap")
    claim: str = Field(description="Counter-claim challenging the primary hypothesis")
    plausibility: float = Field(description="Plausibility score 0.0-1.0")
    contradicting_evidence: List[str] = Field(description="Evidence supporting this alternative")
    explanatory_power: str = Field(description="How well this explains the observations")
    why_we_might_be_wrong: str = Field(description="Why the primary hypothesis could be incorrect")
    why_primary_is_stronger: str = Field(description="Why primary is still more likely")
    what_would_prove_this: List[str] = Field(description="Evidence that would validate this")


class AlternativeHypothesesResponse(BaseModel):
    """Structured response containing alternative hypotheses."""
    alternatives: List[AlternativeHypothesisResponse] = Field(
        description="1-2 alternative explanations challenging the primary"
    )

