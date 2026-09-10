"""
SAFEGUARD AI - Risk Engine
Deterministic, transparent risk scoring from 0-100.
Every score is fully explained by the contributing factors.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

from backend.simulation.simulator import MachineThresholds, MACHINE_CONFIGS

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Risk Score Boundaries
# ─────────────────────────────────────────────────────────────────────────────

RISK_BANDS = [
    (0, 20,  "low",      "LOW"),
    (21, 40, "moderate", "MODERATE"),
    (41, 60, "elevated", "ELEVATED"),
    (61, 80, "high",     "HIGH"),
    (81, 100, "critical","CRITICAL"),
]


def score_to_level(score: float) -> str:
    score = max(0.0, min(100.0, score))
    for lo, hi, level, _ in RISK_BANDS:
        if lo <= score <= hi:
            return level
    return "critical"


@dataclass
class RiskFactor:
    """A single contributing factor to the overall risk score."""
    name: str              # Human-readable name
    category: str          # temperature, vibration, rpm, pressure, load, guard, maintenance, etc.
    value: Any             # Actual measured/detected value
    threshold: Any         # Configured safe threshold
    contribution: float    # Points added to risk score (0–100 total)
    explanation: str       # Why this contributes


@dataclass
class RiskAssessment:
    """Complete risk assessment output for one machine reading."""
    machine_id: str
    timestamp: datetime
    risk_score: float           # 0–100
    risk_level: str             # low / moderate / elevated / high / critical
    risk_factors: List[RiskFactor]
    total_contribution: float
    explanation: str
    is_anomaly: bool = False
    anomaly_score: float = 0.0
    trend: str = "stable"       # increasing / decreasing / stable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine_id": self.machine_id,
            "timestamp": self.timestamp.isoformat(),
            "risk_score": round(self.risk_score, 1),
            "risk_level": self.risk_level,
            "risk_factors": [
                {
                    "name": rf.name,
                    "category": rf.category,
                    "value": rf.value,
                    "threshold": rf.threshold,
                    "contribution": round(rf.contribution, 1),
                    "explanation": rf.explanation,
                }
                for rf in self.risk_factors
            ],
            "explanation": self.explanation,
            "is_anomaly": self.is_anomaly,
            "anomaly_score": round(self.anomaly_score, 3),
            "trend": self.trend,
        }


class RiskEngine:
    """
    Calculates a transparent, deterministic risk score from machine telemetry.

    Risk score composition (max 100 points):
      Temperature anomaly     : 0–20 pts
      Vibration anomaly       : 0–20 pts
      Pressure anomaly        : 0–15 pts
      RPM anomaly             : 0–10 pts
      Load anomaly            : 0–10 pts
      Guard / interlock issue : 0–15 pts (guard=10, interlock=5)
      Emergency stop active   : 0–20 pts  (overrides other factors when active)
      Maintenance overdue     : 0–10 pts
      Door unlock             : 0–5  pts
    Total possible: can exceed 100; capped at 100.
    """

    # Maximum contribution per factor
    FACTOR_WEIGHTS = {
        "temperature":   20.0,
        "vibration":     20.0,
        "pressure":      15.0,
        "rpm":           10.0,
        "load":          10.0,
        "guard":         10.0,
        "interlock":      5.0,
        "emergency_stop": 20.0,
        "maintenance":   10.0,
        "door":           5.0,
    }

    def assess(
        self,
        machine_id: str,
        temperature: float,
        vibration: float,
        rpm: float,
        pressure: float,
        load: float,
        guard_status: bool,
        interlock_active: bool,
        emergency_stop: bool,
        door_locked: bool,
        maintenance_overdue: bool = False,
        timestamp: Optional[datetime] = None,
    ) -> RiskAssessment:
        """Compute the full risk assessment for one set of telemetry values."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        if machine_id not in MACHINE_CONFIGS:
            raise ValueError(f"Unknown machine_id: {machine_id}")

        thresholds: MachineThresholds = MACHINE_CONFIGS[machine_id]["thresholds"]
        factors: List[RiskFactor] = []

        # ── 1. Temperature ──────────────────────────────────────────────────
        temp_contribution = self._score_range(
            value=temperature,
            safe_max=thresholds.temp_max,
            critical=thresholds.temp_critical,
            max_weight=self.FACTOR_WEIGHTS["temperature"],
        )
        if temp_contribution > 0:
            factors.append(RiskFactor(
                name="High Temperature",
                category="temperature",
                value=temperature,
                threshold=thresholds.temp_max,
                contribution=temp_contribution,
                explanation=(
                    f"Temperature {temperature:.1f}°C exceeds safe limit of "
                    f"{thresholds.temp_max}°C. "
                    f"{'CRITICAL: approaching {:.0f}°C limit.'.format(thresholds.temp_critical) if temperature >= thresholds.temp_max * 0.9 else ''}"
                ),
            ))

        # ── 2. Vibration ────────────────────────────────────────────────────
        vib_contribution = self._score_range(
            value=vibration,
            safe_max=thresholds.vibration_max,
            critical=thresholds.vibration_critical,
            max_weight=self.FACTOR_WEIGHTS["vibration"],
        )
        if vib_contribution > 0:
            factors.append(RiskFactor(
                name="High Vibration",
                category="vibration",
                value=vibration,
                threshold=thresholds.vibration_max,
                contribution=vib_contribution,
                explanation=(
                    f"Vibration {vibration:.2f} mm/s RMS exceeds safe limit of "
                    f"{thresholds.vibration_max} mm/s. May indicate bearing wear or imbalance."
                ),
            ))

        # ── 3. Pressure ─────────────────────────────────────────────────────
        pres_contribution = self._score_range(
            value=pressure,
            safe_max=thresholds.pressure_max,
            critical=thresholds.pressure_critical,
            max_weight=self.FACTOR_WEIGHTS["pressure"],
        )
        if pres_contribution > 0:
            factors.append(RiskFactor(
                name="High Pressure",
                category="pressure",
                value=pressure,
                threshold=thresholds.pressure_max,
                contribution=pres_contribution,
                explanation=(
                    f"Pressure {pressure:.1f} bar exceeds safe max of "
                    f"{thresholds.pressure_max} bar. Risk of seal failure or burst."
                ),
            ))

        # ── 4. RPM ──────────────────────────────────────────────────────────
        rpm_contribution = self._score_range(
            value=rpm,
            safe_max=thresholds.rpm_max,
            critical=thresholds.rpm_critical,
            max_weight=self.FACTOR_WEIGHTS["rpm"],
        )
        if rpm_contribution > 0:
            factors.append(RiskFactor(
                name="Overspeed (RPM)",
                category="rpm",
                value=rpm,
                threshold=thresholds.rpm_max,
                contribution=rpm_contribution,
                explanation=(
                    f"RPM {rpm:.0f} exceeds rated maximum of {thresholds.rpm_max:.0f}. "
                    f"Risk of mechanical failure."
                ),
            ))

        # ── 5. Load ─────────────────────────────────────────────────────────
        load_contribution = self._score_range(
            value=load,
            safe_max=thresholds.load_max,
            critical=thresholds.load_critical,
            max_weight=self.FACTOR_WEIGHTS["load"],
        )
        if load_contribution > 0:
            factors.append(RiskFactor(
                name="Overload",
                category="load",
                value=load,
                threshold=thresholds.load_max,
                contribution=load_contribution,
                explanation=(
                    f"Load {load:.1f}% exceeds safe maximum of {thresholds.load_max}%. "
                    f"Accelerates wear and risks motor damage."
                ),
            ))

        # ── 6. Guard Status ─────────────────────────────────────────────────
        if not guard_status:
            factors.append(RiskFactor(
                name="Guard Removed / Open",
                category="guard",
                value=False,
                threshold=True,
                contribution=self.FACTOR_WEIGHTS["guard"],
                explanation="Machine guard is open or removed. Operator exposure to moving parts.",
            ))

        # ── 7. Interlock ────────────────────────────────────────────────────
        if not interlock_active:
            factors.append(RiskFactor(
                name="Interlock Not Active",
                category="interlock",
                value=False,
                threshold=True,
                contribution=self.FACTOR_WEIGHTS["interlock"],
                explanation="Safety interlock is not engaged. Control circuit may not stop on fault.",
            ))

        # ── 8. Emergency Stop ────────────────────────────────────────────────
        if emergency_stop:
            factors.append(RiskFactor(
                name="Emergency Stop Active",
                category="emergency_stop",
                value=True,
                threshold=False,
                contribution=self.FACTOR_WEIGHTS["emergency_stop"],
                explanation="E-stop is active. Machine has been manually halted due to an emergency.",
            ))

        # ── 9. Maintenance Overdue ───────────────────────────────────────────
        if maintenance_overdue:
            factors.append(RiskFactor(
                name="Maintenance Overdue",
                category="maintenance",
                value=True,
                threshold=False,
                contribution=self.FACTOR_WEIGHTS["maintenance"],
                explanation="Scheduled maintenance is overdue. Increased probability of failure.",
            ))

        # ── 10. Door Lock ────────────────────────────────────────────────────
        if not door_locked:
            factors.append(RiskFactor(
                name="Access Door Unlocked",
                category="door",
                value=False,
                threshold=True,
                contribution=self.FACTOR_WEIGHTS["door"],
                explanation="Access door is unlocked while machine is operational.",
            ))

        # ── Aggregate ────────────────────────────────────────────────────────
        total = sum(f.contribution for f in factors)
        risk_score = min(100.0, total)
        risk_level = score_to_level(risk_score)

        explanation = self._build_explanation(machine_id, risk_score, risk_level, factors)

        return RiskAssessment(
            machine_id=machine_id,
            timestamp=timestamp,
            risk_score=round(risk_score, 1),
            risk_level=risk_level,
            risk_factors=factors,
            total_contribution=round(total, 1),
            explanation=explanation,
        )

    @staticmethod
    def _score_range(value: float, safe_max: float, critical: float, max_weight: float) -> float:
        """
        Returns a score contribution between 0 and max_weight.
        - 0          if value <= safe_max
        - proportional between safe_max and critical
        - max_weight if value >= critical
        """
        if value <= safe_max:
            return 0.0
        if value >= critical:
            return max_weight
        # Linear interpolation between safe_max and critical
        ratio = (value - safe_max) / (critical - safe_max)
        return round(ratio * max_weight, 2)

    @staticmethod
    def _build_explanation(machine_id: str, score: float, level: str, factors: List[RiskFactor]) -> str:
        if not factors:
            return f"Machine {machine_id} is operating within all safe parameters. Risk score: {score:.1f}/100."

        lines = [f"Machine {machine_id} risk score: {score:.1f}/100 ({level.upper()})"]
        lines.append("")
        lines.append("Contributing factors:")
        for f in sorted(factors, key=lambda x: x.contribution, reverse=True):
            lines.append(f"  • {f.name}: +{f.contribution:.1f} pts — {f.explanation}")
        return "\n".join(lines)

    def assess_whatif(
        self,
        machine_id: str,
        overrides: Dict[str, Any],
    ) -> RiskAssessment:
        """
        What-If assessment: apply user-specified overrides to a machine's
        default baseline and return the resulting risk assessment.
        """
        if machine_id not in MACHINE_CONFIGS:
            raise ValueError(f"Unknown machine_id: {machine_id}")

        base = dict(MACHINE_CONFIGS[machine_id]["base"])

        return self.assess(
            machine_id=machine_id,
            temperature=overrides.get("temperature", base["temperature"]),
            vibration=overrides.get("vibration", base["vibration"]),
            rpm=overrides.get("rpm", base["rpm"]),
            pressure=overrides.get("pressure", base["pressure"]),
            load=overrides.get("load", base["load"]),
            guard_status=overrides.get("guard_status", True),
            interlock_active=overrides.get("interlock_active", True),
            emergency_stop=overrides.get("emergency_stop", False),
            door_locked=overrides.get("door_locked", True),
            maintenance_overdue=overrides.get("maintenance_overdue", False),
        )


# Module-level singleton
risk_engine = RiskEngine()
