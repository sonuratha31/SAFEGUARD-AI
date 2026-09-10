"""
risk_calculator.py
Deterministic, transparent risk scoring engine (0-100 scale).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RiskFactor:
    name: str
    score_contribution: float
    description: str
    threshold_value: float
    actual_value: float
    unit: str


@dataclass
class RiskCalculationResult:
    machine_id: str
    machine_type: str
    total_score: float          # clamped 0-100
    risk_level: str             # LOW / MODERATE / ELEVATED / HIGH / CRITICAL
    contributing_factors: List[RiskFactor]
    explanation: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Per-machine-type thresholds
# ---------------------------------------------------------------------------

# Each entry: (temp_max, vibration_max, rpm_min, rpm_max, pressure_max, load_warn, load_critical)
_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "CNC_MACHINE": {
        "temp_max": 75.0, "vibration_max": 4.0,
        "rpm_min": 500.0, "rpm_max": 3000.0,
        "pressure_max": 8.0,
        "load_warn": 85.0, "load_critical": 95.0,
    },
    "HYDRAULIC_PRESS": {
        "temp_max": 65.0, "vibration_max": 3.0,
        "rpm_min": 100.0, "rpm_max": 800.0,
        "pressure_max": 250.0,
        "load_warn": 85.0, "load_critical": 95.0,
    },
    "INDUSTRIAL_MOTOR": {
        "temp_max": 85.0, "vibration_max": 6.0,
        "rpm_min": 1000.0, "rpm_max": 3600.0,
        "pressure_max": 5.0,
        "load_warn": 85.0, "load_critical": 95.0,
    },
    "COMPRESSOR": {
        "temp_max": 90.0, "vibration_max": 5.0,
        "rpm_min": 800.0, "rpm_max": 2400.0,
        "pressure_max": 12.0,
        "load_warn": 85.0, "load_critical": 95.0,
    },
    "CONVEYOR_SYSTEM": {
        "temp_max": 55.0, "vibration_max": 2.5,
        "rpm_min": 50.0, "rpm_max": 300.0,
        "pressure_max": 3.0,
        "load_warn": 85.0, "load_critical": 95.0,
    },
}

# Fallback for unknown machine types
_DEFAULT_THRESHOLDS: Dict[str, float] = {
    "temp_max": 80.0, "vibration_max": 5.0,
    "rpm_min": 100.0, "rpm_max": 3000.0,
    "pressure_max": 15.0,
    "load_warn": 85.0, "load_critical": 95.0,
}


# ---------------------------------------------------------------------------
# Risk calculator
# ---------------------------------------------------------------------------

class RiskCalculator:
    """
    Deterministic risk scoring engine.

    Scores are additive across independent factors and then clamped to [0, 100].
    Each factor has a documented maximum contribution so the model remains
    fully interpretable.
    """

    def calculate_risk(
        self,
        machine_id: str,
        machine_type: str,
        reading: Dict[str, Any],
    ) -> RiskCalculationResult:
        thresholds = _THRESHOLDS.get(machine_type, _DEFAULT_THRESHOLDS)
        factors: List[RiskFactor] = []

        # --- Temperature ---
        temp = float(reading.get("temperature", 0))
        t_max = thresholds["temp_max"]
        temp_score, temp_desc = self._graduated_score(
            value=temp,
            max_normal=t_max,
            contributions=[
                (0.10, 10.0, "10 % over max temperature"),
                (0.20, 20.0, "20 % over max temperature"),
                (0.30, 35.0, "30 %+ over max temperature (max +35)"),
            ],
            cap=35.0,
        )
        factors.append(RiskFactor(
            name="Temperature",
            score_contribution=temp_score,
            description=temp_desc if temp_score > 0 else "Temperature within normal range",
            threshold_value=t_max,
            actual_value=temp,
            unit="°C",
        ))

        # --- Vibration ---
        vib = float(reading.get("vibration", 0))
        v_max = thresholds["vibration_max"]
        vib_score, vib_desc = self._graduated_score(
            value=vib,
            max_normal=v_max,
            contributions=[
                (0.10, 10.0, "10 % over max vibration"),
                (0.20, 20.0, "20 % over max vibration"),
                (0.30, 30.0, "30 %+ over max vibration (max +30)"),
            ],
            cap=30.0,
        )
        factors.append(RiskFactor(
            name="Vibration",
            score_contribution=vib_score,
            description=vib_desc if vib_score > 0 else "Vibration within normal range",
            threshold_value=v_max,
            actual_value=vib,
            unit="mm/s",
        ))

        # --- RPM ---
        rpm = float(reading.get("rpm", 0))
        rpm_min = thresholds["rpm_min"]
        rpm_max = thresholds["rpm_max"]
        rpm_score, rpm_desc = self._rpm_score(rpm, rpm_min, rpm_max)
        factors.append(RiskFactor(
            name="RPM",
            score_contribution=rpm_score,
            description=rpm_desc if rpm_score > 0 else "RPM within normal range",
            threshold_value=rpm_max,
            actual_value=rpm,
            unit="rpm",
        ))

        # --- Pressure ---
        pressure = float(reading.get("pressure", 0))
        p_max = thresholds["pressure_max"]
        pres_score, pres_desc = self._graduated_score(
            value=pressure,
            max_normal=p_max,
            contributions=[
                (0.10, 10.0, "10 % over max pressure"),
                (0.20, 20.0, "20 % over max pressure"),
                (0.30, 30.0, "30 %+ over max pressure (max +30)"),
            ],
            cap=30.0,
        )
        factors.append(RiskFactor(
            name="Pressure",
            score_contribution=pres_score,
            description=pres_desc if pres_score > 0 else "Pressure within normal range",
            threshold_value=p_max,
            actual_value=pressure,
            unit="bar",
        ))

        # --- Load ---
        load = float(reading.get("load", 0))
        load_warn = thresholds["load_warn"]
        load_crit = thresholds["load_critical"]
        load_score = 0.0
        load_desc = "Load within acceptable range"
        if load > load_crit:
            load_score = 15.0
            load_desc = f"Load critically high ({load:.1f}% > {load_crit}%)"
        elif load > load_warn:
            load_score = 5.0
            load_desc = f"Load elevated ({load:.1f}% > {load_warn}%)"
        factors.append(RiskFactor(
            name="Load",
            score_contribution=load_score,
            description=load_desc,
            threshold_value=load_warn,
            actual_value=load,
            unit="%",
        ))

        # --- Guard status ---
        guard = bool(reading.get("guard_status", True))
        guard_score = 0.0 if guard else 25.0
        factors.append(RiskFactor(
            name="Guard Status",
            score_contribution=guard_score,
            description="Guard open / disabled (+25)" if not guard else "Guard engaged",
            threshold_value=1.0,
            actual_value=float(guard),
            unit="bool",
        ))

        # --- Interlock status ---
        interlock = bool(reading.get("interlock_status", True))
        interlock_score = 0.0 if interlock else 20.0
        factors.append(RiskFactor(
            name="Interlock Status",
            score_contribution=interlock_score,
            description="Interlock bypassed / inactive (+20)" if not interlock else "Interlock active",
            threshold_value=1.0,
            actual_value=float(interlock),
            unit="bool",
        ))

        # --- E-stop ---
        estop = bool(reading.get("estop_status", False))
        estop_score = 40.0 if estop else 0.0
        factors.append(RiskFactor(
            name="E-Stop",
            score_contribution=estop_score,
            description="Emergency stop triggered (+40)" if estop else "E-Stop not active",
            threshold_value=0.0,
            actual_value=float(estop),
            unit="bool",
        ))

        # --- Maintenance overdue ---
        maint = bool(reading.get("maintenance_overdue", False))
        maint_score = 15.0 if maint else 0.0
        factors.append(RiskFactor(
            name="Maintenance Overdue",
            score_contribution=maint_score,
            description="Maintenance is overdue (+15)" if maint else "Maintenance up-to-date",
            threshold_value=0.0,
            actual_value=float(maint),
            unit="bool",
        ))

        total = min(100.0, max(0.0, sum(f.score_contribution for f in factors)))
        risk_level = self.get_risk_level(total)
        explanation = self.explain_risk_from_factors(
            machine_id, machine_type, total, risk_level, factors
        )

        return RiskCalculationResult(
            machine_id=machine_id,
            machine_type=machine_type,
            total_score=round(total, 2),
            risk_level=risk_level,
            contributing_factors=factors,
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _graduated_score(
        value: float,
        max_normal: float,
        contributions: list,
        cap: float,
    ):
        """
        Return (score, description) for a graduated threshold rule.
        `contributions` is a list of (pct_over, score, description) tuples,
        evaluated from highest to lowest so the highest matching rule wins.
        """
        if max_normal <= 0:
            return 0.0, "N/A"
        for pct_over, score, desc in reversed(contributions):
            if value > max_normal * (1.0 + pct_over):
                return min(score, cap), desc
        if value > max_normal:
            return min(contributions[0][1] * 0.5, cap), f"Slightly above max ({value:.2f} > {max_normal})"
        return 0.0, "Within normal range"

    @staticmethod
    def _rpm_score(rpm: float, rpm_min: float, rpm_max: float):
        if rpm_max <= 0:
            return 0.0, "N/A"
        if rpm > rpm_max:
            pct = (rpm - rpm_max) / rpm_max
            if pct > 0.20:
                return 25.0, f"RPM critically high ({rpm:.0f} rpm, +{pct*100:.0f}% over max)"
            elif pct > 0.10:
                return 15.0, f"RPM above limit ({rpm:.0f} rpm, +{pct*100:.0f}% over max)"
            else:
                return 10.0, f"RPM slightly above max ({rpm:.0f} rpm)"
        if rpm < rpm_min and rpm_min > 0:
            pct = (rpm_min - rpm) / rpm_min
            if pct > 0.20:
                return 25.0, f"RPM critically low ({rpm:.0f} rpm, -{pct*100:.0f}% below min)"
            elif pct > 0.10:
                return 15.0, f"RPM below minimum ({rpm:.0f} rpm)"
            else:
                return 10.0, f"RPM slightly below minimum ({rpm:.0f} rpm)"
        return 0.0, "RPM within normal range"

    @staticmethod
    def get_risk_level(score: float) -> str:
        if score < 15:
            return "LOW"
        elif score < 30:
            return "MODERATE"
        elif score < 50:
            return "ELEVATED"
        elif score < 70:
            return "HIGH"
        else:
            return "CRITICAL"

    @staticmethod
    def explain_risk_from_factors(
        machine_id: str,
        machine_type: str,
        total_score: float,
        risk_level: str,
        factors: List[RiskFactor],
    ) -> str:
        lines = [
            f"Risk Assessment for {machine_id} ({machine_type})",
            f"Overall Risk Level: {risk_level}  |  Total Score: {total_score:.1f}/100",
            "",
            "Contributing Factors:",
        ]
        active = [f for f in factors if f.score_contribution > 0]
        if not active:
            lines.append("  • No risk factors detected — machine operating normally.")
        else:
            for f in sorted(active, key=lambda x: x.score_contribution, reverse=True):
                lines.append(
                    f"  • {f.name}: +{f.score_contribution:.1f} pts — {f.description} "
                    f"(actual: {f.actual_value} {f.unit}, threshold: {f.threshold_value} {f.unit})"
                )
        return "\n".join(lines)

    def explain_risk(self, result: RiskCalculationResult) -> str:
        """Public wrapper for generating a natural-language explanation."""
        return self.explain_risk_from_factors(
            result.machine_id,
            result.machine_type,
            result.total_score,
            result.risk_level,
            result.contributing_factors,
        )
