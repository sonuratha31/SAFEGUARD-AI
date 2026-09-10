"""
SAFEGUARD AI - Machine Simulation Engine  (Phase 2 complete)
Generates realistic time-series telemetry for 5 industrial machines.

Supported scenarios
-------------------
1.  normal               – steady-state operation with ±noise
2.  degrading            – gradual parameter drift over time
3.  overheating          – temperature climbs toward and beyond safe limit
4.  excessive_vibration  – vibration escalates (bearing / imbalance fault)
5.  excessive_pressure   – pressure rises toward critical (hydraulic / compressor)
6.  overload             – load and current exceed rated values
7.  guard_interlock_failure – guard / interlock trip
8.  maintenance_overdue  – machine continues running past scheduled service
9.  sensor_anomaly       – one or more sensors return erratic / stuck values
10. anomaly              – combined / sudden abnormal spike (catch-all)
11. critical             – multi-parameter severe fault (machine must stop)
12. maintenance          – machine undergoing maintenance (low values, coming down)
13. post_maintenance     – fresh after service, recovering to normal

The simulator is intentionally deterministic given the same seed so tests are
reproducible, while each machine gets a distinct seed for variety.
"""
from __future__ import annotations

import math
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Scenario enumeration
# ─────────────────────────────────────────────────────────────────────────────

class SimulationScenario(str, Enum):
    NORMAL               = "normal"
    DEGRADING            = "degrading"
    OVERHEATING          = "overheating"
    EXCESSIVE_VIBRATION  = "excessive_vibration"
    EXCESSIVE_PRESSURE   = "excessive_pressure"
    OVERLOAD             = "overload"
    GUARD_INTERLOCK_FAIL = "guard_interlock_failure"
    MAINTENANCE_OVERDUE  = "maintenance_overdue"
    SENSOR_ANOMALY       = "sensor_anomaly"
    ANOMALY              = "anomaly"
    CRITICAL             = "critical"
    MAINTENANCE          = "maintenance"
    POST_MAINTENANCE     = "post_maintenance"


# Human-readable labels
SCENARIO_LABELS: Dict[str, str] = {
    "normal":                "Normal Operation",
    "degrading":             "Gradual Degradation",
    "overheating":           "Overheating",
    "excessive_vibration":   "Excessive Vibration",
    "excessive_pressure":    "Excessive Pressure",
    "overload":              "Overload",
    "guard_interlock_failure":"Guard / Interlock Failure",
    "maintenance_overdue":   "Maintenance Overdue",
    "sensor_anomaly":        "Sensor Anomaly",
    "anomaly":               "Sudden Abnormal Condition",
    "critical":              "Critical Fault",
    "maintenance":           "Under Maintenance",
    "post_maintenance":      "Post-Maintenance Recovery",
}

# Scenarios that can be externally injected
INJECTABLE_SCENARIOS = [
    "normal", "degrading", "overheating", "excessive_vibration",
    "excessive_pressure", "overload", "guard_interlock_failure",
    "maintenance_overdue", "sensor_anomaly", "anomaly", "critical",
    "maintenance",
]


# ─────────────────────────────────────────────────────────────────────────────
# Safe operating thresholds
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MachineThresholds:
    temp_min: float
    temp_max: float
    temp_critical: float

    vibration_max: float
    vibration_critical: float

    rpm_min: float
    rpm_max: float
    rpm_critical: float

    pressure_max: float
    pressure_critical: float

    load_max: float
    load_critical: float

    current_max: float
    voltage_nominal: float

    # Maintenance interval (simulated operating hours)
    maintenance_interval_hours: float = 500.0


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry reading
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TelemetryReading:
    """Complete telemetry snapshot for one machine at one point in time."""
    machine_id: str
    timestamp: datetime

    # Continuous sensors
    temperature: float          # °C
    vibration: float            # mm/s RMS
    rpm: float                  # rev/min
    pressure: float             # bar
    load: float                 # % of rated
    current: float              # A
    voltage: float              # V
    power_consumption: float    # kW

    # Binary safety sensors
    guard_status: bool          # True = guard in place
    interlock_active: bool      # True = interlock engaged
    emergency_stop: bool        # True = e-stop tripped
    door_locked: bool           # True = access door locked

    # Operational counters
    operating_hours: float      # cumulative hours since last maintenance
    maintenance_overdue: bool   # True when hours exceed interval

    # Simulation metadata
    scenario: str
    is_simulated: bool = True

    # Computed status (derived from values + thresholds at snapshot time)
    machine_status: str = "operational"  # operational / warning / high_risk / critical / maintenance / offline

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


# ─────────────────────────────────────────────────────────────────────────────
# Machine catalogue
# ─────────────────────────────────────────────────────────────────────────────

MACHINE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "M-001": {
        "machine_id": "M-001",
        "name": "CNC Machining Center",
        "machine_type": "cnc_machine",
        "location": "Bay A - Zone 1",
        "manufacturer": "Haas Automation",
        "model_number": "VF-2SS",
        "thresholds": MachineThresholds(
            temp_min=15.0,  temp_max=75.0,  temp_critical=90.0,
            vibration_max=4.5, vibration_critical=7.0,
            rpm_min=0.0, rpm_max=8000.0, rpm_critical=9000.0,
            pressure_max=80.0,  pressure_critical=100.0,
            load_max=85.0,      load_critical=100.0,
            current_max=50.0,   voltage_nominal=480.0,
            maintenance_interval_hours=500.0,
        ),
        "base": {
            "temperature": 42.0, "vibration": 1.8, "rpm": 3500.0,
            "pressure": 55.0, "load": 60.0, "current": 28.0, "voltage": 480.0,
        },
    },
    "M-002": {
        "machine_id": "M-002",
        "name": "Hydraulic Press",
        "machine_type": "hydraulic_press",
        "location": "Bay B - Zone 2",
        "manufacturer": "Schuler Group",
        "model_number": "HPS-500",
        "thresholds": MachineThresholds(
            temp_min=15.0,  temp_max=65.0,  temp_critical=80.0,
            vibration_max=6.0, vibration_critical=10.0,
            rpm_min=0.0, rpm_max=1500.0, rpm_critical=1800.0,
            pressure_max=250.0, pressure_critical=300.0,
            load_max=90.0,      load_critical=105.0,
            current_max=80.0,   voltage_nominal=480.0,
            maintenance_interval_hours=400.0,
        ),
        "base": {
            "temperature": 45.0, "vibration": 2.5, "rpm": 900.0,
            "pressure": 180.0, "load": 70.0, "current": 55.0, "voltage": 480.0,
        },
    },
    "M-003": {
        "machine_id": "M-003",
        "name": "Industrial Motor Drive",
        "machine_type": "industrial_motor",
        "location": "Bay C - Zone 1",
        "manufacturer": "ABB",
        "model_number": "ACS880-75kW",
        "thresholds": MachineThresholds(
            temp_min=10.0,  temp_max=80.0,  temp_critical=100.0,
            vibration_max=5.0, vibration_critical=8.5,
            rpm_min=0.0, rpm_max=1500.0, rpm_critical=1650.0,
            pressure_max=5.0,   pressure_critical=8.0,
            load_max=95.0,      load_critical=110.0,
            current_max=150.0,  voltage_nominal=400.0,
            maintenance_interval_hours=600.0,
        ),
        "base": {
            "temperature": 55.0, "vibration": 2.0, "rpm": 1200.0,
            "pressure": 2.0, "load": 75.0, "current": 110.0, "voltage": 400.0,
        },
    },
    "M-004": {
        "machine_id": "M-004",
        "name": "Air Compressor Unit",
        "machine_type": "compressor",
        "location": "Bay D - Zone 3",
        "manufacturer": "Atlas Copco",
        "model_number": "GA75-VSD",
        "thresholds": MachineThresholds(
            temp_min=10.0,  temp_max=90.0,  temp_critical=110.0,
            vibration_max=3.5, vibration_critical=6.0,
            rpm_min=0.0, rpm_max=3600.0, rpm_critical=4000.0,
            pressure_max=12.0,  pressure_critical=14.0,
            load_max=100.0,     load_critical=115.0,
            current_max=130.0,  voltage_nominal=400.0,
            maintenance_interval_hours=350.0,
        ),
        "base": {
            "temperature": 68.0, "vibration": 1.5, "rpm": 2900.0,
            "pressure": 8.5, "load": 80.0, "current": 95.0, "voltage": 400.0,
        },
    },
    "M-005": {
        "machine_id": "M-005",
        "name": "Conveyor Belt System",
        "machine_type": "conveyor",
        "location": "Bay E - Zone 2",
        "manufacturer": "Rexnord",
        "model_number": "CBF-200",
        "thresholds": MachineThresholds(
            temp_min=10.0,  temp_max=60.0,  temp_critical=75.0,
            vibration_max=3.0, vibration_critical=5.5,
            rpm_min=0.0, rpm_max=600.0, rpm_critical=700.0,
            pressure_max=6.0,   pressure_critical=8.0,
            load_max=90.0,      load_critical=105.0,
            current_max=40.0,   voltage_nominal=380.0,
            maintenance_interval_hours=250.0,
        ),
        "base": {
            "temperature": 35.0, "vibration": 1.2, "rpm": 400.0,
            "pressure": 3.5, "load": 55.0, "current": 25.0, "voltage": 380.0,
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Per-machine simulator
# ─────────────────────────────────────────────────────────────────────────────

class MachineSimulator:
    """
    Simulates realistic telemetry for a single machine across all scenarios.

    All numeric state evolves continuously — readings are never random-only;
    they are anchored to physical baselines and drift/ramp toward fault values
    in a predictable, reproducible way.
    """

    # Seconds of real-time that one simulation tick represents
    TICK_SECONDS: float = 5.0
    # Simulated ticks per operating hour
    TICKS_PER_HOUR: float = 3600.0 / TICK_SECONDS   # 720 ticks/hr

    def __init__(self, machine_id: str, seed: Optional[int] = None):
        if machine_id not in MACHINE_CONFIGS:
            raise ValueError(f"Unknown machine_id: {machine_id}")

        self.machine_id      = machine_id
        self.config          = MACHINE_CONFIGS[machine_id]
        self.thresholds: MachineThresholds = self.config["thresholds"]
        self.base            = dict(self.config["base"])

        # Use per-machine deterministic seed for reproducibility
        self._rng = random.Random(seed if seed is not None else hash(machine_id) & 0x7FFFFFFF)

        # ── Scenario state ────────────────────────────────────────────────
        self.scenario        = SimulationScenario.NORMAL
        self.scenario_steps  = 0          # ticks spent in current scenario
        self.degradation     = 0.0        # 0.0 = new, 1.0 = fully degraded

        # Fault ramp accumulators (reset when scenario changes)
        self._fault_temp_add   = 0.0
        self._fault_vib_mul    = 1.0
        self._fault_pres_add   = 0.0
        self._fault_load_add   = 0.0
        self._anomaly_ttl      = 0        # ticks remaining in anomaly burst
        self._sensor_stuck: Dict[str, Optional[float]] = {}  # param->stuck value

        # ── Safety state ─────────────────────────────────────────────────
        self.guard_status    = True
        self.interlock_active = True
        self.emergency_stop  = False
        self.door_locked     = True

        # ── Time / maintenance ────────────────────────────────────────────
        self.time_step           = 0
        self.operating_hours     = 0.0    # cumulative hours since last maintenance reset
        self.maintenance_overdue = False

    # ──────────────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────────────

    def generate_reading(self) -> TelemetryReading:
        """Advance one tick and return the resulting telemetry snapshot."""
        self._advance()
        return self._snapshot()

    def generate_history(
        self,
        n_points: int = 200,
        interval_seconds: int = 30,
    ) -> List[TelemetryReading]:
        """
        Generate *n_points* readings spaced *interval_seconds* apart,
        timestamped backwards from now.
        """
        now = datetime.now(timezone.utc)
        readings: List[TelemetryReading] = []
        for i in range(n_points, 0, -1):
            r = self.generate_reading()
            r.timestamp = now - timedelta(seconds=i * interval_seconds)
            readings.append(r)
        return readings

    def inject_scenario(
        self,
        scenario: str,
        degradation: Optional[float] = None,
    ) -> None:
        """
        Externally force a scenario (can be called by the API / test harness).
        Resets fault ramps so effects are clean from this tick onward.
        """
        try:
            new = SimulationScenario(scenario)
        except ValueError:
            raise ValueError(
                f"Unknown scenario '{scenario}'. Valid: {INJECTABLE_SCENARIOS}"
            )
        self.scenario       = new
        self.scenario_steps = 0
        self._reset_fault_ramps()

        if degradation is not None:
            self.degradation = max(0.0, min(1.0, float(degradation)))

        # Scenario-specific initialisation
        if new == SimulationScenario.ANOMALY:
            self._anomaly_ttl = self._rng.randint(8, 20)
        elif new == SimulationScenario.GUARD_INTERLOCK_FAIL:
            self.guard_status    = False
            self.interlock_active = False
        elif new in (SimulationScenario.MAINTENANCE, SimulationScenario.POST_MAINTENANCE):
            self.emergency_stop = False
            self.guard_status   = True
            self.interlock_active = True

        logger.info("[%s] Scenario injected: %s (deg=%.2f)", self.machine_id, scenario, self.degradation)

    def reset_to_normal(self) -> None:
        """Restore machine to clean normal operating state."""
        self.inject_scenario("normal", degradation=0.0)
        self.guard_status     = True
        self.interlock_active = True
        self.emergency_stop   = False
        self.door_locked      = True
        self.maintenance_overdue = False
        self.operating_hours  = 0.0
        logger.info("[%s] Reset to normal", self.machine_id)

    def acknowledge_maintenance(self) -> None:
        """Reset operating hours counter after maintenance is performed."""
        self.operating_hours     = 0.0
        self.maintenance_overdue = False
        self.inject_scenario("post_maintenance")

    # ──────────────────────────────────────────────────────────────────────
    # Internal tick logic
    # ──────────────────────────────────────────────────────────────────────

    def _advance(self) -> None:
        self.time_step      += 1
        self.scenario_steps += 1

        # Accumulate operating hours (exclude maintenance downtime)
        if self.scenario not in (
            SimulationScenario.MAINTENANCE, SimulationScenario.POST_MAINTENANCE
        ):
            self.operating_hours += self.TICK_SECONDS / 3600.0
            self.maintenance_overdue = (
                self.operating_hours >= self.thresholds.maintenance_interval_hours
            )

        self._auto_transition()
        self._advance_fault_ramps()

    def _auto_transition(self) -> None:
        """
        Probabilistic auto-transitions between scenarios so that without
        explicit injection the machine goes through a realistic lifecycle.
        """
        s = self.scenario
        r = self._rng.random

        if s == SimulationScenario.NORMAL:
            if r() < 0.0008:     # ~0.08 % per tick → avg ~208 min at 5s/tick
                self.inject_scenario("degrading")

        elif s == SimulationScenario.DEGRADING:
            self.degradation = min(1.0, self.degradation + 0.003)
            if self.degradation >= 0.55 and r() < 0.04:
                self.inject_scenario("anomaly")

        elif s == SimulationScenario.ANOMALY:
            self._anomaly_ttl = max(0, self._anomaly_ttl - 1)
            if self._anomaly_ttl <= 0:
                self.inject_scenario("degrading", degradation=self.degradation)

        elif s == SimulationScenario.MAINTENANCE:
            self.degradation = max(0.0, self.degradation - 0.05)
            # Don't exit maintenance until at least 5 ticks have passed
            # (prevents immediate auto-exit when degradation starts at 0.0)
            if self.degradation <= 0.02 and self.scenario_steps >= 5:
                self.inject_scenario("post_maintenance")

        elif s == SimulationScenario.POST_MAINTENANCE:
            if r() < 0.04:
                self.inject_scenario("normal", degradation=0.0)

    def _reset_fault_ramps(self) -> None:
        self._fault_temp_add  = 0.0
        self._fault_vib_mul   = 1.0
        self._fault_pres_add  = 0.0
        self._fault_load_add  = 0.0
        self._sensor_stuck    = {}
        # Restore safety flags (scenarios can re-trip them explicitly)
        self.guard_status     = True
        self.interlock_active = True
        self.emergency_stop   = False

    def _advance_fault_ramps(self) -> None:
        """Update continuous fault ramp accumulators each tick."""
        s = self.scenario

        if s == SimulationScenario.OVERHEATING:
            # Temperature climbs ~0.15 °C per tick until it hits critical
            self._fault_temp_add = min(
                self.thresholds.temp_critical - self.base["temperature"] + 5,
                self._fault_temp_add + 0.15,
            )

        elif s == SimulationScenario.EXCESSIVE_VIBRATION:
            # Vibration multiplier ramps from 1.0 → ~2.5× over ~100 ticks
            self._fault_vib_mul = min(2.8, self._fault_vib_mul + 0.017)

        elif s == SimulationScenario.EXCESSIVE_PRESSURE:
            # Pressure add ramps until critical
            self._fault_pres_add = min(
                self.thresholds.pressure_critical - self.base["pressure"] + 3,
                self._fault_pres_add + 0.2,
            )

        elif s == SimulationScenario.OVERLOAD:
            # Load and current ramp to > 100 %
            self._fault_load_add = min(50.0, self._fault_load_add + 0.3)

        elif s == SimulationScenario.SENSOR_ANOMALY:
            # Initialise stuck / erratic values once
            if not self._sensor_stuck:
                params = self._rng.sample(["temperature", "vibration", "pressure"], k=2)
                for p in params:
                    stuck_val = None  # None → erratic, float → stuck
                    if self._rng.random() < 0.5:
                        stuck_val = self.base[p] * self._rng.uniform(0.1, 2.5)
                    self._sensor_stuck[p] = stuck_val

        elif s == SimulationScenario.GUARD_INTERLOCK_FAIL:
            # Keep safety flags tripped
            self.guard_status     = False
            self.interlock_active = False

        elif s == SimulationScenario.MAINTENANCE_OVERDUE:
            # Maintenance flag is driven by operating hours;
            # here we force it on and let degradation keep ramping slowly
            self.maintenance_overdue = True
            self.degradation = min(1.0, self.degradation + 0.001)

        elif s == SimulationScenario.CRITICAL:
            # In critical state ramp temperature and vibration sharply
            self._fault_temp_add = min(
                self.thresholds.temp_critical * 1.1 - self.base["temperature"],
                self._fault_temp_add + 0.5,
            )
            self._fault_vib_mul  = min(3.0, self._fault_vib_mul + 0.05)
            if self.scenario_steps > 3:
                self.guard_status = False
            if self.scenario_steps > 5:
                self.emergency_stop = True

    # ──────────────────────────────────────────────────────────────────────
    # Reading generation
    # ──────────────────────────────────────────────────────────────────────

    def _noise(self, scale: float) -> float:
        return self._rng.gauss(0.0, scale)

    def _drift(self, base: float) -> float:
        """Slow sinusoidal variation around baseline."""
        return base * (1.0 + 0.02 * math.sin(2 * math.pi * self.time_step / 200.0))

    def _degraded(self, param: str) -> float:
        """Apply degradation multiplier to a base value."""
        d = self.degradation
        mults = {
            "temperature": 1.0 + 0.40 * d,
            "vibration":   1.0 + 0.80 * d,
            "rpm":         1.0 - 0.10 * d,
            "pressure":    1.0 + 0.15 * d,
            "load":        1.0 + 0.20 * d,
            "current":     1.0 + 0.25 * d,
        }
        return mults.get(param, 1.0)

    def _base(self, param: str) -> float:
        """Drift + degradation baseline for a parameter."""
        return self._drift(self.base[param]) * self._degraded(param)

    def _snapshot(self) -> TelemetryReading:
        b = self.base
        s = self.scenario

        # ── Base values with noise ────────────────────────────────────────
        temperature = round(self._base("temperature") + self._noise(b["temperature"] * 0.015), 2)
        vibration   = round(max(0.0, self._base("vibration")  + self._noise(b["vibration"]  * 0.04)),  3)
        rpm         = round(max(0.0, self._base("rpm")         + self._noise(b["rpm"]         * 0.015)), 1)
        pressure    = round(max(0.0, self._base("pressure")    + self._noise(b["pressure"]    * 0.02)),  2)
        load        = round(max(0.0, self._base("load")        + self._noise(b["load"]        * 0.025)), 1)
        current     = round(max(0.0, self._base("current")     + self._noise(b["current"]     * 0.02)),  2)
        voltage     = round(b["voltage"] + self._noise(1.5), 1)

        # ── Scenario-specific overrides ───────────────────────────────────
        if s == SimulationScenario.OVERHEATING:
            temperature = round(temperature + self._fault_temp_add, 2)

        elif s == SimulationScenario.EXCESSIVE_VIBRATION:
            vibration = round(vibration * self._fault_vib_mul, 3)

        elif s == SimulationScenario.EXCESSIVE_PRESSURE:
            pressure = round(pressure + self._fault_pres_add, 2)

        elif s == SimulationScenario.OVERLOAD:
            load    = round(min(load    + self._fault_load_add, 125.0), 1)
            current = round(min(current + self._fault_load_add * (b["current"] / b["load"]), b["current"] * 1.5), 2)

        elif s == SimulationScenario.ANOMALY:
            # Random spike on temperature and/or vibration for anomaly_ttl ticks
            spike = self._rng.uniform(1.25, 1.6)
            temperature = round(temperature * spike, 2)
            vibration   = round(vibration   * spike * 0.8, 3)
            pressure    = round(pressure    * self._rng.uniform(1.0, 1.2), 2)
            if self._rng.random() < 0.12:
                self.guard_status = False
            if self._rng.random() < 0.06:
                self.interlock_active = False

        elif s == SimulationScenario.CRITICAL:
            temperature = round(temperature + self._fault_temp_add, 2)
            vibration   = round(vibration   * self._fault_vib_mul, 3)
            load        = round(min(load * 1.3, 115.0), 1)

        elif s == SimulationScenario.SENSOR_ANOMALY:
            for param, stuck in self._sensor_stuck.items():
                if stuck is not None:
                    # Stuck sensor — constant bad value
                    if param == "temperature": temperature = round(stuck, 2)
                    elif param == "vibration":  vibration   = round(max(0.0, stuck), 3)
                    elif param == "pressure":   pressure    = round(max(0.0, stuck), 2)
                else:
                    # Erratic sensor — large noise
                    if param == "temperature":
                        temperature = round(temperature + self._noise(20.0), 2)
                    elif param == "vibration":
                        vibration   = round(max(0.0, vibration + self._noise(3.0)), 3)
                    elif param == "pressure":
                        pressure    = round(max(0.0, pressure + self._noise(b["pressure"] * 0.4)), 2)

        elif s == SimulationScenario.MAINTENANCE:
            # Parameters ramping down toward zero while machine is stopped
            factor = max(0.05, 1.0 - self.scenario_steps * 0.02)
            temperature = round(max(15.0, temperature * factor), 2)
            vibration   = round(max(0.0,  vibration   * factor), 3)
            rpm         = round(max(0.0,  rpm         * factor), 1)
            pressure    = round(max(0.0,  pressure    * 0.1),    2)
            load        = round(max(0.0,  load        * factor), 1)

        elif s == SimulationScenario.POST_MAINTENANCE:
            # Parameters ramping back up from low (scenario_steps 0..80)
            factor = min(1.0, 0.3 + self.scenario_steps * 0.01)
            temperature = round(self.base["temperature"] * factor + self._noise(1.0), 2)
            vibration   = round(max(0.0, self.base["vibration"] * factor + self._noise(0.05)), 3)
            rpm         = round(max(0.0, self.base["rpm"]       * factor), 1)

        # Guard restore during normal-ish scenarios
        if s in (SimulationScenario.NORMAL, SimulationScenario.POST_MAINTENANCE,
                 SimulationScenario.DEGRADING, SimulationScenario.MAINTENANCE_OVERDUE):
            if not self.guard_status    and self._rng.random() < 0.25:
                self.guard_status = True
            if not self.interlock_active and self._rng.random() < 0.30:
                self.interlock_active = True

        power = round(voltage * current / 1000.0, 2)

        status = _compute_machine_status(
            scenario=s,
            temperature=temperature,
            vibration=vibration,
            pressure=pressure,
            load=load,
            guard_ok=self.guard_status,
            estop=self.emergency_stop,
            thresholds=self.thresholds,
        )

        return TelemetryReading(
            machine_id         = self.machine_id,
            timestamp          = datetime.now(timezone.utc),
            temperature        = temperature,
            vibration          = vibration,
            rpm                = rpm,
            pressure           = pressure,
            load               = min(load, 130.0),
            current            = current,
            voltage            = voltage,
            power_consumption  = power,
            guard_status       = self.guard_status,
            interlock_active   = self.interlock_active,
            emergency_stop     = self.emergency_stop,
            door_locked        = self.door_locked,
            operating_hours    = round(self.operating_hours, 3),
            maintenance_overdue= self.maintenance_overdue,
            scenario           = self.scenario.value,
            machine_status     = status,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Machine status computation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_machine_status(
    scenario: SimulationScenario,
    temperature: float,
    vibration: float,
    pressure: float,
    load: float,
    guard_ok: bool,
    estop: bool,
    thresholds: MachineThresholds,
) -> str:
    """
    Derive the human-readable machine status from current conditions.
    Returns one of: operational / warning / high_risk / critical / maintenance / offline
    """
    if scenario in (SimulationScenario.MAINTENANCE,):
        return "maintenance"

    if estop:
        return "critical"

    if not guard_ok:
        return "critical"

    if (temperature >= thresholds.temp_critical
            or vibration >= thresholds.vibration_critical
            or pressure  >= thresholds.pressure_critical
            or load      >= thresholds.load_critical):
        return "critical"

    if (temperature >= thresholds.temp_max
            or vibration >= thresholds.vibration_max
            or pressure  >= thresholds.pressure_max
            or load      >= thresholds.load_max):
        return "high_risk"

    if (temperature >= thresholds.temp_max * 0.85
            or vibration >= thresholds.vibration_max * 0.80
            or scenario  in (SimulationScenario.DEGRADING,
                             SimulationScenario.MAINTENANCE_OVERDUE)):
        return "warning"

    return "operational"


# ─────────────────────────────────────────────────────────────────────────────
# Multi-machine manager
# ─────────────────────────────────────────────────────────────────────────────

class SimulationManager:
    """
    Manages one MachineSimulator per machine.
    Provides start/stop/reset, scenario injection, and batch ticks.
    """

    def __init__(self) -> None:
        self.simulators: Dict[str, MachineSimulator] = {
            mid: MachineSimulator(mid) for mid in MACHINE_CONFIGS
        }
        self._running = False
        self._pre_warm()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Mark simulation as running (the tick loop is driven by TelemetryService)."""
        self._running = True
        logger.info("SimulationManager started")

    def stop(self) -> None:
        self._running = False
        logger.info("SimulationManager stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Tick / readings ───────────────────────────────────────────────────

    def tick(self) -> Dict[str, TelemetryReading]:
        """Advance all simulators one step and return readings."""
        return {mid: sim.generate_reading() for mid, sim in self.simulators.items()}

    def get_reading(self, machine_id: str) -> Optional[TelemetryReading]:
        """Return the latest reading for one machine without advancing time."""
        sim = self.simulators.get(machine_id)
        if sim is None:
            return None
        return sim._snapshot()

    def generate_history(self, machine_id: str, n_points: int = 200) -> List[TelemetryReading]:
        sim = self.simulators.get(machine_id)
        if sim is None:
            return []
        return sim.generate_history(n_points)

    # ── Scenario control ──────────────────────────────────────────────────

    def inject_fault(
        self,
        machine_id: str,
        scenario: str,
        degradation: Optional[float] = None,
    ) -> None:
        sim = self.simulators.get(machine_id)
        if sim is None:
            raise ValueError(f"Unknown machine_id: {machine_id}")
        sim.inject_scenario(scenario, degradation)

    def reset_machine(self, machine_id: str) -> None:
        sim = self.simulators.get(machine_id)
        if sim is None:
            raise ValueError(f"Unknown machine_id: {machine_id}")
        sim.reset_to_normal()

    def acknowledge_maintenance(self, machine_id: str) -> None:
        sim = self.simulators.get(machine_id)
        if sim is None:
            raise ValueError(f"Unknown machine_id: {machine_id}")
        sim.acknowledge_maintenance()

    def get_machine_status(self, machine_id: str) -> Dict[str, Any]:
        """Return a status summary dict for a single machine."""
        sim = self.simulators.get(machine_id)
        if sim is None:
            raise ValueError(f"Unknown machine_id: {machine_id}")
        reading = sim._snapshot()
        return {
            "machine_id":          machine_id,
            "machine_name":        self.simulators[machine_id].config["name"],
            "machine_type":        self.simulators[machine_id].config["machine_type"],
            "scenario":            sim.scenario.value,
            "scenario_label":      SCENARIO_LABELS.get(sim.scenario.value, sim.scenario.value),
            "machine_status":      reading.machine_status,
            "degradation":         round(sim.degradation, 4),
            "operating_hours":     round(sim.operating_hours, 2),
            "maintenance_overdue": sim.maintenance_overdue,
            "guard_status":        sim.guard_status,
            "interlock_active":    sim.interlock_active,
            "emergency_stop":      sim.emergency_stop,
            "simulation_running":  self._running,
        }

    def get_all_statuses(self) -> List[Dict[str, Any]]:
        return [self.get_machine_status(mid) for mid in self.simulators]

    # ── Internal ──────────────────────────────────────────────────────────

    def _pre_warm(self) -> None:
        """Pre-set varied initial states for a diverse demo view."""
        presets = [
            ("M-001", "normal",              0.0),
            ("M-002", "degrading",           0.30),
            ("M-003", "anomaly",             0.60),
            ("M-004", "normal",              0.05),
            ("M-005", "maintenance_overdue", 0.15),
        ]
        for mid, scenario, deg in presets:
            sim = self.simulators[mid]
            sim.inject_scenario(scenario, deg)
            # Advance time step so readings aren't identical at t=0
            sim.time_step = self.simulators[mid]._rng.randint(50, 200)
        self._running = True


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

simulation_manager = SimulationManager()
