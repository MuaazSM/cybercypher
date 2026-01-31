import numpy as np
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from uuid import uuid4
from models.anomalies import AnomalySignal, AnomalyReport
from models.events import CleanEvent
from db.models import CleanEventDB
import logging

logger = logging.getLogger(__name__)


class AnomalyDetectionAgent:
    """Detect emerging patterns before they become incidents"""
    
    def __init__(self):
        self.name = "AnomalyDetector"
        # Anomaly thresholds
        self.z_score_threshold = 2.0  # 2 std deviations = ~95% confidence
        self.rate_deviation_threshold = 2.5  # 2.5x baseline for rate anomaly
        self.velocity_threshold = 0.5  # events/hour^2 (acceleration)
        self.stage_concentration_threshold = 0.7  # 70% in single stage = anomaly
    
    def scan_for_anomalies(
        self,
        db: Session,
        lookback_minutes: int = 120
    ) -> AnomalyReport:
        """
        Scan all signatures in recent time window for emerging anomalies.
        
        This runs CONTINUOUSLY (every 5-10 minutes) to catch problems early.
        """
        print(f"[AnomalyDetector] Scanning for anomalies (lookback: {lookback_minutes}m)")
        
        # Get recent events
        cutoff_time = datetime.utcnow() - timedelta(minutes=lookback_minutes)
        recent_events = db.query(CleanEventDB).filter(
            CleanEventDB.timestamp >= cutoff_time
        ).all()
        
        if not recent_events:
            print("[AnomalyDetector] No recent events to scan")
            return AnomalyReport(
                signals=[],
                total_signatures_scanned=0,
                signatures_with_anomalies=0,
                max_confidence=0.0,
                high_severity_count=0,
                escalation_recommended=False
            )
        
        # Group events by signature
        events_by_signature: Dict[str, List] = {}
        for event in recent_events:
            if event.signature not in events_by_signature:
                events_by_signature[event.signature] = []
            events_by_signature[event.signature].append(event)
        
        signals: List[AnomalySignal] = []
        
        # Analyze each signature
        for signature, events in events_by_signature.items():
            anomaly_signals = self._analyze_signature(
                signature, events, db, lookback_minutes
            )
            signals.extend(anomaly_signals)
        
        # Create report
        high_severity_signals = [s for s in signals if s.severity_estimate == "high"]
        
        report = AnomalyReport(
            signals=signals,
            total_signatures_scanned=len(events_by_signature),
            signatures_with_anomalies=len([s for s in signals]),
            max_confidence=max([s.confidence for s in signals], default=0.0),
            high_severity_count=len(high_severity_signals),
            escalation_recommended=len(high_severity_signals) > 0 or len(signals) >= 2
        )
        
        # Print summary
        self._print_scan_summary(report)
        
        return report
    
    def _analyze_signature(
        self,
        signature: str,
        recent_events: List,
        db: Session,
        lookback_minutes: int
    ) -> List[AnomalySignal]:
        """Analyze single signature for all anomaly types"""
        
        signals: List[AnomalySignal] = []
        
        # Build baseline from older data (>lookback_minutes ago)
        baseline_data = self._build_baseline(signature, db, lookback_minutes)
        
        if not baseline_data or baseline_data["baseline_rate"] == 0:
            return signals  # Skip if no baseline
        
        # Rate anomalies
        rate_signal = self._detect_rate_anomalies(
            signature, recent_events, baseline_data
        )
        if rate_signal:
            signals.append(rate_signal)
        
        # Velocity anomalies (acceleration)
        velocity_signal = self._detect_velocity_anomalies(
            signature, db, lookback_minutes
        )
        if velocity_signal:
            signals.append(velocity_signal)
        
        # Stage concentration anomalies
        stage_signal = self._detect_stage_anomalies(
            signature, recent_events, baseline_data
        )
        if stage_signal:
            signals.append(stage_signal)
        
        return signals
    
    def _build_baseline(
        self,
        signature: str,
        db: Session,
        lookback_minutes: int,
        baseline_window_hours: int = 24
    ) -> Optional[Dict]:
        """
        Build statistical baseline for a signature using historical data.
        
        Uses data from {baseline_window_hours} ago, excluding last {lookback_minutes}.
        """
        
        # Time windows
        now = datetime.utcnow()
        recent_cutoff = now - timedelta(minutes=lookback_minutes)
        baseline_start = now - timedelta(hours=baseline_window_hours)
        baseline_end = now - timedelta(minutes=lookback_minutes + 60)  # +60min buffer
        
        # Get baseline events
        baseline_events = db.query(CleanEventDB).filter(
            CleanEventDB.signature == signature,
            CleanEventDB.timestamp >= baseline_start,
            CleanEventDB.timestamp < baseline_end
        ).all()
        
        if len(baseline_events) < 5:
            # Not enough historical data
            return None
        
        # Calculate baseline metrics
        baseline_rate = len(baseline_events) / (
            (baseline_end - baseline_start).total_seconds() / 3600
        )
        
        # Calculate rate variance
        hourly_counts = self._get_hourly_counts(baseline_events)
        if len(hourly_counts) > 1:
            baseline_std = np.std(hourly_counts)
        else:
            baseline_std = baseline_rate * 0.2  # Assume 20% variance if only 1 hour
        
        return {
            "baseline_rate": baseline_rate,
            "baseline_std": baseline_std,
            "baseline_event_count": len(baseline_events),
            "baseline_merchants": len(set(e.merchant_id for e in baseline_events)),
            "stage_distribution": self._get_stage_distribution(baseline_events)
        }
    
    def _detect_rate_anomalies(
        self,
        signature: str,
        recent_events: List,
        baseline_data: Dict
    ) -> Optional[AnomalySignal]:
        """
        Detect rate anomalies using z-score.
        
        Z-score = (current_rate - baseline_mean) / baseline_std
        Anomaly if z-score > threshold AND current > baseline
        """
        
        current_rate = len(recent_events) / 2  # Assuming 120min lookback = 2 hours
        baseline_rate = baseline_data["baseline_rate"]
        baseline_std = baseline_data["baseline_std"]
        
        if baseline_rate == 0 or baseline_std == 0:
            return None
        
        # Calculate z-score
        z_score = (current_rate - baseline_rate) / baseline_std
        
        # Deviation factor
        deviation_factor = current_rate / baseline_rate if baseline_rate > 0 else 1.0
        
        # Check thresholds
        # Z-score > 2.0 means 95% confidence it's not baseline
        # BUT confidence capped at 0.7 for early warnings
        if z_score > self.z_score_threshold and deviation_factor > self.rate_deviation_threshold:
            
            # Map z-score to confidence (0.3-0.7)
            confidence = min(0.3 + (z_score / 4.0) * 0.4, 0.7)
            
            return AnomalySignal(
                anomaly_type="rate",
                signature=signature,
                confidence=confidence,
                current_value=current_rate,
                baseline_value=baseline_rate,
                deviation_factor=deviation_factor,
                z_score=z_score,
                event_count=len(recent_events),
                merchant_count=len(set(e.merchant_id for e in recent_events)),
                time_window_minutes=120,
                severity_estimate=self._severity_from_deviation(deviation_factor),
                recommended_action=(
                    f"Rate elevated {deviation_factor:.1f}x baseline. "
                    f"Monitor for next 30-60 minutes. If stays elevated, escalate to incident detection."
                ),
                sample_event_ids=[uuid4() for _ in recent_events[:5]]
            )
        
        return None
    
    def _detect_velocity_anomalies(
        self,
        signature: str,
        db: Session,
        lookback_minutes: int
    ) -> Optional[AnomalySignal]:
        """
        Detect velocity anomalies (acceleration of error rate).
        
        Velocity = d(rate)/dt (events per hour per hour)
        High velocity = problem is GETTING WORSE rapidly
        """
        
        now = datetime.utcnow()
        
        # Get events in 3 time windows to detect acceleration
        window1_start = now - timedelta(minutes=lookback_minutes)
        window2_start = now - timedelta(minutes=lookback_minutes // 2)
        window3_start = now - timedelta(minutes=lookback_minutes // 4)
        
        events_w1 = db.query(CleanEventDB).filter(
            CleanEventDB.signature == signature,
            CleanEventDB.timestamp >= window1_start,
            CleanEventDB.timestamp < window2_start
        ).count()
        
        events_w2 = db.query(CleanEventDB).filter(
            CleanEventDB.signature == signature,
            CleanEventDB.timestamp >= window2_start,
            CleanEventDB.timestamp < window3_start
        ).count()
        
        events_w3 = db.query(CleanEventDB).filter(
            CleanEventDB.signature == signature,
            CleanEventDB.timestamp >= window3_start,
            CleanEventDB.timestamp <= now
        ).count()
        
        # Calculate rates for each window (events per hour)
        window_duration_hours = lookback_minutes / 4 / 60
        rate_w1 = events_w1 / window_duration_hours if window_duration_hours > 0 else 0
        rate_w2 = events_w2 / window_duration_hours if window_duration_hours > 0 else 0
        rate_w3 = events_w3 / window_duration_hours if window_duration_hours > 0 else 0
        
        # Calculate velocity (rate of change)
        velocity = (rate_w3 - rate_w1) / (lookback_minutes / 60) if lookback_minutes > 0 else 0
        
        # Anomaly if velocity > threshold (getting worse)
        if velocity > self.velocity_threshold:
            
            # Confidence based on velocity magnitude
            confidence = min(0.35 + (velocity / 1.0) * 0.3, 0.7)
            
            recent_events = db.query(CleanEventDB).filter(
                CleanEventDB.signature == signature,
                CleanEventDB.timestamp >= window3_start
            ).all()
            
            return AnomalySignal(
                anomaly_type="velocity",
                signature=signature,
                confidence=confidence,
                current_value=velocity,
                baseline_value=0.0,
                deviation_factor=1.0,  # Not applicable
                velocity=velocity,
                event_count=events_w1 + events_w2 + events_w3,
                merchant_count=len(set(e.merchant_id for e in recent_events)),
                time_window_minutes=lookback_minutes,
                severity_estimate="high" if velocity > 1.0 else "medium",
                recommended_action=(
                    f"Error rate accelerating at {velocity:.2f} events/hour^2. "
                    f"URGENT: Monitor continuously. May escalate quickly."
                ),
                sample_event_ids=[uuid4() for _ in recent_events[:5]]
            )
        
        return None
    
    def _detect_stage_anomalies(
        self,
        signature: str,
        recent_events: List,
        baseline_data: Dict
    ) -> Optional[AnomalySignal]:
        """
        Detect stage concentration anomalies.
        
        Anomaly = errors suddenly concentrated in single stage
        Indicates localized problem (not systemic), easier to fix
        """
        
        # Get current stage distribution
        current_stage_dist = self._get_stage_distribution(recent_events)
        baseline_stage_dist = baseline_data.get("stage_distribution", {})
        
        if not current_stage_dist:
            return None
        
        # Find max concentration
        max_stage_pct = max(current_stage_dist.values())
        max_stage = max(current_stage_dist, key=current_stage_dist.get)
        
        # Check if concentration changed significantly
        baseline_max_pct = baseline_stage_dist.get(max_stage, 0.2)
        
        if max_stage_pct > self.stage_concentration_threshold:
            
            # Concentration is high
            concentration_shift = max_stage_pct - baseline_max_pct
            
            # Confidence based on how concentrated it is
            confidence = min(0.4 + (max_stage_pct - 0.7) / 0.3 * 0.3, 0.7)
            
            return AnomalySignal(
                anomaly_type="stage_concentration",
                signature=signature,
                confidence=confidence,
                current_value=max_stage_pct * 100,  # As percentage
                baseline_value=baseline_max_pct * 100,
                deviation_factor=max_stage_pct / baseline_max_pct if baseline_max_pct > 0 else 1.0,
                stage_concentration=current_stage_dist,
                event_count=len(recent_events),
                merchant_count=len(set(e.merchant_id for e in recent_events)),
                time_window_minutes=120,
                severity_estimate="medium" if max_stage_pct > 0.8 else "low",
                recommended_action=(
                    f"{max_stage_pct*100:.0f}% of errors in Stage {max_stage}. "
                    f"Suggests localized migration issue. Check Stage {max_stage} deployment/config."
                ),
                sample_event_ids=[uuid4() for _ in recent_events[:5]]
            )
        
        return None
    
    # Helper methods
    
    def _get_hourly_counts(self, events: List) -> np.ndarray:
        """Bin events by hour and return counts"""
        if not events:
            return np.array([])
        
        # Create hourly bins
        timestamps = [e.timestamp for e in events]
        min_time = min(timestamps)
        max_time = max(timestamps)
        
        hours = int((max_time - min_time).total_seconds() / 3600) + 1
        if hours < 2:
            hours = 2
        
        counts = np.zeros(hours)
        for ts in timestamps:
            hour_idx = int((ts - min_time).total_seconds() / 3600)
            counts[hour_idx] += 1
        
        return counts
    
    def _get_stage_distribution(self, events: List) -> Dict[int, float]:
        """Get percentage of events per migration stage"""
        if not events:
            return {}
        
        stage_counts = {}
        for event in events:
            stage = event.migration_stage
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        
        total = len(events)
        return {stage: count / total for stage, count in stage_counts.items()}
    
    def _severity_from_deviation(self, deviation_factor: float) -> str:
        """Map deviation factor to severity"""
        if deviation_factor > 5.0:
            return "high"
        elif deviation_factor > 3.0:
            return "medium"
        else:
            return "low"
    
    def _print_scan_summary(self, report: AnomalyReport):
        """Print scan results"""
        print(f"[AnomalyDetector] Scan complete")
        print(f"  Signatures scanned: {report.total_signatures_scanned}")
        print(f"  Anomalies detected: {len(report.signals)}")
        
        if report.signals:
            print(f"  Max confidence: {report.max_confidence:.2f}")
            print(f"  High severity: {report.high_severity_count}")
            
            for signal in report.signals[:3]:  # Print top 3
                print(f"\n  ⚠ {signal.anomaly_type.upper()}: {signal.signature}")
                print(f"      Confidence: {signal.confidence:.2f}")
                print(f"      Deviation: {signal.deviation_factor:.2f}x baseline")
                print(f"      Action: {signal.recommended_action[:60]}...")
        
        if report.escalation_recommended:
            print(f"\n  🚨 ESCALATION RECOMMENDED: Review above anomalies")
