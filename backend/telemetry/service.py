"""
SAFEGUARD AI - Telemetry Service  (Phase 2 complete)

Drives the simulation tick loop, persists readings to the database,
manages simulation lifecycle (start / stop / reset), and provides
current + historical telemetry to the API layer.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from backend.simulation.simulator import (
    simulation_manager,
    MACHINE_CONFIGS,
    INJECTABLE_SCENARIOS,
    SCENARIO_LABELS,
    SimulationScenario,
)
from backend.risk_engine.engine import risk_engine
from backend.risk_engine.anomaly_detection import anomaly_manager
from backend.agents.orchestrator import safety_orchestrator

logger = logging.getLogger(__name__)


class TelemetryService:
    """
    Central telemetry service for SAFEGUARD AI.

    Responsibilities
    ----------------
    * Drive the simulation tick loop (called by the FastAPI background task).
    * Persist every reading to the SQL database (MachineReading table).
    * Maintain in-memory rolling history (fast access for API queries).
    * Expose start / stop / reset / inject-fault controls.
    * Compute risk score and anomaly flag per reading.
    * Provide facility-level aggregated summary.
    """

    def __init__(self) -> None:
        # ── In-memory state ───────────────────────────────────────────────
        self._latest:  Dict[str, Dict[str, Any]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {mid: [] for mid in MACHINE_CONFIGS}
        self._max_history = 300

        # Full analysis cache (multi-agent, slower)
        self._analysis_cache: Dict[str, Dict[str, Any]] = {}

        # Database session factory (set during app startup)
        self._db_session_factory = None   # callable → Session

        # Tick counter and DB-write throttle
        self._tick_count = 0
        self._db_write_every = 1          # write every N ticks (1 = every tick)

        # Simulation running flag (mirrors SimulationManager)
        self._running = False

    # ──────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the simulation."""
        simulation_manager.start()
        self._running = True
        logger.info("TelemetryService started")

    def stop(self) -> None:
        """Stop the simulation (readings freeze at last known values)."""
        simulation_manager.stop()
        self._running = False
        logger.info("TelemetryService stopped")

    @property
    def is_running(self) -> bool:
        return simulation_manager.is_running

    def configure_db(self, session_factory) -> None:
        """Inject the SQLAlchemy Session factory for DB persistence."""
        self._db_session_factory = session_factory
        logger.info("TelemetryService: DB session factory configured")

    # ──────────────────────────────────────────────────────────────────────
    # Tick
    # ──────────────────────────────────────────────────────────────────────

    def tick(self) -> Dict[str, Dict[str, Any]]:
        """
        Advance simulation one step, compute risk, store in memory and DB.
        Returns the enriched state dict for every machine.
        """
        self._tick_count += 1
        readings = simulation_manager.tick()
        result: Dict[str, Dict[str, Any]] = {}

        for machine_id, reading in readings.items():
            telemetry = reading.to_dict()

            # ── Risk scoring ─────────────────────────────────────────────
            risk = risk_engine.assess(
                machine_id=machine_id,
                temperature=reading.temperature,
                vibration=reading.vibration,
                rpm=reading.rpm,
                pressure=reading.pressure,
                load=reading.load,
                guard_status=reading.guard_status,
                interlock_active=reading.interlock_active,
                emergency_stop=reading.emergency_stop,
                door_locked=reading.door_locked,
                maintenance_overdue=reading.maintenance_overdue,
            )

            # ── Anomaly detection ────────────────────────────────────────
            anomaly = anomaly_manager.update(machine_id, {
                "temperature": reading.temperature,
                "vibration":   reading.vibration,
                "rpm":         reading.rpm,
                "pressure":    reading.pressure,
                "load":        reading.load,
                "current":     reading.current,
            })

            machine_cfg = MACHINE_CONFIGS[machine_id]
            state: Dict[str, Any] = {
                **telemetry,
                "machine_name":      machine_cfg["name"],
                "machine_type":      machine_cfg["machine_type"],
                "location":          machine_cfg["location"],
                # risk
                "risk_score":        risk.risk_score,
                "risk_level":        risk.risk_level,
                "risk_factors": [
                    {
                        "name":         f.name,
                        "category":     f.category,
                        "value":        f.value,
                        "threshold":    f.threshold,
                        "contribution": f.contribution,
                        "explanation":  f.explanation,
                    }
                    for f in risk.risk_factors
                ],
                "risk_explanation":  risk.explanation,
                # anomaly
                "anomaly_detected":  anomaly.is_anomaly,
                "anomaly_score":     anomaly.anomaly_score,
                # simulation
                "simulation_running": self._running,
            }

            self._latest[machine_id] = state

            # Rolling in-memory history
            self._history[machine_id].append(state)
            if len(self._history[machine_id]) > self._max_history:
                self._history[machine_id].pop(0)

            # Persist to DB (throttled)
            if self._tick_count % self._db_write_every == 0:
                self._persist_reading(machine_id, reading, risk.risk_score,
                                      risk.risk_level, anomaly.is_anomaly,
                                      anomaly.anomaly_score)

            result[machine_id] = state

        return result

    # ──────────────────────────────────────────────────────────────────────
    # Read helpers
    # ──────────────────────────────────────────────────────────────────────

    def get_current_state(self) -> Dict[str, Dict[str, Any]]:
        """Latest enriched reading for all machines (primes via tick if empty)."""
        if not self._latest:
            return self.tick()
        return self._latest

    def get_machine_state(self, machine_id: str) -> Optional[Dict[str, Any]]:
        return self._latest.get(machine_id)

    def get_history(self, machine_id: str, n: int = 100) -> List[Dict[str, Any]]:
        """Return up to n most-recent in-memory readings."""
        return self._history.get(machine_id, [])[-n:]

    def get_history_from_db(
        self,
        machine_id: str,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return historical readings straight from the SQL database.
        Falls back gracefully to in-memory if DB is unavailable.
        """
        if self._db_session_factory is None:
            return self.get_history(machine_id, limit)

        try:
            from backend.database.models import MachineReading
            from sqlalchemy import desc

            with self._db_session_factory() as db:
                q = db.query(MachineReading).filter(
                    MachineReading.machine_id == machine_id
                )
                if since:
                    q = q.filter(MachineReading.timestamp >= since)
                rows = (
                    q.order_by(desc(MachineReading.timestamp))
                     .limit(limit)
                     .all()
                )
            return [self._reading_row_to_dict(r) for r in reversed(rows)]

        except Exception as exc:
            logger.warning("DB history fetch failed (%s); falling back to memory", exc)
            return self.get_history(machine_id, limit)

    # ──────────────────────────────────────────────────────────────────────
    # Simulation control
    # ──────────────────────────────────────────────────────────────────────

    def inject_fault(
        self,
        machine_id: str,
        scenario: str,
        degradation: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Inject a fault scenario on a machine.
        Returns the first reading after injection.
        """
        simulation_manager.inject_fault(machine_id, scenario, degradation)
        # Advance one tick so the new scenario takes effect immediately
        readings = self.tick()
        state = readings.get(machine_id, {})
        state["scenario_injected"] = scenario
        state["scenario_label"] = SCENARIO_LABELS.get(scenario, scenario)
        return state

    def reset_machine(self, machine_id: str) -> Dict[str, Any]:
        """Reset a machine to normal operating state."""
        simulation_manager.reset_machine(machine_id)
        readings = self.tick()
        state = readings.get(machine_id, {})
        state["reset"] = True
        return state

    def acknowledge_maintenance(self, machine_id: str) -> Dict[str, Any]:
        """Acknowledge maintenance — resets operating hours, enters post-maintenance."""
        simulation_manager.acknowledge_maintenance(machine_id)
        readings = self.tick()
        return readings.get(machine_id, {})

    def force_scenario(
        self,
        machine_id: str,
        scenario: str,
        degradation: Optional[float] = None,
    ) -> None:
        """Alias kept for backward compatibility with existing API endpoints."""
        simulation_manager.inject_fault(machine_id, scenario, degradation)

    # ──────────────────────────────────────────────────────────────────────
    # Machine status
    # ──────────────────────────────────────────────────────────────────────

    def get_machine_status(self, machine_id: str) -> Dict[str, Any]:
        """
        Return a rich status dict for a single machine.
        Combines simulation state with latest telemetry.
        """
        sim_status = simulation_manager.get_machine_status(machine_id)
        latest = self._latest.get(machine_id, {})

        return {
            **sim_status,
            "risk_score":       latest.get("risk_score", 0.0),
            "risk_level":       latest.get("risk_level", "unknown"),
            "anomaly_detected": latest.get("anomaly_detected", False),
            "temperature":      latest.get("temperature"),
            "vibration":        latest.get("vibration"),
            "rpm":              latest.get("rpm"),
            "pressure":         latest.get("pressure"),
            "load":             latest.get("load"),
            "last_reading_ts":  latest.get("timestamp"),
        }

    def get_all_machine_statuses(self) -> List[Dict[str, Any]]:
        return [self.get_machine_status(mid) for mid in MACHINE_CONFIGS]

    # ──────────────────────────────────────────────────────────────────────
    # Facility summary
    # ──────────────────────────────────────────────────────────────────────

    def get_facility_summary(self) -> Dict[str, Any]:
        states = list(self._latest.values())
        if not states:
            states = list(self.tick().values())

        total    = len(states)
        safe     = sum(1 for s in states if s["risk_score"] <= 20)
        warning  = sum(1 for s in states if 21 <= s["risk_score"] <= 40)
        elevated = sum(1 for s in states if 41 <= s["risk_score"] <= 60)
        high     = sum(1 for s in states if 61 <= s["risk_score"] <= 80)
        critical = sum(1 for s in states if s["risk_score"] > 80)

        avg_risk             = sum(s["risk_score"] for s in states) / total if total else 0
        facility_safety_score = round(100 - avg_risk, 1)

        non_compliant_count  = sum(
            1 for s in states
            for f in s.get("risk_factors", [])
            if f["category"] in ("guard", "emergency_stop")
        )
        compliance_score = max(0, round(100 - (non_compliant_count / max(total, 1)) * 50, 1))

        critical_alerts = sum(
            1 for s in states if s["risk_score"] > 80 or s.get("emergency_stop")
        )
        high_alerts = sum(1 for s in states if 61 <= s["risk_score"] <= 80)

        return {
            "total_machines":        total,
            "safe_machines":         safe,
            "warning_machines":      warning,
            "elevated_machines":     elevated,
            "high_risk_machines":    high,
            "critical_machines":     critical,
            "facility_safety_score": facility_safety_score,
            "compliance_score":      compliance_score,
            "critical_alerts":       critical_alerts,
            "high_alerts":           high_alerts,
            "avg_risk_score":        round(avg_risk, 1),
            "simulation_running":    self._running,
            "timestamp":             datetime.now(timezone.utc).isoformat(),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Machine config helpers
    # ──────────────────────────────────────────────────────────────────────

    def get_all_machine_configs(self) -> List[Dict[str, Any]]:
        configs = []
        for mid, cfg in MACHINE_CONFIGS.items():
            thresholds = cfg["thresholds"]
            configs.append({
                "machine_id":   cfg["machine_id"],
                "name":         cfg["name"],
                "machine_type": cfg["machine_type"],
                "location":     cfg["location"],
                "manufacturer": cfg.get("manufacturer", ""),
                "model_number": cfg.get("model_number", ""),
                "thresholds": {
                    k: getattr(thresholds, k)
                    for k in thresholds.__dataclass_fields__
                },
            })
        return configs

    # ──────────────────────────────────────────────────────────────────────
    # Multi-agent full analysis
    # ──────────────────────────────────────────────────────────────────────

    def run_full_analysis(self, machine_id: str) -> Dict[str, Any]:
        """Run the full multi-agent analysis for one machine (comprehensive, slower)."""
        state = self._latest.get(machine_id)
        if not state:
            self.tick()
            state = self._latest.get(machine_id)
        if not state:
            raise ValueError(f"No data available for {machine_id}")

        result = safety_orchestrator.analyze(
            machine_id=machine_id,
            telemetry=state,
            maintenance_overdue=state.get("maintenance_overdue", False),
        )
        self._analysis_cache[machine_id] = result.to_dict()
        return result.to_dict()

    def get_cached_analysis(self, machine_id: str) -> Optional[Dict[str, Any]]:
        return self._analysis_cache.get(machine_id)

    # ──────────────────────────────────────────────────────────────────────
    # DB helpers
    # ──────────────────────────────────────────────────────────────────────

    def _persist_reading(
        self,
        machine_id: str,
        reading,          # TelemetryReading
        risk_score: float,
        risk_level: str,
        anomaly_detected: bool,
        anomaly_score: float,
    ) -> None:
        """Write one telemetry reading to the MachineReading table."""
        if self._db_session_factory is None:
            return
        try:
            from backend.database.models import MachineReading, RiskLevel
            from sqlalchemy.exc import SQLAlchemyError

            rl = RiskLevel(risk_level) if risk_level in RiskLevel.__members__.values() else RiskLevel.LOW

            with self._db_session_factory() as db:
                row = MachineReading(
                    machine_id          = machine_id,
                    timestamp           = reading.timestamp,
                    temperature         = reading.temperature,
                    vibration           = reading.vibration,
                    rpm                 = reading.rpm,
                    pressure            = reading.pressure,
                    load                = reading.load,
                    current             = reading.current,
                    voltage             = reading.voltage,
                    power_consumption   = reading.power_consumption,
                    guard_status        = reading.guard_status,
                    interlock_active    = reading.interlock_active,
                    emergency_stop      = reading.emergency_stop,
                    door_locked         = reading.door_locked,
                    risk_score          = risk_score,
                    risk_level          = rl,
                    anomaly_detected    = anomaly_detected,
                    anomaly_score       = anomaly_score,
                    is_simulated        = True,
                    simulation_scenario = reading.scenario,
                )
                db.add(row)
                db.commit()
        except Exception as exc:
            # Non-fatal — in-memory still works
            logger.debug("Telemetry DB write skipped: %s", exc)

    @staticmethod
    def _reading_row_to_dict(row) -> Dict[str, Any]:
        """Convert a SQLAlchemy MachineReading row to a plain dict."""
        return {
            "id":                   row.id,
            "machine_id":           row.machine_id,
            "timestamp":            row.timestamp.isoformat() if row.timestamp else None,
            "temperature":          row.temperature,
            "vibration":            row.vibration,
            "rpm":                  row.rpm,
            "pressure":             row.pressure,
            "load":                 row.load,
            "current":              row.current,
            "voltage":              row.voltage,
            "power_consumption":    row.power_consumption,
            "guard_status":         row.guard_status,
            "interlock_active":     row.interlock_active,
            "emergency_stop":       row.emergency_stop,
            "door_locked":          row.door_locked,
            "risk_score":           row.risk_score,
            "risk_level":           row.risk_level.value if row.risk_level else None,
            "anomaly_detected":     row.anomaly_detected,
            "anomaly_score":        row.anomaly_score,
            "is_simulated":         row.is_simulated,
            "simulation_scenario":  row.simulation_scenario,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

telemetry_service = TelemetryService()
