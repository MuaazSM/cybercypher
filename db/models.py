from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text,
    DateTime, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import uuid

Base = declarative_base()


class RawEventDB(Base):
    """
    Raw events from external sources (Agent 1: Ingestion).
    Stores unprocessed signals from tickets, API errors, webhooks, etc.
    """
    __tablename__ = "events_raw"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)  # ticket, api_error, webhook_fail, checkout_fail
    merchant_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    payload = Column(JSONB, nullable=False)  # Flexible structure per event_type
    source = Column(String(100), nullable=False)  # zendesk, api_logs, webhook_service, checkout_monitor
    idempotency_key = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_merchant_timestamp', 'merchant_id', 'timestamp'),
        Index('idx_event_type', 'event_type'),
        Index('idx_idempotency', 'idempotency_key'),
    )


class CleanEventDB(Base):
    """
    Normalized, enriched events with signatures (Agent 2: Normalization).
    Contains structured metadata for pattern detection and clustering.
    """
    __tablename__ = "events_clean"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signature = Column(String(255), nullable=False)  # e.g., "WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2"
    merchant_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Structured fields
    component = Column(String(50), nullable=False)  # checkout, api, webhook, auth, orders, inventory
    error_code = Column(String(100))
    severity_hint = Column(String(20), nullable=False)  # low, medium, high
    
    # Enriched context
    migration_stage = Column(Integer, nullable=False)  # 1, 2, 3, or 4
    merchant_industry = Column(String(100))
    merchant_framework = Column(String(100))
    merchant_region = Column(String(100))
    
    # Text summary
    raw_text_summary = Column(Text, nullable=False)
    
    # Reference to original
    raw_event_id = Column(UUID(as_uuid=True), ForeignKey('events_raw.event_id'))
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_signature', 'signature'),
        Index('idx_merchant_stage', 'merchant_id', 'migration_stage'),
        Index('idx_component', 'component'),
        Index('idx_timestamp', 'timestamp'),
    )


class IncidentClusterDB(Base):
    """
    Groups of related events indicating potential incidents (Agent 3: Pattern Detection).
    Represents patterns detected across multiple merchants/events.
    """
    __tablename__ = "incident_clusters"

    cluster_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Cluster identity
    primary_signature = Column(String(255), nullable=False)
    top_signatures = Column(JSONB, nullable=False)  # Array of strings
    
    # Affected scope
    affected_merchant_ids = Column(JSONB, nullable=False)  # Array of strings
    merchant_count = Column(Integer, nullable=False)
    event_count = Column(Integer, nullable=False)
    
    # Pattern characteristics
    trend = Column(String(20), nullable=False)  # spiking, stable, declining
    first_seen = Column(DateTime, nullable=False)
    last_seen = Column(DateTime, nullable=False)
    rate_per_hour = Column(Float, nullable=False)
    baseline_rate = Column(Float, nullable=False)
    
    # Supporting evidence
    sample_event_ids = Column(JSONB, nullable=False)  # Array of UUIDs
    stage_distribution = Column(JSONB, nullable=False)  # {stage: count}
    component_distribution = Column(JSONB, nullable=False)  # {component: count}

    __table_args__ = (
        Index('idx_signature_cluster', 'primary_signature'),
        Index('idx_trend', 'trend'),
        Index('idx_updated', 'updated_at'),
    )


class IncidentDB(Base):
    """
    Confirmed incidents requiring investigation (Agent 4: Triage).
    Represents validated issues with severity and business impact assessment.
    """
    __tablename__ = "incidents"

    incident_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Status tracking
    status = Column(String(50), nullable=False)  # open, investigating, resolved, closed
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    
    # Identity
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False)
    
    # Link to cluster
    cluster_id = Column(UUID(as_uuid=True), ForeignKey('incident_clusters.cluster_id'))
    
    # Scope
    affected_merchants = Column(JSONB, nullable=False)  # Array of merchant IDs
    blast_radius_estimate = Column(String(255))
    
    # Business impact
    impacts_checkout = Column(Boolean, default=False)
    impacts_revenue = Column(Boolean, default=False)
    customer_trust_risk = Column(String(20))  # low, medium, high
    
    # Metadata
    assigned_to = Column(String(100))
    external_ticket_id = Column(String(100))

    __table_args__ = (
        Index('idx_status', 'status'),
        Index('idx_severity', 'severity'),
        Index('idx_cluster', 'cluster_id'),
    )


class IncidentHypothesisDB(Base):
    """
    Root cause hypotheses with evidence (Agent 5: Root Cause Analysis).
    Contains ranked hypotheses with confidence scores and RAG context.
    """
    __tablename__ = "incident_hypotheses"

    hypothesis_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey('incidents.incident_id'), nullable=False)
    
    # Classification (4 root cause buckets)
    type = Column(String(50), nullable=False)  # merchant_config, migration_misstep, platform_regression, docs_gap
    
    # The claim
    claim = Column(Text, nullable=False)
    
    # Confidence and evidence
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0
    evidence = Column(JSONB, nullable=False)  # Array of supporting facts
    counterevidence = Column(JSONB)  # Array of contradicting facts
    unknowns = Column(JSONB)  # Array of things to verify
    
    # RAG context
    similar_past_incidents = Column(JSONB)  # Array of incident IDs
    relevant_docs = Column(JSONB)  # Array of document references
    
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_incident', 'incident_id'),
        Index('idx_confidence', 'confidence'),
        Index('idx_type', 'type'),
    )


class ActionPlanDB(Base):
    """
    Complete action plans for addressing incidents (Agent 6: Action Planning).
    Groups related actions with risk assessment.
    """
    __tablename__ = "action_plans"

    plan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey('incidents.incident_id'), nullable=False)
    hypothesis_id = Column(UUID(as_uuid=True), ForeignKey('incident_hypotheses.hypothesis_id'))
    created_at = Column(DateTime, default=func.now())
    
    # Plan metadata
    total_risk_score = Column(Float)
    estimated_blast_radius = Column(String(255))

    __table_args__ = (
        Index('idx_incident_plan', 'incident_id'),
    )


class ActionDB(Base):
    """
    Individual actions within an action plan (Agent 6: Action Planning).
    Contains specific action types, payloads, and execution tracking.
    """
    __tablename__ = "actions"

    action_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('action_plans.plan_id'), nullable=False)
    
    # Action details
    action_type = Column(String(50), nullable=False)  # support_guidance, proactive_comms, escalate_eng, mitigation, docs_update
    priority = Column(Integer, nullable=False)  # 1 = highest
    
    # Reasoning
    rationale = Column(Text, nullable=False)
    expected_impact = Column(Text)
    
    # Risk assessment
    risk_level = Column(String(20), nullable=False)  # low, medium, high
    requires_approval = Column(Boolean, nullable=False)
    rollback_plan = Column(Text)
    
    # Action-specific payload
    payload = Column(JSONB, nullable=False)  # Flexible structure per action_type
    
    # Execution tracking
    status = Column(String(50), default='planned')  # planned, approved, executing, completed, failed
    execution_result = Column(Text)
    external_id = Column(String(255))  # e.g., GitHub issue #, Slack message timestamp
    
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_plan', 'plan_id'),
        Index('idx_status_action', 'status'),
        Index('idx_priority', 'priority'),
    )


class ApprovalDB(Base):
    """
    Approval records for high-risk actions (Agent 7: Policy & Approval Gate).
    Tracks human approval workflow and policy checks.
    """
    __tablename__ = "approvals"

    approval_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_id = Column(UUID(as_uuid=True), ForeignKey('actions.action_id'), nullable=False)
    
    # Approval status
    status = Column(String(20), nullable=False)  # pending, approved, rejected
    
    # Requester context
    requested_at = Column(DateTime, default=func.now())
    requester = Column(String(100), nullable=False, default='system')
    
    # Approval context
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    
    # Policy check results
    policy_checks = Column(JSONB, nullable=False)  # {check_name: passed}
    required_approver_role = Column(String(100))

    __table_args__ = (
        Index('idx_action_approval', 'action_id'),
        Index('idx_status_approval', 'status'),
    )


class ExecutedActionDB(Base):
    """
    Audit records of executed actions (Agent 8: Execution).
    Comprehensive logging of action execution with external references.
    """
    __tablename__ = "actions_executed"

    execution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_id = Column(UUID(as_uuid=True), ForeignKey('actions.action_id'), nullable=False)
    
    # Execution metadata
    executed_at = Column(DateTime, default=func.now())
    executed_by = Column(String(100), nullable=False, default='system')
    
    # Results
    success = Column(Boolean, nullable=False)
    execution_log = Column(Text, nullable=False)
    external_references = Column(JSONB)  # {"github_issue": "#123", "slack_ts": "..."}
    
    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Payload snapshot (for audit)
    action_payload_snapshot = Column(JSONB)

    __table_args__ = (
        Index('idx_action_exec', 'action_id'),
        Index('idx_executed_at', 'executed_at'),
        Index('idx_success', 'success'),
    )


class ActionOutcomeDB(Base):
    """
    Feedback measurements for learning (Agent 9: Feedback & Learning).
    Tracks action effectiveness for future decision-making.
    """
    __tablename__ = "action_outcomes"

    outcome_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), ForeignKey('actions_executed.execution_id'), nullable=False)
    
    # Measurement
    measured_at = Column(DateTime, default=func.now())
    outcome = Column(String(20), nullable=False)  # helped, neutral, harmed
    
    # Metrics
    ticket_volume_before = Column(Integer)
    ticket_volume_after = Column(Integer)
    incident_resolved = Column(Boolean)
    merchant_feedback = Column(Text)
    
    # Learning signals
    confidence_score = Column(Float)  # How confident are we in this outcome assessment?
    should_update_patterns = Column(Boolean, default=False)

    __table_args__ = (
        Index('idx_execution', 'execution_id'),
        Index('idx_outcome', 'outcome'),
    )


class ActionSimulationDB(Base):
    """
    Simulation runs for "what-if" analysis (Priority 9: Simulation Mode).
    Stores predicted outcomes and comparison to alternatives before execution.
    """
    __tablename__ = "action_simulations"

    simulation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey('incidents.incident_id'), nullable=False)
    action_id = Column(UUID(as_uuid=True), nullable=True)  # May be from request, not persisted in actions table
    action_type = Column(String(50), nullable=False)
    action_payload = Column(JSONB, nullable=False)

    # Simulation outputs
    predicted_outcomes = Column(JSONB, nullable=False)
    confidence_in_prediction = Column(Float, nullable=False)
    side_effects = Column(JSONB, nullable=False)
    alternative_outcomes = Column(JSONB, nullable=False)
    comparison_to_alternatives = Column(JSONB, nullable=False)
    ranked_alternatives = Column(JSONB, nullable=False)

    # Approval tracking
    approval_id = Column(UUID(as_uuid=True), ForeignKey('approvals.approval_id'))
    approved = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index('idx_sim_incident', 'incident_id'),
        Index('idx_sim_action_type', 'action_type'),
        Index('idx_sim_created_at', 'created_at'),
    )


class MerchantProfileDB(Base):
    """
    Merchant context for event enrichment.
    Provides migration status, industry, and risk profile data.
    """
    __tablename__ = "merchant_profiles"

    merchant_id = Column(String(100), primary_key=True)
    
    # Migration status
    migration_stage = Column(Integer, nullable=False)  # 1, 2, 3, or 4
    migrated_at = Column(DateTime)
    
    # Merchant characteristics
    industry = Column(String(100))
    storefront_framework = Column(String(100))  # shopify, custom, react, etc.
    region = Column(String(100))
    monthly_volume = Column(Integer)  # Transaction count
    
    # Risk profile
    high_value = Column(Boolean, default=False)  # VIP merchant
    
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_stage', 'migration_stage'),
        Index('idx_industry', 'industry'),
    )


class KnownPatternDB(Base):
    """
    Learned patterns from successful resolutions (Agent 9: Learning).
    Builds institutional knowledge for future decision-making.
    """
    __tablename__ = "known_patterns"

    pattern_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signature = Column(String(255), nullable=False)
    root_cause_type = Column(String(50), nullable=False)
    successful_action_type = Column(String(50), nullable=False)
    
    # Success metrics
    success_count = Column(Integer, default=1)
    total_attempts = Column(Integer, default=1)
    success_rate = Column(Float)
    
    last_seen = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint('signature', 'successful_action_type', name='uq_signature_action'),
        Index('idx_signature_pattern', 'signature'),
    )


class PolicyThresholdDB(Base):
    """
    Dynamic policy thresholds learned from human approver patterns (Agent 7 & 9: Learning).
    Tracks approval policies and their evolution based on human decisions.
    
    Enables the system to learn:
    - "Approvers trust high-confidence escalations → auto-approve these"
    - "Approvers reject low-confidence comms → require human review"
    - "Approvers fast-track critical incidents → adjust escalation threshold"
    """
    __tablename__ = "policy_thresholds"

    threshold_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Policy identification
    policy_name = Column(String(100), nullable=False)  # e.g., "escalation_confidence_threshold"
    applies_to = Column(String(50), nullable=False)  # e.g., "escalate_eng", "proactive_comms"
    
    # Threshold values
    current_value = Column(Float, nullable=False)  # Current threshold (e.g., 0.6)
    previous_value = Column(Float)  # Previous threshold for comparison
    
    # Learning metadata
    based_on_n_approvals = Column(Integer, default=0)  # How many approvals informed this?
    approval_rate = Column(Float)  # Approval rate at this threshold
    rejection_rate = Column(Float)  # Rejection rate at this threshold
    
    # Audit trail
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    update_reason = Column(Text)  # Why was it updated? e.g., "Approvers rejected 80% of <0.5 confidence actions"
    updated_by = Column(String(100), default='system')  # Who/what updated it
    
    # Statistical confidence
    confidence_in_change = Column(Float)  # How confident in this update? (0-1)
    sample_size = Column(Integer)  # Sample size for statistical validity

    __table_args__ = (
        UniqueConstraint('policy_name', 'applies_to', name='uq_policy_applies_to'),
        Index('idx_policy_applies', 'applies_to'),
        Index('idx_updated_at', 'updated_at'),
    )
