"""
SAFEGUARD AI - Multi-Agent System
Four specialized agents working together to deliver safety intelligence.

Agents:
1. SafetyDataAgent    - Retrieves safety standards via RAG
2. RiskDetectionAgent - Analyzes telemetry and scores risk
3. ComplianceAgent    - Verifies conditions against standards
4. RecommendationAgent- Generates prioritized corrective actions

Orchestration: rule-based pipeline with optional IBM Orchestrate/Langflow.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from backend.risk_engine.engine import risk_engine, RiskAssessment
from backend.risk_engine.anomaly_detection import anomaly_manager
from backend.risk_engine.trend_analysis import trend_analyzer
from backend.compliance.engine import compliance_engine, ComplianceResult
from backend.recommendations.engine import recommendation_engine, SafetyRecommendation
from backend.rag.pipeline import rag_pipeline, RetrievedChunk
from backend.services.watsonx import watsonx_client
from backend.services.langflow import langflow_client
from backend.simulation.simulator import MACHINE_CONFIGS

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    agent_name: str
    status: str          # success / warning / error
    output: Any
    duration_ms: float
    used_ibm_service: bool = False
    fallback_used: bool = False


@dataclass
class SafetyAnalysisResult:
    """Complete output from the multi-agent safety analysis pipeline."""
    session_id: str
    machine_id: str
    machine_name: str
    machine_type: str
    timestamp: datetime
    telemetry: Dict[str, Any]

    # Agent outputs
    retrieved_evidence: List[Dict[str, Any]]
    risk_assessment: Dict[str, Any]
    compliance_results: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]

    # Aggregate scores
    risk_score: float
    risk_level: str
    compliance_score: float
    overall_compliance_status: str

    # Trend and anomaly
    anomaly_detected: bool
    anomaly_score: float
    trends: Dict[str, Any]

    # Explanations and narratives
    risk_explanation: str
    risk_summary: str      # from IBM WatsonX if available
    agent_trace: List[Dict[str, Any]]  # audit trail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "machine_id": self.machine_id,
            "machine_name": self.machine_name,
            "machine_type": self.machine_type,
            "timestamp": self.timestamp.isoformat(),
            "telemetry": self.telemetry,
            "retrieved_evidence": self.retrieved_evidence,
            "risk_assessment": self.risk_assessment,
            "compliance_results": self.compliance_results,
            "recommendations": self.recommendations,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "compliance_score": self.compliance_score,
            "overall_compliance_status": self.overall_compliance_status,
            "anomaly_detected": self.anomaly_detected,
            "anomaly_score": self.anomaly_score,
            "trends": self.trends,
            "risk_explanation": self.risk_explanation,
            "risk_summary": self.risk_summary,
            "agent_trace": self.agent_trace,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Individual Agents
# ─────────────────────────────────────────────────────────────────────────────

class SafetyDataAgent:
    """
    Retrieves relevant safety standards, machine information, and supporting
    evidence from the RAG pipeline for a given machine and condition set.
    Uses IBM Langflow RAG flow when configured.
    """
    name = "SafetyDataAgent"

    def run(self, machine_id: str, machine_type: str, risk_categories: List[str]) -> AgentResult:
        import time
        start = time.time()

        try:
            # Try Langflow RAG flow first
            langflow_result = None
            if langflow_client.available and risk_categories:
                query = f"safety requirements for {machine_type}: {', '.join(risk_categories)}"
                langflow_result = langflow_client.query_rag_flow(query, machine_type)

            # Always use local RAG for structured evidence
            evidence_chunks: List[RetrievedChunk] = []
            queries = []
            if "temperature" in risk_categories:
                queries.append("temperature operating limits thermal protection")
            if "vibration" in risk_categories:
                queries.append("vibration evaluation criteria ISO 10816 bearing")
            if "guard" in risk_categories:
                queries.append("machine guard protection operator safety OSHA")
            if "pressure" in risk_categories:
                queries.append("hydraulic pressure relief valve maximum allowable")
            if "maintenance" in risk_categories:
                queries.append("maintenance requirements inspection records NFPA")
            if not queries:
                queries.append(f"safety requirements {machine_type} general")

            seen_ids = set()
            for q in queries:
                chunks = rag_pipeline.retrieve(q, machine_type=machine_type, top_k=3)
                for c in chunks:
                    if c.chunk_id not in seen_ids:
                        seen_ids.add(c.chunk_id)
                        evidence_chunks.append(c)

            evidence_dicts = [
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "title": c.title,
                    "source": c.source,
                    "section": c.section,
                    "topic": c.topic,
                    "content": c.content,
                    "relevance_score": c.relevance_score,
                    "evidence_type": c.evidence_type,
                    "langflow_enhanced": langflow_result is not None,
                }
                for c in evidence_chunks
            ]

            duration = (time.time() - start) * 1000
            return AgentResult(
                agent_name=self.name,
                status="success",
                output=evidence_dicts,
                duration_ms=round(duration, 1),
                used_ibm_service=langflow_result is not None,
                fallback_used=langflow_result is None,
            )

        except Exception as e:
            logger.error(f"SafetyDataAgent error: {e}")
            duration = (time.time() - start) * 1000
            return AgentResult(
                agent_name=self.name,
                status="error",
                output=[],
                duration_ms=round(duration, 1),
            )


class RiskDetectionAgent:
    """
    Analyzes machine telemetry and identifies unsafe or abnormal operating conditions.
    Uses the deterministic risk engine, anomaly detection, and trend analysis.
    """
    name = "RiskDetectionAgent"

    def run(
        self,
        machine_id: str,
        telemetry: Dict[str, Any],
        maintenance_overdue: bool = False,
    ) -> AgentResult:
        import time
        start = time.time()

        try:
            # Risk scoring
            risk = risk_engine.assess(
                machine_id=machine_id,
                temperature=telemetry.get("temperature", 0),
                vibration=telemetry.get("vibration", 0),
                rpm=telemetry.get("rpm", 0),
                pressure=telemetry.get("pressure", 0),
                load=telemetry.get("load", 0),
                guard_status=telemetry.get("guard_status", True),
                interlock_active=telemetry.get("interlock_active", True),
                emergency_stop=telemetry.get("emergency_stop", False),
                door_locked=telemetry.get("door_locked", True),
                maintenance_overdue=maintenance_overdue,
            )

            # Anomaly detection
            anomaly = anomaly_manager.update(machine_id, {
                "temperature": telemetry.get("temperature", 0),
                "vibration": telemetry.get("vibration", 0),
                "rpm": telemetry.get("rpm", 0),
                "pressure": telemetry.get("pressure", 0),
                "load": telemetry.get("load", 0),
                "current": telemetry.get("current", 0),
            })

            # Enrich risk assessment with anomaly data
            risk.is_anomaly = anomaly.is_anomaly
            risk.anomaly_score = anomaly.anomaly_score

            # Trend analysis
            trends = trend_analyzer.update(machine_id, {
                "temperature": telemetry.get("temperature", 0),
                "vibration": telemetry.get("vibration", 0),
                "rpm": telemetry.get("rpm", 0),
                "pressure": telemetry.get("pressure", 0),
                "load": telemetry.get("load", 0),
            })

            # Determine trend
            rising_params = [p for p, t in trends.items() if t.trend == "increasing"]
            if rising_params and risk.risk_score > 30:
                risk.trend = "increasing"
            elif all(t.trend == "decreasing" for t in trends.values() if t.trend != "stable"):
                risk.trend = "decreasing"
            else:
                risk.trend = "stable"

            trends_dict = {
                p: {
                    "trend": t.trend,
                    "slope": t.slope,
                    "confidence": t.confidence,
                    "current_value": t.current_value,
                    "predicted_1h": t.predicted_1h,
                    "predicted_4h": t.predicted_4h,
                    "explanation": t.explanation,
                    "is_prediction": True,
                }
                for p, t in trends.items()
            }

            duration = (time.time() - start) * 1000
            return AgentResult(
                agent_name=self.name,
                status="success",
                output={"risk": risk, "anomaly": anomaly, "trends": trends_dict},
                duration_ms=round(duration, 1),
            )

        except Exception as e:
            logger.error(f"RiskDetectionAgent error: {e}")
            import time
            duration = (time.time() - start) * 1000
            return AgentResult(
                agent_name=self.name,
                status="error",
                output=None,
                duration_ms=round(duration, 1),
            )


class ComplianceAgentWorker:
    """
    Compares machine conditions against retrieved safety requirements
    and determines compliance status with full evidence.
    """
    name = "ComplianceAgent"

    def run(
        self,
        machine_id: str,
        machine_type: str,
        telemetry: Dict[str, Any],
        maintenance_overdue: bool = False,
    ) -> AgentResult:
        import time
        start = time.time()

        try:
            results = compliance_engine.run_compliance_check(
                machine_id=machine_id,
                machine_type=machine_type,
                temperature=telemetry.get("temperature", 0),
                vibration=telemetry.get("vibration", 0),
                pressure=telemetry.get("pressure", 0),
                guard_status=telemetry.get("guard_status", True),
                interlock_active=telemetry.get("interlock_active", True),
                emergency_stop=telemetry.get("emergency_stop", False),
                maintenance_overdue=maintenance_overdue,
            )

            duration = (time.time() - start) * 1000
            return AgentResult(
                agent_name=self.name,
                status="success",
                output=results,
                duration_ms=round(duration, 1),
            )

        except Exception as e:
            logger.error(f"ComplianceAgent error: {e}")
            import time
            duration = (time.time() - start) * 1000
            return AgentResult(
                agent_name=self.name,
                status="error",
                output=[],
                duration_ms=round(duration, 1),
            )


class RecommendationAgentWorker:
    """
    Generates prioritized corrective and preventive actions based on
    detected risks and compliance violations.
    """
    name = "RecommendationAgent"

    def run(
        self,
        risk_assessment: RiskAssessment,
        compliance_results: List[ComplianceResult],
        machine_type: str,
    ) -> AgentResult:
        import time
        start = time.time()

        try:
            recs = recommendation_engine.generate(risk_assessment, compliance_results, machine_type)
            duration = (time.time() - start) * 1000
            return AgentResult(
                agent_name=self.name,
                status="success",
                output=recs,
                duration_ms=round(duration, 1),
            )

        except Exception as e:
            logger.error(f"RecommendationAgent error: {e}")
            import time
            duration = (time.time() - start) * 1000
            return AgentResult(
                agent_name=self.name,
                status="error",
                output=[],
                duration_ms=round(duration, 1),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class SafetyOrchestrator:
    """
    Orchestrates the four safety agents in sequence.
    Compatible with IBM Watson Orchestrate for enterprise deployments.

    Flow:
    1. RiskDetectionAgent  → determine risk categories
    2. SafetyDataAgent     → retrieve relevant evidence (RAG)
    3. ComplianceAgent     → verify compliance against evidence
    4. RecommendationAgent → generate recommendations
    5. WatsonX             → enhance narrative summaries
    """

    def __init__(self):
        self._data_agent = SafetyDataAgent()
        self._risk_agent = RiskDetectionAgent()
        self._compliance_agent = ComplianceAgentWorker()
        self._rec_agent = RecommendationAgentWorker()

    def analyze(
        self,
        machine_id: str,
        telemetry: Dict[str, Any],
        maintenance_overdue: bool = False,
    ) -> SafetyAnalysisResult:
        """Run the full multi-agent safety analysis for one machine reading."""
        session_id = uuid.uuid4().hex[:12]
        start_ts = datetime.now(timezone.utc)
        agent_trace = []

        if machine_id not in MACHINE_CONFIGS:
            raise ValueError(f"Unknown machine_id: {machine_id}")

        machine_cfg = MACHINE_CONFIGS[machine_id]
        machine_name = machine_cfg["name"]
        machine_type = machine_cfg["machine_type"]

        # ── Step 1: Risk Detection ──────────────────────────────────────────
        risk_result = self._risk_agent.run(machine_id, telemetry, maintenance_overdue)
        agent_trace.append({
            "agent": risk_result.agent_name,
            "status": risk_result.status,
            "duration_ms": risk_result.duration_ms,
        })

        if risk_result.status != "success" or risk_result.output is None:
            logger.error(f"RiskDetectionAgent failed for {machine_id}")
            risk_assessment = None
            trends_dict = {}
            anomaly_detected = False
            anomaly_score = 0.0
        else:
            risk_assessment: RiskAssessment = risk_result.output["risk"]
            trends_dict = risk_result.output["trends"]
            anomaly = risk_result.output["anomaly"]
            anomaly_detected = anomaly.is_anomaly
            anomaly_score = anomaly.anomaly_score

        risk_categories = (
            [f.category for f in risk_assessment.risk_factors]
            if risk_assessment else []
        )

        # ── Step 2: Safety Data Retrieval (RAG) ────────────────────────────
        data_result = self._data_agent.run(machine_id, machine_type, risk_categories)
        agent_trace.append({
            "agent": data_result.agent_name,
            "status": data_result.status,
            "duration_ms": data_result.duration_ms,
            "chunks_retrieved": len(data_result.output) if data_result.output else 0,
            "used_langflow": data_result.used_ibm_service,
        })
        evidence = data_result.output or []

        # ── Step 3: Compliance Check ────────────────────────────────────────
        compliance_result = self._compliance_agent.run(
            machine_id, machine_type, telemetry, maintenance_overdue
        )
        agent_trace.append({
            "agent": compliance_result.agent_name,
            "status": compliance_result.status,
            "duration_ms": compliance_result.duration_ms,
        })
        compliance_checks: List[ComplianceResult] = compliance_result.output or []

        # ── Step 4: Recommendations ─────────────────────────────────────────
        rec_result = self._rec_agent.run(risk_assessment, compliance_checks, machine_type)
        agent_trace.append({
            "agent": rec_result.agent_name,
            "status": rec_result.status,
            "duration_ms": rec_result.duration_ms,
        })
        recommendations: List[SafetyRecommendation] = rec_result.output or []

        # ── Step 5: IBM WatsonX narrative summary ───────────────────────────
        risk_summary = ""
        if risk_assessment:
            risk_summary = watsonx_client.summarize_risk(
                machine_name, risk_assessment.to_dict()
            )
            agent_trace.append({
                "agent": "WatsonXSummaryService",
                "status": "success",
                "used_ibm_watsonx": watsonx_client.available,
                "fallback_used": not watsonx_client.available,
            })

        # ── Aggregate scores ────────────────────────────────────────────────
        overall_compliance = compliance_engine.overall_status(compliance_checks)
        comp_score = compliance_engine.compliance_score(compliance_checks)

        return SafetyAnalysisResult(
            session_id=session_id,
            machine_id=machine_id,
            machine_name=machine_name,
            machine_type=machine_type,
            timestamp=start_ts,
            telemetry=telemetry,
            retrieved_evidence=evidence,
            risk_assessment=risk_assessment.to_dict() if risk_assessment else {},
            compliance_results=[
                {
                    "check_id": c.check_id,
                    "requirement": c.requirement,
                    "current_condition": c.current_condition,
                    "expected_condition": c.expected_condition,
                    "status": c.status,
                    "risk_level": c.risk_level,
                    "evidence": c.evidence,
                    "source": c.source,
                    "explanation": c.explanation,
                    "evidence_type": c.evidence_type,
                    "standard_reference": c.standard_reference,
                }
                for c in compliance_checks
            ],
            recommendations=[r.to_dict() for r in recommendations],
            risk_score=risk_assessment.risk_score if risk_assessment else 0.0,
            risk_level=risk_assessment.risk_level if risk_assessment else "unknown",
            compliance_score=comp_score,
            overall_compliance_status=overall_compliance,
            anomaly_detected=anomaly_detected,
            anomaly_score=anomaly_score,
            trends=trends_dict,
            risk_explanation=risk_assessment.explanation if risk_assessment else "",
            risk_summary=risk_summary,
            agent_trace=agent_trace,
        )

    def whatif_analysis(
        self,
        machine_id: str,
        overrides: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        What-If analysis: apply user parameter overrides and run risk + compliance.
        Uses the same real engine — no LLM-generated scores.
        """
        if machine_id not in MACHINE_CONFIGS:
            raise ValueError(f"Unknown machine_id: {machine_id}")

        machine_cfg = MACHINE_CONFIGS[machine_id]
        machine_type = machine_cfg["machine_type"]
        base = dict(machine_cfg["base"])

        # Merge overrides with base values
        telemetry = {
            "temperature": overrides.get("temperature", base["temperature"]),
            "vibration": overrides.get("vibration", base["vibration"]),
            "rpm": overrides.get("rpm", base["rpm"]),
            "pressure": overrides.get("pressure", base["pressure"]),
            "load": overrides.get("load", base["load"]),
            "guard_status": overrides.get("guard_status", True),
            "interlock_active": overrides.get("interlock_active", True),
            "emergency_stop": overrides.get("emergency_stop", False),
            "door_locked": overrides.get("door_locked", True),
        }

        risk = risk_engine.assess(
            machine_id=machine_id,
            temperature=telemetry["temperature"],
            vibration=telemetry["vibration"],
            rpm=telemetry["rpm"],
            pressure=telemetry["pressure"],
            load=telemetry["load"],
            guard_status=telemetry["guard_status"],
            interlock_active=telemetry["interlock_active"],
            emergency_stop=telemetry["emergency_stop"],
            door_locked=telemetry["door_locked"],
            maintenance_overdue=overrides.get("maintenance_overdue", False),
        )

        compliance_checks = compliance_engine.run_compliance_check(
            machine_id=machine_id,
            machine_type=machine_type,
            temperature=telemetry["temperature"],
            vibration=telemetry["vibration"],
            pressure=telemetry["pressure"],
            guard_status=telemetry["guard_status"],
            interlock_active=telemetry["interlock_active"],
            emergency_stop=telemetry["emergency_stop"],
            maintenance_overdue=overrides.get("maintenance_overdue", False),
        )

        affected_requirements = [
            {
                "requirement": c.requirement,
                "status": c.status,
                "explanation": c.explanation,
                "source": c.source,
            }
            for c in compliance_checks
            if c.status != "compliant"
        ]

        return {
            "machine_id": machine_id,
            "applied_overrides": overrides,
            "telemetry_used": telemetry,
            "risk_score": risk.risk_score,
            "risk_level": risk.risk_level,
            "risk_factors": [
                {
                    "name": f.name,
                    "category": f.category,
                    "value": f.value,
                    "threshold": f.threshold,
                    "contribution": f.contribution,
                    "explanation": f.explanation,
                }
                for f in risk.risk_factors
            ],
            "explanation": risk.explanation,
            "compliance_score": compliance_engine.compliance_score(compliance_checks),
            "overall_compliance_status": compliance_engine.overall_status(compliance_checks),
            "affected_requirements": affected_requirements,
            "what_changed": (
                f"Simulating {machine_cfg['name']} with modified parameters: "
                + ", ".join(f"{k}={v}" for k, v in overrides.items())
            ),
        }


# Module-level singleton
safety_orchestrator = SafetyOrchestrator()
