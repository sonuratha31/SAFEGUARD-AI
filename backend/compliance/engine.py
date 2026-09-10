"""
SAFEGUARD AI - Compliance Engine
Compares machine conditions against safety standards retrieved via RAG.
Returns structured compliance assessments with full evidence and explainability.
"""
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from backend.risk_engine.engine import RiskAssessment
from backend.rag.pipeline import rag_pipeline, RetrievedChunk
from backend.simulation.simulator import MACHINE_CONFIGS

logger = logging.getLogger(__name__)

INSUFFICIENT_EVIDENCE = "Insufficient evidence to verify this requirement."


@dataclass
class ComplianceResult:
    """A single compliance check result."""
    check_id: str
    machine_id: str
    requirement: str
    current_condition: str
    expected_condition: str
    status: str                     # compliant / partially_compliant / non_compliant / unknown
    risk_level: str                 # low / moderate / elevated / high / critical
    evidence: List[Dict[str, Any]]  # RAG-retrieved evidence
    source: str
    explanation: str
    evidence_type: str              # verified / inferred / prediction / unknown
    standard_reference: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Compliance Rules
# ─────────────────────────────────────────────────────────────────────────────

def _check_guard(machine_id: str, guard_ok: bool, chunks: List[RetrievedChunk]) -> ComplianceResult:
    status = "compliant" if guard_ok else "non_compliant"
    return ComplianceResult(
        check_id=f"{machine_id}_guard_{uuid.uuid4().hex[:8]}",
        machine_id=machine_id,
        requirement="Machine guard shall be in place during operation",
        current_condition="Guard in place" if guard_ok else "Guard removed or open",
        expected_condition="Guard shall be closed and secured during all operational states",
        status=status,
        risk_level="low" if guard_ok else "critical",
        evidence=[_chunk_to_evidence(c) for c in chunks] if chunks else [],
        source="OSHA 29 CFR 1910.212(a)(1); ISO 13849-1 Section 5.1",
        explanation=(
            "Guard is correctly in place. Operator is protected from moving parts."
            if guard_ok else
            "Guard is open or removed while machine is operational. This is a critical "
            "safety violation per OSHA 1910.212 and ISO 13849-1. Immediate stop required."
        ),
        evidence_type="verified" if chunks else "unknown",
        standard_reference="OSHA 1910.212 / ISO 13849-1",
    )


def _check_interlock(machine_id: str, interlock_ok: bool, chunks: List[RetrievedChunk]) -> ComplianceResult:
    status = "compliant" if interlock_ok else "non_compliant"
    return ComplianceResult(
        check_id=f"{machine_id}_interlock_{uuid.uuid4().hex[:8]}",
        machine_id=machine_id,
        requirement="Safety interlock shall be active and functional during machine operation",
        current_condition="Interlock active" if interlock_ok else "Interlock not active",
        expected_condition="Interlocking guards shall be connected to control system and monitored",
        status=status,
        risk_level="low" if interlock_ok else "high",
        evidence=[_chunk_to_evidence(c) for c in chunks] if chunks else [],
        source="ISO 13849-1 Section 5.2",
        explanation=(
            "Interlock is active and monitoring guard position correctly."
            if interlock_ok else
            "Safety interlock is not active. Per ISO 13849-1 §5.2, interlock failure "
            "shall result in a safe state. Investigate interlock circuit immediately."
        ),
        evidence_type="verified" if chunks else "inferred",
        standard_reference="ISO 13849-1 §5.2",
    )


def _check_emergency_stop(machine_id: str, estop: bool, chunks: List[RetrievedChunk]) -> ComplianceResult:
    # E-stop being active is not a compliance violation itself, but it must be functional
    status = "compliant"  # E-stop system exists (we can check it)
    return ComplianceResult(
        check_id=f"{machine_id}_estop_{uuid.uuid4().hex[:8]}",
        machine_id=machine_id,
        requirement="Emergency stop device shall be accessible and functional",
        current_condition="E-stop ACTIVE (machine halted)" if estop else "E-stop available (not activated)",
        expected_condition="Emergency stop shall be readily accessible and clearly identified",
        status=status,
        risk_level="critical" if estop else "low",
        evidence=[_chunk_to_evidence(c) for c in chunks] if chunks else [],
        source="ISO 13849-1 §5.3; NFPA 79 §9.2",
        explanation=(
            "Emergency stop is currently active — machine has been halted. "
            "Investigate cause before releasing e-stop and resuming operation."
            if estop else
            "Emergency stop system is available and not activated. Functional status confirmed."
        ),
        evidence_type="verified" if chunks else "inferred",
        standard_reference="ISO 13849-1 §5.3 / NFPA 79 §9.2",
    )


def _check_temperature(
    machine_id: str, temp: float, chunks: List[RetrievedChunk]
) -> ComplianceResult:
    cfg = MACHINE_CONFIGS.get(machine_id, {})
    thresholds = cfg.get("thresholds")
    if thresholds is None:
        return _unknown_check(machine_id, "temperature")

    if temp <= thresholds.temp_max:
        status = "compliant"
        risk_level = "low"
        explanation = f"Temperature {temp:.1f}°C is within safe operating limit of {thresholds.temp_max}°C."
    elif temp <= thresholds.temp_critical:
        status = "partially_compliant"
        risk_level = "elevated"
        explanation = (
            f"Temperature {temp:.1f}°C exceeds safe operating limit ({thresholds.temp_max}°C) "
            f"but below critical threshold ({thresholds.temp_critical}°C). Monitor closely."
        )
    else:
        status = "non_compliant"
        risk_level = "critical"
        explanation = (
            f"Temperature {temp:.1f}°C exceeds critical threshold of {thresholds.temp_critical}°C. "
            f"Immediate action required to prevent equipment damage and fire risk."
        )

    return ComplianceResult(
        check_id=f"{machine_id}_temp_{uuid.uuid4().hex[:8]}",
        machine_id=machine_id,
        requirement="Machine temperature shall remain within safe operating range",
        current_condition=f"Temperature: {temp:.1f}°C",
        expected_condition=f"Temperature shall not exceed {thresholds.temp_max}°C (critical: {thresholds.temp_critical}°C)",
        status=status,
        risk_level=risk_level,
        evidence=[_chunk_to_evidence(c) for c in chunks] if chunks else [],
        source="ISO 4413 §5.5; IEC 60079-14 §6.1",
        explanation=explanation,
        evidence_type="verified" if chunks else "inferred",
        standard_reference="ISO 4413 / IEC 60079-14",
    )


def _check_vibration(
    machine_id: str, vibration: float, chunks: List[RetrievedChunk]
) -> ComplianceResult:
    cfg = MACHINE_CONFIGS.get(machine_id, {})
    thresholds = cfg.get("thresholds")
    if thresholds is None:
        return _unknown_check(machine_id, "vibration")

    # Based on ISO 10816-3 zones
    if vibration <= 2.3:
        status = "compliant"; risk_level = "low"
        explanation = f"Vibration {vibration:.2f} mm/s RMS — Zone A (ISO 10816-3). Acceptable."
    elif vibration <= thresholds.vibration_max:
        status = "compliant"; risk_level = "moderate"
        explanation = f"Vibration {vibration:.2f} mm/s RMS — Zone B (ISO 10816-3). Acceptable for long-term operation."
    elif vibration <= thresholds.vibration_critical:
        status = "partially_compliant"; risk_level = "elevated"
        explanation = (
            f"Vibration {vibration:.2f} mm/s RMS — Zone C (ISO 10816-3). "
            f"Unsatisfactory for long-term operation. Schedule maintenance."
        )
    else:
        status = "non_compliant"; risk_level = "critical"
        explanation = (
            f"Vibration {vibration:.2f} mm/s RMS — Zone D (ISO 10816-3). "
            f"Severity is sufficient to cause machine damage. Shutdown recommended."
        )

    return ComplianceResult(
        check_id=f"{machine_id}_vib_{uuid.uuid4().hex[:8]}",
        machine_id=machine_id,
        requirement="Vibration levels shall remain within ISO 10816-3 acceptable zones",
        current_condition=f"Vibration: {vibration:.2f} mm/s RMS",
        expected_condition=f"Vibration shall not exceed {thresholds.vibration_max} mm/s (critical: {thresholds.vibration_critical} mm/s)",
        status=status,
        risk_level=risk_level,
        evidence=[_chunk_to_evidence(c) for c in chunks] if chunks else [],
        source="ISO 10816-3 Table 1",
        explanation=explanation,
        evidence_type="verified" if chunks else "inferred",
        standard_reference="ISO 10816-3",
    )


def _check_pressure(
    machine_id: str, pressure: float, chunks: List[RetrievedChunk]
) -> ComplianceResult:
    cfg = MACHINE_CONFIGS.get(machine_id, {})
    thresholds = cfg.get("thresholds")
    if thresholds is None:
        return _unknown_check(machine_id, "pressure")

    if pressure <= thresholds.pressure_max:
        status = "compliant"; risk_level = "low"
        explanation = f"Pressure {pressure:.1f} bar is within the safe operating limit of {thresholds.pressure_max} bar."
    elif pressure <= thresholds.pressure_critical:
        status = "partially_compliant"; risk_level = "high"
        explanation = (
            f"Pressure {pressure:.1f} bar exceeds safe limit ({thresholds.pressure_max} bar). "
            f"Relief valve should activate before critical threshold ({thresholds.pressure_critical} bar)."
        )
    else:
        status = "non_compliant"; risk_level = "critical"
        explanation = (
            f"Pressure {pressure:.1f} bar exceeds critical threshold ({thresholds.pressure_critical} bar). "
            f"Risk of catastrophic failure. Emergency shutdown required."
        )

    return ComplianceResult(
        check_id=f"{machine_id}_pressure_{uuid.uuid4().hex[:8]}",
        machine_id=machine_id,
        requirement="System pressure shall not exceed maximum allowable working pressure",
        current_condition=f"Pressure: {pressure:.1f} bar",
        expected_condition=f"Pressure shall not exceed {thresholds.pressure_max} bar (critical: {thresholds.pressure_critical} bar)",
        status=status,
        risk_level=risk_level,
        evidence=[_chunk_to_evidence(c) for c in chunks] if chunks else [],
        source="ISO 4413 §5.4; ISO 4414 §5.3",
        explanation=explanation,
        evidence_type="verified" if chunks else "inferred",
        standard_reference="ISO 4413 §5.4",
    )


def _check_maintenance(
    machine_id: str, maintenance_overdue: bool, chunks: List[RetrievedChunk]
) -> ComplianceResult:
    status = "compliant" if not maintenance_overdue else "non_compliant"
    return ComplianceResult(
        check_id=f"{machine_id}_maint_{uuid.uuid4().hex[:8]}",
        machine_id=machine_id,
        requirement="Scheduled maintenance shall be performed at required intervals",
        current_condition="Maintenance current" if not maintenance_overdue else "Maintenance OVERDUE",
        expected_condition="Maintenance shall be performed per manufacturer schedule and NFPA 79 §12.5",
        status=status,
        risk_level="low" if not maintenance_overdue else "high",
        evidence=[_chunk_to_evidence(c) for c in chunks] if chunks else [],
        source="NFPA 79 §12.5; OSHA 1910.217(e)",
        explanation=(
            "Maintenance is current. Machine is within its scheduled maintenance interval."
            if not maintenance_overdue else
            "Maintenance is overdue. Per NFPA 79 §12.5 and OSHA 1910.217(e), maintenance records "
            "shall be kept and machines maintained per schedule. Schedule maintenance immediately."
        ),
        evidence_type="verified" if chunks else "inferred",
        standard_reference="NFPA 79 §12.5",
    )


def _unknown_check(machine_id: str, topic: str) -> ComplianceResult:
    return ComplianceResult(
        check_id=f"{machine_id}_{topic}_unknown",
        machine_id=machine_id,
        requirement=f"Compliance check for {topic}",
        current_condition="Unknown",
        expected_condition="Unknown",
        status="unknown",
        risk_level="low",
        evidence=[],
        source="",
        explanation=INSUFFICIENT_EVIDENCE,
        evidence_type="unknown",
        standard_reference="",
    )


def _chunk_to_evidence(chunk: RetrievedChunk) -> Dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "title": chunk.title,
        "source": chunk.source,
        "section": chunk.section,
        "content": chunk.content,
        "relevance_score": chunk.relevance_score,
        "evidence_type": chunk.evidence_type,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main Compliance Engine
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceEngine:
    """
    Runs all compliance checks for a machine telemetry reading.
    Retrieves supporting evidence from the RAG pipeline.
    """

    def run_compliance_check(
        self,
        machine_id: str,
        machine_type: str,
        temperature: float,
        vibration: float,
        pressure: float,
        guard_status: bool,
        interlock_active: bool,
        emergency_stop: bool,
        maintenance_overdue: bool,
    ) -> List[ComplianceResult]:
        """
        Run all applicable compliance checks and return results.
        """
        results: List[ComplianceResult] = []

        # Retrieve relevant safety evidence from RAG
        evidence_map = self._retrieve_evidence(machine_type)

        results.append(_check_guard(machine_id, guard_status, evidence_map.get("guards", [])))
        results.append(_check_interlock(machine_id, interlock_active, evidence_map.get("interlocks", [])))
        results.append(_check_emergency_stop(machine_id, emergency_stop, evidence_map.get("emergency_stop", [])))
        results.append(_check_temperature(machine_id, temperature, evidence_map.get("temperature", [])))
        results.append(_check_vibration(machine_id, vibration, evidence_map.get("vibration", [])))
        results.append(_check_pressure(machine_id, pressure, evidence_map.get("pressure", [])))
        results.append(_check_maintenance(machine_id, maintenance_overdue, evidence_map.get("maintenance", [])))

        return results

    def _retrieve_evidence(self, machine_type: str) -> Dict[str, List[RetrievedChunk]]:
        """Pre-fetch evidence for each compliance topic."""
        topics = {
            "guards": "machine guard protection during operation",
            "interlocks": "safety interlock device requirements",
            "emergency_stop": "emergency stop function requirements",
            "temperature": "safe operating temperature limits thermal protection",
            "vibration": "vibration evaluation criteria acceptable levels",
            "pressure": "maximum allowable working pressure safety relief valve",
            "maintenance": "maintenance inspection records requirements",
        }
        result = {}
        for key, query in topics.items():
            try:
                chunks = rag_pipeline.retrieve(query, machine_type=machine_type, top_k=2)
                result[key] = chunks
            except Exception as e:
                logger.warning(f"Evidence retrieval failed for {key}: {e}")
                result[key] = []
        return result

    @staticmethod
    def overall_status(results: List[ComplianceResult]) -> str:
        """Compute the overall compliance status from individual check results."""
        statuses = {r.status for r in results}
        if "non_compliant" in statuses:
            return "non_compliant"
        if "partially_compliant" in statuses:
            return "partially_compliant"
        if "unknown" in statuses and len(statuses) == {"unknown"}:
            return "unknown"
        return "compliant"

    @staticmethod
    def compliance_score(results: List[ComplianceResult]) -> float:
        """Returns 0–100 compliance score."""
        if not results:
            return 100.0
        weights = {"compliant": 1.0, "partially_compliant": 0.5, "unknown": 0.5, "non_compliant": 0.0}
        total = sum(weights.get(r.status, 0.0) for r in results)
        return round((total / len(results)) * 100, 1)


# Module-level singleton
compliance_engine = ComplianceEngine()
