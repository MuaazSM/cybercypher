import json
import logging
from datetime import datetime

from db.database import SessionLocal
from db.models import IncidentDB, IncidentHypothesisDB
from agents.triage import IncidentTriageAgent
from agents.root_cause import RootCauseAnalystAgent
from tools.llm_router import LLMRouter, LLMConfig
from tools.knowledge_base import KnowledgeBase
from sqlalchemy import func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_root_cause_analysis():
    """Demo root cause analysis with RAG enhancement."""
    print("\n" + "=" * 80)
    print("ROOT CAUSE ANALYST AGENT DEMO (Agent 5)")
    print("=" * 80)
    
    # Initialize components
    print("\n[1] Initializing components...")
    llm_config = LLMConfig()
    
    # Check if any LLM is configured
    if not any([llm_config.openai_api_key, llm_config.groq_api_key, llm_config.gemini_api_key]):
        print("✗ ERROR: No LLM API keys found!")
        print("\nRoot Cause Analysis REQUIRES an LLM provider.")
        print("Set one of these environment variables:")
        print("  - OPENAI_API_KEY (https://platform.openai.com/api-keys)")
        print("  - GROQ_API_KEY (https://console.groq.com/keys)")
        print("  - GEMINI_API_KEY (https://aistudio.google.com/app/apikey)")
        print("\nOr create a .env file with your API key.")
        return
    
    llm = LLMRouter(llm_config)
    
    # Initialize and seed knowledge base
    kb = KnowledgeBase()
    KnowledgeBase.seed_knowledge_base(kb)
    print("✓ LLM Router and Knowledge Base initialized")
    print(f"✓ Knowledge base seeded with {len(kb.get_all())} documents")
    
    # Initialize root cause agent with LLM and knowledge base
    root_cause_agent = RootCauseAnalystAgent(llm, kb)
    
    # Initialize and seed knowledge base
    kb = KnowledgeBase()
    KnowledgeBase.seed_knowledge_base(kb)
    print("✓ LLM Router and Knowledge Base initialized")
    print(f"✓ Knowledge base seeded with {len(kb.get_all())} documents")
    
    db = SessionLocal()
    
    try:
        # Step 1: Ensure we have an incident to analyze
        print("\n[2] Getting incident to analyze...")
        incident = db.query(IncidentDB).order_by(
            IncidentDB.created_at.desc()
        ).first()
        
        if not incident:
            print("✗ No incidents found. Run demo_triage.py first.")
            return
        
        print(f"✓ Found incident: {incident.title}")
        print(f"   Severity: {incident.severity}")
        print(f"   Cluster: {incident.cluster_id}")
        
        # Convert to Pydantic
        from models.incidents import Incident
        incident_pydantic = Incident(
            incident_id=incident.incident_id,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
            status=incident.status,
            severity=incident.severity,
            title=incident.title,
            summary=incident.summary,
            cluster_id=incident.cluster_id,
            affected_merchants=json.loads(incident.affected_merchants),
            blast_radius_estimate=incident.blast_radius_estimate,
            impacts_checkout=incident.impacts_checkout,
            impacts_revenue=incident.impacts_revenue,
            customer_trust_risk=incident.customer_trust_risk
        )
        
        # Step 2: Perform root cause analysis
        print("\n[3] Performing root cause analysis...")
        analysis = root_cause_agent.analyze_root_cause(incident_pydantic, db)
        
        print(f"✓ Analysis complete: {len(analysis.hypotheses)} hypotheses generated")
        print(f"✓ RAG sources used: {analysis.rag_sources_used}")
        
        # Step 3: Display hypotheses
        print("\n[4] Generated Hypotheses (Ranked by Confidence)")
        print("-" * 80)
        
        for i, hypothesis in enumerate(analysis.hypotheses, 1):
            print(f"\n   Hypothesis {i}: {hypothesis.type}")
            print(f"   Confidence: {hypothesis.confidence:.2f}/1.00")
            print(f"   Claim: {hypothesis.claim}")
            
            if hypothesis.evidence:
                print(f"   Supporting Evidence ({len(hypothesis.evidence)}):")
                for evidence in hypothesis.evidence:
                    print(f"     • {evidence}")
            
            if hypothesis.counterevidence:
                print(f"   Counterevidence ({len(hypothesis.counterevidence)}):")
                for item in hypothesis.counterevidence:
                    print(f"     • {item}")
            
            if hypothesis.unknowns:
                print(f"   Unknowns ({len(hypothesis.unknowns)}):")
                for item in hypothesis.unknowns:
                    print(f"     • {item}")
            
            if hypothesis.similar_past_incidents:
                print(f"   Similar Past Incidents: {', '.join(hypothesis.similar_past_incidents)}")
            
            if hypothesis.relevant_docs:
                print(f"   Relevant Docs: {', '.join(hypothesis.relevant_docs)}")
        
        # Step 4: Recommended next steps
        print(f"\n[5] Recommended Investigation Steps")
        print("-" * 80)
        for i, step in enumerate(analysis.recommended_next_steps, 1):
            print(f"   {i}. {step}")
        
        # Step 5: Verify storage
        print(f"\n[6] Verifying database storage...")
        stored_hypotheses = db.query(IncidentHypothesisDB).filter(
            IncidentHypothesisDB.incident_id == incident.incident_id
        ).all()
        
        print(f"✓ Stored {len(stored_hypotheses)} hypotheses in database")
        
        if stored_hypotheses:
            first_hyp = stored_hypotheses[0]
            print(f"✓ Sample stored hypothesis:")
            print(f"   - Type: {first_hyp.type}")
            print(f"   - Confidence: {first_hyp.confidence:.2f}")
            print(f"   - Claim: {first_hyp.claim[:60]}...")
        
        # Statistics
        print(f"\n[7] Analysis Statistics")
        print("-" * 80)
        
        total_hypotheses = db.query(IncidentHypothesisDB).count()
        avg_confidence = db.query(func.avg(IncidentHypothesisDB.confidence)).scalar() or 0
        
        type_counts = {}
        for hyp in db.query(IncidentHypothesisDB).all():
            type_counts[hyp.type] = type_counts.get(hyp.type, 0) + 1
        
        print(f"   • Total hypotheses generated: {total_hypotheses}")
        print(f"   • Average confidence: {avg_confidence:.2f}")
        print(f"   • Hypothesis type distribution:")
        for hyp_type, count in sorted(type_counts.items()):
            print(f"     - {hyp_type}: {count}")
        
        print("\n" + "=" * 80)
        print("✅ ROOT CAUSE ANALYSIS DEMO COMPLETE")
        print("=" * 80)
        print("\nNext Steps:")
        print("  • Hypotheses are ranked by confidence")
        print("  • Top hypothesis provides most likely root cause")
        print("  • Evidence supports or contradicts each hypothesis")
        print("  • Investigation steps guide next actions")
        print("  • RAG sources show relevant past incidents and documentation")
        print("\n")
        
    finally:
        db.close()


if __name__ == "__main__":
    demo_root_cause_analysis()
