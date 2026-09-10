"""
SAFEGUARD AI - Database seeder  (sync SQLAlchemy)
Seeds the Machine table and (optionally) generates sample MachineReading rows.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.database.models import Machine, MachineStatus
from backend.simulation.simulator import MACHINE_CONFIGS, simulation_manager


# ─────────────────────────────────────────────────────────────────────────────
# Machine seed data
# ─────────────────────────────────────────────────────────────────────────────

def seed_machines(db: Session) -> None:
    """
    Insert Machine rows for every machine in MACHINE_CONFIGS if not already present.
    Safe to call multiple times (idempotent).
    """
    from backend.database.models import Machine, MachineStatus

    now = datetime.now(timezone.utc)
    for mid, cfg in MACHINE_CONFIGS.items():
        existing = db.query(Machine).filter(Machine.machine_id == mid).first()
        if existing:
            continue

        thresholds = cfg["thresholds"]
        machine = Machine(
            machine_id     = mid,
            name           = cfg["name"],
            machine_type   = cfg["machine_type"],
            location       = cfg["location"],
            manufacturer   = cfg.get("manufacturer", ""),
            model_number   = cfg.get("model_number", ""),
            status         = MachineStatus.OPERATIONAL,
            is_active      = True,
            installation_date = datetime(2019, 1, 1),
            last_maintenance  = now - timedelta(days=30),
            next_maintenance_due = now + timedelta(days=60),
            config = {
                "thresholds": {
                    k: getattr(thresholds, k)
                    for k in thresholds.__dataclass_fields__
                },
                "base": cfg.get("base", {}),
            },
            created_at = now,
            updated_at = now,
        )
        db.add(machine)

    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Sample readings seed
# ─────────────────────────────────────────────────────────────────────────────

def seed_sample_readings(
    db: Session,
    ticks: int = 50,
    skip_if_exists: bool = True,
) -> int:
    """
    Generate *ticks* simulation steps and persist the resulting MachineReading rows.

    Parameters
    ----------
    ticks          : number of simulation steps to run
    skip_if_exists : skip if any readings already exist (idempotent)

    Returns
    -------
    Number of rows written.
    """
    from backend.database.models import MachineReading, RiskLevel
    from backend.risk_engine.engine import risk_engine

    if skip_if_exists:
        count = db.query(MachineReading).limit(1).count()
        if count > 0:
            return 0

    rows_written = 0
    now = datetime.now(timezone.utc)

    for tick_i in range(ticks):
        readings = simulation_manager.tick()
        for machine_id, reading in readings.items():
            # Quick inline risk assessment for seed data
            risk = risk_engine.assess(
                machine_id       = machine_id,
                temperature      = reading.temperature,
                vibration        = reading.vibration,
                rpm              = reading.rpm,
                pressure         = reading.pressure,
                load             = reading.load,
                guard_status     = reading.guard_status,
                interlock_active = reading.interlock_active,
                emergency_stop   = reading.emergency_stop,
                door_locked      = reading.door_locked,
                maintenance_overdue = reading.maintenance_overdue,
            )

            try:
                rl = RiskLevel(risk.risk_level)
            except ValueError:
                rl = RiskLevel.LOW

            # Backdate timestamps to create plausible history
            ts = now - timedelta(seconds=(ticks - tick_i) * 30)

            row = MachineReading(
                machine_id          = machine_id,
                timestamp           = ts,
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
                risk_score          = risk.risk_score,
                risk_level          = rl,
                anomaly_detected    = False,
                anomaly_score       = 0.0,
                is_simulated        = True,
                simulation_scenario = reading.scenario,
            )
            db.add(row)
            rows_written += 1

    db.commit()
    return rows_written


# ─────────────────────────────────────────────────────────────────────────────
# Combined seed entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_all_seeds(db: Session, sample_ticks: int = 50) -> None:
    """Run machine + sample-readings seeds in the correct order."""
    seed_machines(db)
    seed_sample_readings(db, ticks=sample_ticks)
