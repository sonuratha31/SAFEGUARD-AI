"""
machine_simulator.py
Realistic simulation engine for 5 industrial machines.
"""
from __future__ import annotations

import random
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional


# ---------------------------------------------------------------------------
# Simulation mode
# ---------------------------------------------------------------------------

class SimMode(str, Enum):
    NORMAL = "NORMAL"
    DEGRADING = "DEGRADING"
    ANOMALY = "ANOMALY"
    FAULT = "FAULT"


# ---------------------------------------------------------------------------
# Machine configuration
# ---------------------------------------------------------------------------

@dataclass
class MachineConfig:
    machine_id: str
    name: str
    machine_type: str
    location: str
    # Normal operating ranges
    temp_min: float
    temp_max: float
    vibration_min: float
    vibration_max: float
    rpm_min: float
    rpm_max: float
    pressure_min: float
    pressure_max: float
    load_min: float
    load_max: float
    # How many simulated ticks equal "one maintenance hour"
    ticks_per_maintenance_hour: int = 60
    maintenance_interval_hours: int = 500


MACHINE_CONFIGS: Dict[str, MachineConfig] = {
    "M-001": MachineConfig(
        machine_id="M-001", name="CNC Machine", machine_type="CNC_MACHINE",
        location="Shop Floor A",
        temp_min=40, temp_max=75,
        vibration_min=0.5, vibration_max=4.0,
        rpm_min=500, rpm_max=3000,
        pressure_min=2, pressure_max=8,
        load_min=20, load_max=80,
    ),
    "M-002": MachineConfig(
        machine_id="M-002", name="Hydraulic Press", machine_type="HYDRAULIC_PRESS",
        location="Shop Floor B",
        temp_min=35, temp_max=65,
        vibration_min=0.3, vibration_max=3.0,
        rpm_min=100, rpm_max=800,
        pressure_min=50, pressure_max=250,
        load_min=30, load_max=90,
    ),
    "M-003": MachineConfig(
        machine_id="M-003", name="Industrial Motor", machine_type="INDUSTRIAL_MOTOR",
        location="Utility Room 1",
        temp_min=45, temp_max=85,
        vibration_min=1.0, vibration_max=6.0,
        rpm_min=1000, rpm_max=3600,
        pressure_min=1, pressure_max=5,
        load_min=40, load_max=90,
    ),
    "M-004": MachineConfig(
        machine_id="M-004", name="Compressor", machine_type="COMPRESSOR",
        location="Utility Room 2",
        temp_min=50, temp_max=90,
        vibration_min=0.8, vibration_max=5.0,
        rpm_min=800, rpm_max=2400,
        pressure_min=4, pressure_max=12,
        load_min=50, load_max=95,
    ),
    "M-005": MachineConfig(
        machine_id="M-005", name="Conveyor System", machine_type="CONVEYOR_SYSTEM",
        location="Assembly Line 1",
        temp_min=30, temp_max=55,
        vibration_min=0.2, vibration_max=2.5,
        rpm_min=50, rpm_max=300,
        pressure_min=1, pressure_max=3,
        load_min=20, load_max=70,
    ),
}


# ---------------------------------------------------------------------------
# Machine state
# ---------------------------------------------------------------------------

@dataclass
class MachineState:
    machine_id: str
    mode: SimMode = SimMode.NORMAL
    # Current telemetry
    temperature: float = 0.0
    vibration: float = 0.0
    rpm: float = 0.0
    pressure: float = 0.0
    load: float = 0.0
    # Safety flags
    guard_status: bool = True
    interlock_status: bool = True
    estop_status: bool = False
    maintenance_overdue: bool = False
    # Internal degradation counters
    degradation_ticks: int = 0
    anomaly_ticks_remaining: int = 0
    ticks_since_maintenance: int = 0
    # Trend accumulators (slow drift)
    temp_drift: float = 0.0
    vibration_drift: float = 0.0


# ---------------------------------------------------------------------------
# Simulator engine
# ---------------------------------------------------------------------------

class SimulatorEngine:
    """Maintains simulation state for all 5 machines and advances time."""

    # Probability per tick of transitioning to a new mode
    _TRANSITION_PROBS = {
        SimMode.NORMAL: {SimMode.DEGRADING: 0.005, SimMode.ANOMALY: 0.002},
        SimMode.DEGRADING: {SimMode.NORMAL: 0.008, SimMode.FAULT: 0.003, SimMode.ANOMALY: 0.01},
        SimMode.ANOMALY: {SimMode.NORMAL: 0.15, SimMode.DEGRADING: 0.05},
        SimMode.FAULT: {SimMode.DEGRADING: 0.02},
    }

    def __init__(self) -> None:
        self._states: Dict[str, MachineState] = {}
        self._configs: Dict[str, MachineConfig] = MACHINE_CONFIGS
        for mid, cfg in self._configs.items():
            state = MachineState(machine_id=mid)
            # Initialise telemetry to midpoint of normal range
            state.temperature = (cfg.temp_min + cfg.temp_max) / 2
            state.vibration = (cfg.vibration_min + cfg.vibration_max) / 2
            state.rpm = (cfg.rpm_min + cfg.rpm_max) / 2
            state.pressure = (cfg.pressure_min + cfg.pressure_max) / 2
            state.load = (cfg.load_min + cfg.load_max) / 2
            self._states[mid] = state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance simulation by one tick for all machines."""
        for mid, state in self._states.items():
            cfg = self._configs[mid]
            self._maybe_transition(state)
            self._advance_state(state, cfg)

    def get_reading(self, machine_id: str) -> Dict[str, Any]:
        """Return the current sensor reading for a single machine."""
        state = self._states[machine_id]
        return self._state_to_reading(machine_id, state)

    def get_all_readings(self) -> Dict[str, Dict[str, Any]]:
        """Return current sensor readings for all machines."""
        return {mid: self.get_reading(mid) for mid in self._states}

    def simulate_what_if(
        self, machine_id: str, overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Return a reading for machine_id with user-supplied overrides applied.
        Does NOT mutate internal state.
        """
        state = self._states[machine_id]
        reading = self._state_to_reading(machine_id, state)
        reading.update(overrides)
        return reading

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_transition(self, state: MachineState) -> None:
        transitions = self._TRANSITION_PROBS.get(state.mode, {})
        for target_mode, prob in transitions.items():
            if random.random() < prob:
                state.mode = target_mode
                if target_mode == SimMode.ANOMALY:
                    state.anomaly_ticks_remaining = random.randint(5, 20)
                elif target_mode == SimMode.NORMAL:
                    state.degradation_ticks = 0
                    state.temp_drift = 0.0
                    state.vibration_drift = 0.0
                break

    def _advance_state(self, state: MachineState, cfg: MachineConfig) -> None:
        mode = state.mode

        # Maintenance overdue tracking
        state.ticks_since_maintenance += 1
        maintenance_interval_ticks = (
            cfg.maintenance_interval_hours * cfg.ticks_per_maintenance_hour
        )
        state.maintenance_overdue = state.ticks_since_maintenance > maintenance_interval_ticks

        if mode == SimMode.NORMAL:
            self._apply_normal_noise(state, cfg)

        elif mode == SimMode.DEGRADING:
            state.degradation_ticks += 1
            # Gradual drift upward for temperature and vibration
            state.temp_drift = min(
                cfg.temp_max * 0.4,
                state.temp_drift + random.uniform(0.02, 0.08)
            )
            state.vibration_drift = min(
                cfg.vibration_max * 0.5,
                state.vibration_drift + random.uniform(0.005, 0.02)
            )
            self._apply_normal_noise(state, cfg)
            state.temperature += state.temp_drift
            state.vibration += state.vibration_drift

        elif mode == SimMode.ANOMALY:
            state.anomaly_ticks_remaining = max(0, state.anomaly_ticks_remaining - 1)
            # Burst spike in temperature and vibration
            spike_factor = random.uniform(1.2, 1.6)
            mid_temp = (cfg.temp_min + cfg.temp_max) / 2
            mid_vib = (cfg.vibration_min + cfg.vibration_max) / 2
            state.temperature = mid_temp * spike_factor + random.gauss(0, 2)
            state.vibration = mid_vib * spike_factor + random.gauss(0, 0.3)
            self._apply_normal_noise(state, cfg, temp=False, vibration=False)
            # Small chance guard/interlock trips during anomaly
            if random.random() < 0.05:
                state.guard_status = False
            if random.random() < 0.03:
                state.interlock_status = False

        elif mode == SimMode.FAULT:
            # Values pushed well beyond normal range
            state.temperature = cfg.temp_max * random.uniform(1.25, 1.45)
            state.vibration = cfg.vibration_max * random.uniform(1.3, 1.6)
            state.rpm = cfg.rpm_max * random.uniform(0.05, 0.2)
            state.pressure = cfg.pressure_max * random.uniform(1.1, 1.3)
            state.load = min(100.0, cfg.load_max * random.uniform(1.1, 1.2))
            state.guard_status = random.random() > 0.3
            state.interlock_status = random.random() > 0.4
            state.estop_status = random.random() < 0.6

        # Recovery: restore flags when returning to normal
        if mode == SimMode.NORMAL:
            state.guard_status = True
            state.interlock_status = True
            state.estop_status = False

        # Clamp values to physically plausible minima
        state.temperature = max(15.0, state.temperature)
        state.vibration = max(0.0, state.vibration)
        state.rpm = max(0.0, state.rpm)
        state.pressure = max(0.0, state.pressure)
        state.load = max(0.0, min(100.0, state.load))

    def _apply_normal_noise(
        self,
        state: MachineState,
        cfg: MachineConfig,
        temp: bool = True,
        vibration: bool = True,
    ) -> None:
        """Apply Gaussian noise and a slow sinusoidal cycle to telemetry."""
        t = state.ticks_since_maintenance  # use as a proxy for time

        if temp:
            baseline = (cfg.temp_min + cfg.temp_max) / 2
            amplitude = (cfg.temp_max - cfg.temp_min) / 2 * 0.3
            state.temperature = (
                baseline
                + amplitude * math.sin(t / 80.0)
                + random.gauss(0, (cfg.temp_max - cfg.temp_min) * 0.03)
            )

        if vibration:
            baseline = (cfg.vibration_min + cfg.vibration_max) / 2
            amplitude = (cfg.vibration_max - cfg.vibration_min) / 2 * 0.2
            state.vibration = max(
                0.0,
                baseline
                + amplitude * math.sin(t / 50.0 + 1.0)
                + random.gauss(0, (cfg.vibration_max - cfg.vibration_min) * 0.05),
            )

        rpm_baseline = (cfg.rpm_min + cfg.rpm_max) / 2
        state.rpm = max(
            0.0,
            rpm_baseline + random.gauss(0, (cfg.rpm_max - cfg.rpm_min) * 0.04),
        )

        pressure_baseline = (cfg.pressure_min + cfg.pressure_max) / 2
        state.pressure = max(
            0.0,
            pressure_baseline + random.gauss(0, (cfg.pressure_max - cfg.pressure_min) * 0.04),
        )

        load_baseline = (cfg.load_min + cfg.load_max) / 2
        state.load = max(
            0.0,
            min(
                100.0,
                load_baseline + random.gauss(0, (cfg.load_max - cfg.load_min) * 0.06),
            ),
        )

    @staticmethod
    def _state_to_reading(machine_id: str, state: MachineState) -> Dict[str, Any]:
        return {
            "machine_id": machine_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "temperature": round(state.temperature, 2),
            "vibration": round(state.vibration, 3),
            "rpm": round(state.rpm, 1),
            "pressure": round(state.pressure, 2),
            "load": round(state.load, 1),
            "guard_status": state.guard_status,
            "interlock_status": state.interlock_status,
            "estop_status": state.estop_status,
            "maintenance_overdue": state.maintenance_overdue,
            "simulation_mode": state.mode.value,
        }
