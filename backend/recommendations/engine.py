"""
SAFEGUARD AI - Recommendation Engine
Generates prioritized, structured safety recommendations from risk and compliance findings.
"""
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from backend.risk_engine.engine import RiskAssessment, RiskFactor
from backend.compliance.engine import ComplianceResult
from backend.rag.pipeline import rag_pipeline, RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class SafetyRecommendation:
    """A structured, prioritized safety recommendation."""
    rec_id: str
    machine_id: str
    issue: str
    severity: str           # low / moderate / elevated / high / critical
    immediate_action: str
    corrective_action: str
    preventive_action: str
    priority: int           # 1 = highest
    reason: str
    supporting_evidence: List[Dict[str, Any]]
    is_ai_generated: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rec_id": self.rec_id,
            "machine_id": self.machine_id,
            "issue": self.issue,
            "severity": self.severity,
            "immediate_action": self.immediate_action,
            "corrective_action": self.corrective_action,
            "preventive_action": self.preventive_action,
            "priority": self.priority,
            "reason": self.reason,
            "supporting_evidence": self.supporting_evidence,
            "is_ai_generated": self.is_ai_generated,
            "timestamp": self.timestamp.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Rule-based recommendation templates
# ─────────────────────────────────────────────────────────────────────────────

def _rec_high_temperature(machine_id: str, factor: RiskFactor, evidence: List[RetrievedChunk]) -> SafetyRecommendation:
    temp = factor.value
    critical = factor.threshold
    severity = "critical" if temp > critical * 0.95 else "high"
    return SafetyRecommendation(
        rec_id=f"REC-{machine_id}-TEMP-{uuid.uuid4().hex[:6].upper()}",
        machine_id=machine_id,
        issue=f"High temperature detected: {temp:.1f}°C (threshold: {critical}°C)",
        severity=severity,
        immediate_action=(
            "Reduce machine load immediately. Check cooling system airflow. "
            "If temperature continues rising, initiate controlled shutdown."
        ),
        corrective_action=(
            "Inspect and clean all cooling fans, vents, and heat exchangers. "
            "Check coolant level and pump operation. Replace thermal paste on heat sinks if applicable. "
            "Verify ambient temperature in machine bay."
        ),
        preventive_action=(
            "Implement temperature trending monitoring. Schedule quarterly cooling system maintenance. "
            "Establish automated alerts at 85% of temperature threshold. "
            "Review production scheduling to avoid thermal buildup."
        ),
        priority=1 if severity == "critical" else 2,
        reason=(
            f"Temperature {temp:.1f}°C has exceeded the configured safe operating limit. "
            "Sustained high temperature accelerates insulation degradation, increases "
            "bearing wear rate, and raises fire risk."
        ),
        supporting_evidence=[{"source": c.source, "section": c.section, "content": c.content[:200]}
                              for c in evidence],
    )


def _rec_high_vibration(machine_id: str, factor: RiskFactor, evidence: List[RetrievedChunk]) -> SafetyRecommendation:
    vib = factor.value
    severity = "critical" if factor.contribution >= 15 else "high"
    return SafetyRecommendation(
        rec_id=f"REC-{machine_id}-VIB-{uuid.uuid4().hex[:6].upper()}",
        machine_id=machine_id,
        issue=f"Excessive vibration: {vib:.2f} mm/s RMS (ISO 10816-3 Zone {'D' if vib > 7.1 else 'C'})",
        severity=severity,
        immediate_action=(
            "Reduce operating speed. Check for loose fasteners, unbalanced rotating parts, "
            "or misaligned couplings. If vibration is in Zone D (>7.1 mm/s), shut down immediately."
        ),
        corrective_action=(
            "Perform vibration spectrum analysis to identify frequency components. "
            "Check bearing condition using ultrasound or vibration analysis. "
            "Balance rotating assemblies. Inspect flexible couplings and belts. "
            "Tighten all structural fasteners."
        ),
        preventive_action=(
            "Implement vibration-based predictive maintenance program. "
            "Install continuous vibration monitoring on critical bearings. "
            "Establish vibration baselines and trend against ISO 10816-3 zones. "
            "Schedule bearing replacement at prescribed intervals."
        ),
        priority=1 if severity == "critical" else 2,
        reason=(
            f"Vibration at {vib:.2f} mm/s RMS exceeds safe operating zone. "
            "Excessive vibration causes accelerated bearing failure, fatigue cracking, "
            "and eventual catastrophic mechanical failure per ISO 10816-3."
        ),
        supporting_evidence=[{"source": c.source, "section": c.section, "content": c.content[:200]}
                              for c in evidence],
    )


def _rec_guard_issue(machine_id: str, evidence: List[RetrievedChunk]) -> SafetyRecommendation:
    return SafetyRecommendation(
        rec_id=f"REC-{machine_id}-GUARD-{uuid.uuid4().hex[:6].upper()}",
        machine_id=machine_id,
        issue="Machine guard is open or removed during operation",
        severity="critical",
        immediate_action=(
            "STOP MACHINE IMMEDIATELY. "
            "Do not restart until guard is properly reinstalled and verified closed. "
            "Remove personnel from hazardous zone."
        ),
        corrective_action=(
            "Reinstall guard and verify it is properly secured. "
            "Check interlock switch alignment and function. "
            "Inspect guard for damage and replace if necessary. "
            "Investigate why the guard was removed or opened."
        ),
        preventive_action=(
            "Implement guard monitoring with automatic machine stop on guard opening. "
            "Train operators on guard requirements (OSHA 1910.212). "
            "Perform monthly guard inspection and document results. "
            "Review procedures to ensure guards are not bypassed for production convenience."
        ),
        priority=1,
        reason=(
            "Open guard creates direct operator exposure to moving parts, cutting tools, "
            "or nip points. This is a critical OSHA and ISO 13849-1 violation. "
            "Severity: CRITICAL — risk of severe injury or fatality."
        ),
        supporting_evidence=[{"source": c.source, "section": c.section, "content": c.content[:200]}
                              for c in evidence],
    )


def _rec_maintenance_overdue(machine_id: str, evidence: List[RetrievedChunk]) -> SafetyRecommendation:
    return SafetyRecommendation(
        rec_id=f"REC-{machine_id}-MAINT-{uuid.uuid4().hex[:6].upper()}",
        machine_id=machine_id,
        issue="Scheduled maintenance is overdue",
        severity="high",
        immediate_action=(
            "Schedule maintenance immediately. Flag machine for priority maintenance window. "
            "Increase monitoring frequency until maintenance is completed."
        ),
        corrective_action=(
            "Perform all overdue maintenance tasks per maintenance checklist. "
            "Document all findings and replaced components. "
            "Reset maintenance interval counter after completion. "
            "Inspect for any wear or damage that may have occurred during the overdue period."
        ),
        preventive_action=(
            "Implement computerized maintenance management system (CMMS). "
            "Set automated maintenance reminders 2 weeks before due date. "
            "Review maintenance intervals — adjust if too long given actual operating conditions. "
            "Assign maintenance ownership to specific technicians."
        ),
        priority=2,
        reason=(
            "Overdue maintenance increases probability of unexpected failure by 30-50%. "
            "Per NFPA 79 §12.5, machines shall be maintained per manufacturer schedule. "
            "Operating beyond maintenance interval voids many safety certifications."
        ),
        supporting_evidence=[{"source": c.source, "section": c.section, "content": c.content[:200]}
                              for c in evidence],
    )


def _rec_high_pressure(machine_id: str, factor: RiskFactor, evidence: List[RetrievedChunk]) -> SafetyRecommendation:
    pressure = factor.value
    severity = "critical" if factor.contribution >= 12 else "high"
    return SafetyRecommendation(
        rec_id=f"REC-{machine_id}-PRES-{uuid.uuid4().hex[:6].upper()}",
        machine_id=machine_id,
        issue=f"System pressure {pressure:.1f} bar exceeds safe operating limit",
        severity=severity,
        immediate_action=(
            "Reduce system load to lower pressure. "
            "Verify pressure relief valve is set correctly and functioning. "
            "If pressure continues rising, initiate emergency shutdown."
        ),
        corrective_action=(
            "Inspect and calibrate pressure relief valve. "
            "Check for blockages in pressure lines or heat exchangers. "
            "Inspect seals, hoses, and fittings for condition. "
            "Verify pressure gauge accuracy with calibrated reference."
        ),
        preventive_action=(
            "Implement pressure monitoring with high-pressure alarm at 90% of maximum. "
            "Schedule annual pressure relief valve testing and calibration. "
            "Perform regular inspection of hydraulic/pneumatic system components. "
            "Establish written procedure for pressure system isolation and depressurization."
        ),
        priority=1 if severity == "critical" else 2,
        reason=(
            f"Pressure {pressure:.1f} bar exceeds configured maximum. "
            "Per ISO 4413 §5.4, every system shall be protected by pressure relief valve. "
            "Overpressure risks pipe burst, seal failure, and fluid injection injuries."
        ),
        supporting_evidence=[{"source": c.source, "section": c.section, "content": c.content[:200]}
                              for c in evidence],
    )


def _rec_estop_active(machine_id: str, evidence: List[RetrievedChunk]) -> SafetyRecommendation:
    return SafetyRecommendation(
        rec_id=f"REC-{machine_id}-ESTOP-{uuid.uuid4().hex[:6].upper()}",
        machine_id=machine_id,
        issue="Emergency stop is active — machine halted",
        severity="critical",
        immediate_action=(
            "Do NOT reset e-stop until the cause has been identified and corrected. "
            "Secure the area and investigate the reason for e-stop activation."
        ),
        corrective_action=(
            "Complete root cause investigation. "
            "Correct underlying condition that triggered e-stop. "
            "Verify all safety systems are functioning before restart. "
            "Follow restart procedure and obtain supervisor authorization."
        ),
        preventive_action=(
            "Analyze e-stop activation history for patterns. "
            "Review machine operation procedures and operator training. "
            "Consider whether additional safeguards are needed to prevent the root cause."
        ),
        priority=1,
        reason=(
            "E-stop activation indicates a safety-critical event occurred. "
            "Per ISO 13849-1 §5.3, e-stop shall remain latched until manually reset "
            "after investigation. Do not reset without root cause resolution."
        ),
        supporting_evidence=[{"source": c.source, "section": c.section, "content": c.content[:200]}
                              for c in evidence],
    )


class RecommendationEngine:
    """
    Generates prioritized safety recommendations from risk assessment and compliance check results.
    Uses rule-based logic augmented with RAG evidence.
    IBM WatsonX LLM can optionally enhance recommendation text.
    """

    def generate(
        self,
        risk_assessment: RiskAssessment,
        compliance_results: List[ComplianceResult],
        machine_type: str,
    ) -> List[SafetyRecommendation]:
        """Generate all applicable recommendations, sorted by priority."""
        recommendations: List[SafetyRecommendation] = []
        evidence_cache: Dict[str, List[RetrievedChunk]] = {}

        def get_evidence(query: str, key: str) -> List[RetrievedChunk]:
            if key not in evidence_cache:
                try:
                    evidence_cache[key] = rag_pipeline.retrieve(query, machine_type=machine_type, top_k=2)
                except Exception:
                    evidence_cache[key] = []
            return evidence_cache[key]

        # From risk factors
        for factor in risk_assessment.risk_factors:
            if factor.category == "temperature" and factor.contribution > 5:
                ev = get_evidence("temperature safe operating limit thermal protection", "temperature")
                recommendations.append(_rec_high_temperature(risk_assessment.machine_id, factor, ev))

            elif factor.category == "vibration" and factor.contribution > 5:
                ev = get_evidence("vibration evaluation criteria ISO 10816", "vibration")
                recommendations.append(_rec_high_vibration(risk_assessment.machine_id, factor, ev))

            elif factor.category == "guard":
                ev = get_evidence("machine guard protection OSHA ISO 13849", "guard")
                recommendations.append(_rec_guard_issue(risk_assessment.machine_id, ev))

            elif factor.category == "maintenance":
                ev = get_evidence("maintenance requirements NFPA 79 schedule", "maintenance")
                recommendations.append(_rec_maintenance_overdue(risk_assessment.machine_id, ev))

            elif factor.category == "pressure" and factor.contribution > 5:
                ev = get_evidence("hydraulic pressure maximum allowable ISO 4413", "pressure")
                recommendations.append(_rec_high_pressure(risk_assessment.machine_id, factor, ev))

            elif factor.category == "emergency_stop":
                ev = get_evidence("emergency stop function ISO 13849 NFPA 79", "estop")
                recommendations.append(_rec_estop_active(risk_assessment.machine_id, ev))

        # From compliance violations
        seen_categories = {r.category for r in risk_assessment.risk_factors}
        for compliance in compliance_results:
            if compliance.status == "non_compliant":
                # Avoid duplicate recommendations
                if "guard" in compliance.standard_reference.lower() and "guard" not in seen_categories:
                    ev = get_evidence("machine guard OSHA ISO 13849", "guard")
                    recommendations.append(_rec_guard_issue(risk_assessment.machine_id, ev))
                    seen_categories.add("guard")

        # De-duplicate (keep one per category)
        seen = set()
        unique_recs = []
        for rec in recommendations:
            key = rec.issue[:30]
            if key not in seen:
                seen.add(key)
                unique_recs.append(rec)

        # Sort by priority, then severity
        severity_order = {"critical": 0, "high": 1, "elevated": 2, "moderate": 3, "low": 4}
        unique_recs.sort(key=lambda r: (r.priority, severity_order.get(r.severity, 5)))

        # Re-assign sequential priorities
        for i, rec in enumerate(unique_recs):
            rec.priority = i + 1

        return unique_recs


# Module-level singleton
recommendation_engine = RecommendationEngine()
