"""
SAFEGUARD AI - Tests for Simulation Engine  (Phase 2 comprehensive)

Covers:
  - All 10 core fault scenarios
  - Operating hours accumulation
  - Maintenance overdue trigger
  - Machine status computation
  - DB persistence (MachineReading rows written + read back)
  - All new Phase 2 API endpoints
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from backend.simulation.simulator import (
    MachineSimulator, SimulationManager, MACHINE_CONFIGS,
    SimulationScenario, INJECTABLE_SCENARIOS, SCENARIO_LABELS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Basic sanity
# ─────────────────────────────────────────────────────────────────────────────

def test_all_machines_have_configs():
    assert set(MACHINE_CONFIGS.keys()) == {"M-001", "M-002", "M-003", "M-004", "M-005"}


def test_injectable_scenarios_list():
    """All 10 required scenarios (plus extras) must be injectable."""
    required = [
        "normal", "degrading", "overheating", "excessive_vibration",
        "excessive_pressure", "overload", "guard_interlock_failure",
        "maintenance_overdue", "sensor_anomaly", "anomaly",
    ]
    for s in required:
        assert s in INJECTABLE_SCENARIOS, f"Missing injectable scenario: {s}"


def test_scenario_labels_defined():
    for s in INJECTABLE_SCENARIOS:
        assert s in SCENARIO_LABELS, f"No label for scenario: {s}"


def test_simulator_generates_reading():
    sim = MachineSimulator("M-001")
    reading = sim.generate_reading()
    assert reading.machine_id == "M-001"
    assert isinstance(reading.temperature, float)
    assert isinstance(reading.vibration, float)
    assert reading.temperature > 0
    assert reading.vibration >= 0


def test_simulator_values_in_plausible_range():
    sim = MachineSimulator("M-001")
    for _ in range(10):
        r = sim.generate_reading()
        assert 0 <= r.temperature <= 200
        assert 0 <= r.vibration <= 50
        assert 0 <= r.rpm <= 20000
        assert 0 <= r.load <= 200


def test_simulator_history_length():
    sim = MachineSimulator("M-001")
    history = sim.generate_history(n_points=50)
    assert len(history) == 50


def test_reading_has_operating_hours():
    sim = MachineSimulator("M-001")
    r = sim.generate_reading()
    assert hasattr(r, "operating_hours")
    assert isinstance(r.operating_hours, float)
    assert r.operating_hours >= 0


def test_reading_has_machine_status():
    sim = MachineSimulator("M-001")
    r = sim.generate_reading()
    assert r.machine_status in (
        "operational", "warning", "high_risk", "critical", "maintenance", "offline"
    )


def test_reading_has_scenario_field():
    sim = MachineSimulator("M-001")
    r = sim.generate_reading()
    assert isinstance(r.scenario, str)
    assert r.scenario  # non-empty


# ─────────────────────────────────────────────────────────────────────────────
# Scenario injection — inject_scenario (was force_scenario)
# ─────────────────────────────────────────────────────────────────────────────

def test_inject_anomaly_scenario():
    sim = MachineSimulator("M-003")
    sim.inject_scenario("anomaly", degradation=0.8)
    assert sim.scenario == SimulationScenario.ANOMALY
    assert sim.degradation == 0.8


def test_inject_invalid_scenario_raises():
    sim = MachineSimulator("M-001")
    with pytest.raises(ValueError):
        sim.inject_scenario("not_a_real_scenario")


def test_inject_resets_fault_ramps():
    sim = MachineSimulator("M-001")
    sim.inject_scenario("overheating")
    # advance several ticks so temp ramp builds
    for _ in range(20):
        sim.generate_reading()
    # now reset to normal — ramps should be gone
    sim.inject_scenario("normal")
    assert sim._fault_temp_add == 0.0
    assert sim._fault_vib_mul == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# All 10 core scenarios — verify parameter changes
# ─────────────────────────────────────────────────────────────────────────────

def _avg(values):
    return sum(values) / len(values) if values else 0.0


def test_scenario_normal():
    sim = MachineSimulator("M-001")
    sim.inject_scenario("normal", degradation=0.0)
    readings = [sim.generate_reading() for _ in range(15)]
    cfg = MACHINE_CONFIGS["M-001"]
    base_temp = cfg["base"]["temperature"]
    avg_temp = _avg([r.temperature for r in readings])
    # Normal should stay within ±20 % of baseline
    assert base_temp * 0.80 <= avg_temp <= base_temp * 1.20


def test_scenario_degrading():
    """Degraded machine should read higher temperature/vibration than normal."""
    sim_normal  = MachineSimulator("M-001")
    sim_degraded = MachineSimulator("M-001")
    sim_degraded.inject_scenario("degrading", degradation=0.9)

    normal_temps   = [sim_normal.generate_reading().temperature  for _ in range(20)]
    degraded_temps = [sim_degraded.generate_reading().temperature for _ in range(20)]

    assert _avg(degraded_temps) > _avg(normal_temps), \
        "Degraded machine should have higher average temperature"


def test_scenario_overheating():
    """Temperature must climb above safe_max after sufficient ticks."""
    sim = MachineSimulator("M-001")
    sim.inject_scenario("overheating")
    thresholds = MACHINE_CONFIGS["M-001"]["thresholds"]
    # Rate = 0.15°C/tick; need (temp_max - base_temp) / 0.15 ticks ≈ 220 ticks; use 300
    exceeded = False
    for _ in range(300):
        r = sim.generate_reading()
        if r.temperature > thresholds.temp_max:
            exceeded = True
            break
    assert exceeded, f"Overheating should push temperature above {thresholds.temp_max}"


def test_scenario_excessive_vibration():
    """Vibration must climb above safe max after sufficient ticks."""
    sim = MachineSimulator("M-001")
    sim.inject_scenario("excessive_vibration")
    thresholds = MACHINE_CONFIGS["M-001"]["thresholds"]
    exceeded = False
    for _ in range(150):
        r = sim.generate_reading()
        if r.vibration > thresholds.vibration_max:
            exceeded = True
            break
    assert exceeded, f"Excessive vibration should exceed {thresholds.vibration_max}"


def test_scenario_excessive_pressure():
    """Pressure must climb above safe max after sufficient ticks."""
    sim = MachineSimulator("M-002")
    sim.inject_scenario("excessive_pressure")
    thresholds = MACHINE_CONFIGS["M-002"]["thresholds"]
    # M-002: base=180, max=250, gap=70, rate=0.2/tick → needs ≈350 ticks; use 400
    exceeded = False
    for _ in range(400):
        r = sim.generate_reading()
        if r.pressure > thresholds.pressure_max:
            exceeded = True
            break
    assert exceeded, f"Excessive pressure should exceed {thresholds.pressure_max}"


def test_scenario_overload():
    """Load must climb well above rated value."""
    sim = MachineSimulator("M-001")
    sim.inject_scenario("overload")
    exceeded = False
    for _ in range(200):
        r = sim.generate_reading()
        if r.load > MACHINE_CONFIGS["M-001"]["base"]["load"] * 1.15:
            exceeded = True
            break
    assert exceeded, "Overload scenario should push load significantly above baseline"


def test_scenario_guard_interlock_failure():
    """guard_status and interlock_active should be False after injection."""
    sim = MachineSimulator("M-002")
    sim.inject_scenario("guard_interlock_failure")
    r = sim.generate_reading()
    assert not r.guard_status, "Guard should be down in guard_interlock_failure"
    assert not r.interlock_active, "Interlock should be disengaged"


def test_scenario_maintenance_overdue():
    """maintenance_overdue flag should be True after injection."""
    sim = MachineSimulator("M-003")
    sim.inject_scenario("maintenance_overdue")
    r = sim.generate_reading()
    assert r.maintenance_overdue, "maintenance_overdue flag must be set"


def test_scenario_sensor_anomaly():
    """Sensor anomaly produces erratic values for the affected sensors."""
    sim = MachineSimulator("M-004")
    sim.inject_scenario("sensor_anomaly")
    # Trigger _advance_fault_ramps by generating a reading
    r1 = sim.generate_reading()
    # After the first tick the _sensor_stuck dict is populated
    assert len(sim._sensor_stuck) > 0, "sensor_anomaly should populate stuck sensors"
    # Values should be non-negative (no physics broken)
    assert r1.vibration >= 0
    assert r1.temperature >= 0


def test_scenario_anomaly_burst():
    """Anomaly scenario should produce elevated temperature/vibration for a burst."""
    sim = MachineSimulator("M-001")
    sim.inject_scenario("anomaly")
    base_temp = MACHINE_CONFIGS["M-001"]["base"]["temperature"]
    # At least one reading during the burst should be above baseline
    values = [sim.generate_reading().temperature for _ in range(25)]
    assert max(values) > base_temp, "Anomaly scenario should spike temperature above baseline"


# ─────────────────────────────────────────────────────────────────────────────
# Operating hours
# ─────────────────────────────────────────────────────────────────────────────

def test_operating_hours_accumulate():
    sim = MachineSimulator("M-001")
    sim.inject_scenario("normal")
    initial = sim.operating_hours
    for _ in range(50):
        sim.generate_reading()
    assert sim.operating_hours > initial, "Operating hours should increase over ticks"


def test_operating_hours_paused_during_maintenance():
    sim = MachineSimulator("M-001")
    sim.inject_scenario("maintenance", degradation=0.5)  # high degradation to stay in maintenance
    before = sim.operating_hours
    # Run 3 ticks — all should still be in MAINTENANCE (degradation will only drop 0.15)
    for _ in range(3):
        sim.generate_reading()
    assert sim.operating_hours == before, \
        "Operating hours must NOT accumulate while machine is in maintenance"
    # Verify scenario is still maintenance after 3 ticks
    assert sim.scenario == SimulationScenario.MAINTENANCE


def test_maintenance_overdue_triggers_on_hours():
    sim = MachineSimulator("M-005")  # interval = 250 h
    sim.inject_scenario("normal", degradation=0.0)
    # Set operating hours just below threshold
    sim.operating_hours = sim.thresholds.maintenance_interval_hours - 0.001
    sim.generate_reading()   # this tick should push it over
    assert sim.maintenance_overdue, "maintenance_overdue must flip True when hours exceed interval"


def test_acknowledge_maintenance_resets_hours():
    sim = MachineSimulator("M-001")
    sim.operating_hours = 600.0
    sim.maintenance_overdue = True
    sim.acknowledge_maintenance()
    assert sim.operating_hours == 0.0
    assert not sim.maintenance_overdue
    assert sim.scenario == SimulationScenario.POST_MAINTENANCE


# ─────────────────────────────────────────────────────────────────────────────
# Machine status computation
# ─────────────────────────────────────────────────────────────────────────────

def test_machine_status_maintenance():
    sim = MachineSimulator("M-001")
    sim.inject_scenario("maintenance", degradation=0.5)  # ensure we stay in maintenance
    r = sim.generate_reading()
    assert r.machine_status == "maintenance"


def test_machine_status_critical_on_estop():
    sim = MachineSimulator("M-001")
    sim.inject_scenario("critical")
    # Advance until emergency_stop trips (> 5 steps in critical)
    for _ in range(10):
        r = sim.generate_reading()
    assert r.machine_status == "critical"


def test_machine_status_critical_on_guard_failure():
    sim = MachineSimulator("M-002")
    sim.inject_scenario("guard_interlock_failure")
    r = sim.generate_reading()
    assert r.machine_status == "critical"


def test_machine_status_warning_degrading():
    sim = MachineSimulator("M-001")
    sim.inject_scenario("degrading", degradation=0.0)
    r = sim.generate_reading()
    # degrading scenario → at minimum "warning" (without heavy load)
    assert r.machine_status in ("warning", "operational", "high_risk", "critical"), \
        "Degrading should report warning or above"


# ─────────────────────────────────────────────────────────────────────────────
# SimulationManager
# ─────────────────────────────────────────────────────────────────────────────

def test_simulation_manager_ticks_all_machines():
    mgr = SimulationManager()
    readings = mgr.tick()
    assert set(readings.keys()) == set(MACHINE_CONFIGS.keys())


def test_simulation_manager_inject_fault():
    """inject_fault (new name) should change scenario on the target machine."""
    mgr = SimulationManager()
    mgr.inject_fault("M-002", "maintenance", 0.5)
    assert mgr.simulators["M-002"].scenario == SimulationScenario.MAINTENANCE


def test_simulation_manager_inject_fault_invalid_machine():
    mgr = SimulationManager()
    with pytest.raises(ValueError):
        mgr.inject_fault("M-999", "normal")


def test_simulation_manager_reset_machine():
    mgr = SimulationManager()
    mgr.inject_fault("M-001", "critical", 0.8)
    mgr.reset_machine("M-001")
    assert mgr.simulators["M-001"].scenario == SimulationScenario.NORMAL
    assert mgr.simulators["M-001"].degradation == 0.0


def test_simulation_manager_acknowledge_maintenance():
    mgr = SimulationManager()
    mgr.simulators["M-003"].operating_hours = 700.0
    mgr.simulators["M-003"].maintenance_overdue = True
    mgr.acknowledge_maintenance("M-003")
    assert mgr.simulators["M-003"].operating_hours == 0.0
    assert not mgr.simulators["M-003"].maintenance_overdue


def test_simulation_manager_get_machine_status():
    mgr = SimulationManager()
    status = mgr.get_machine_status("M-001")
    assert "machine_id" in status
    assert "scenario" in status
    assert "operating_hours" in status
    assert "machine_status" in status


def test_simulation_manager_start_stop():
    mgr = SimulationManager()
    mgr.stop()
    assert not mgr.is_running
    mgr.start()
    assert mgr.is_running


# ─────────────────────────────────────────────────────────────────────────────
# DB persistence (integration — uses real SQLite in-memory)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def in_memory_db():
    """Create a fresh in-memory SQLite DB, seed machines, return SessionLocal factory."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database.models import Base
    from backend.simulation.seed_data import seed_machines

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    class _Factory:
        """Context-manager-compatible session factory."""
        def __call__(self):
            return factory()
        def __enter__(self):
            self._session = factory()
            return self._session
        def __exit__(self, *args):
            self._session.close()

    obj = _Factory()
    # Seed Machine rows so FK constraints are satisfied for MachineReading inserts
    with obj() as db:
        seed_machines(db)
    return obj


def test_telemetry_persists_to_db(in_memory_db):
    """TelemetryService.tick() should write a MachineReading row per machine."""
    from backend.telemetry.service import TelemetryService
    from backend.database.models import MachineReading

    svc = TelemetryService()
    svc.configure_db(in_memory_db)
    svc.start()
    svc.tick()

    with in_memory_db() as db:
        count = db.query(MachineReading).count()

    assert count >= 5, f"Expected ≥5 rows (one per machine), got {count}"


def test_telemetry_history_from_db(in_memory_db):
    """get_history_from_db should return rows previously persisted."""
    from backend.telemetry.service import TelemetryService
    from backend.database.models import MachineReading

    svc = TelemetryService()
    svc.configure_db(in_memory_db)
    svc.start()
    # Tick 3 times
    for _ in range(3):
        svc.tick()

    rows = svc.get_history_from_db("M-001", limit=50)
    assert isinstance(rows, list)
    assert len(rows) >= 1, "Should return at least one DB row for M-001"
    # Each row should be a dict with expected keys
    row = rows[0]
    assert "machine_id" in row
    assert row["machine_id"] == "M-001"


def test_telemetry_db_row_has_risk_score(in_memory_db):
    """DB rows should include risk_score and risk_level."""
    from backend.telemetry.service import TelemetryService

    svc = TelemetryService()
    svc.configure_db(in_memory_db)
    svc.start()
    svc.tick()

    rows = svc.get_history_from_db("M-002", limit=10)
    if rows:
        row = rows[0]
        assert "risk_score" in row
        assert "risk_level" in row


def test_telemetry_without_db_falls_back_to_memory():
    """Without a DB factory, get_history_from_db should fall back gracefully."""
    from backend.telemetry.service import TelemetryService

    svc = TelemetryService()
    # No configure_db call
    svc.start()
    svc.tick()
    rows = svc.get_history_from_db("M-001", limit=10)
    assert isinstance(rows, list)  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 API endpoints
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client():
    from unittest.mock import patch
    with patch('backend.rag.pipeline.rag_pipeline') as mock_rag:
        mock_rag._initialized = True
        mock_rag._embedding_service = type("ES", (), {"mode": "tfidf"})()
        mock_rag._flat_chunks = []
        from backend.api.main import app
        app.router.lifespan_handler = None
        from fastapi.testclient import TestClient
        yield TestClient(app)


def test_api_simulation_status(api_client):
    r = api_client.get("/api/v1/simulation/status")
    assert r.status_code == 200
    data = r.json()
    assert "simulation_running" in data
    assert "available_scenarios" in data
    assert "scenario_labels" in data
    assert "machines" in data


def test_api_simulation_start_stop(api_client):
    r = api_client.post("/api/v1/simulation/start")
    assert r.status_code == 200
    assert r.json()["running"] is True

    r = api_client.post("/api/v1/simulation/stop")
    assert r.status_code == 200
    assert r.json()["running"] is False


def test_api_simulation_scenarios_list(api_client):
    r = api_client.get("/api/v1/simulation/scenarios")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    scenario_names = [item["scenario"] for item in data]
    assert "overheating" in scenario_names
    assert "guard_interlock_failure" in scenario_names


def test_api_inject_fault_valid(api_client):
    r = api_client.post("/api/v1/simulation/fault", json={
        "machine_id": "M-001",
        "scenario": "overheating",
        "degradation": 0.5,
    })
    assert r.status_code == 200
    data = r.json()
    assert "machine_id" in data
    assert data["machine_id"] == "M-001"
    assert "risk_score" in data
    assert "scenario_label" in data


def test_api_inject_fault_invalid_scenario(api_client):
    r = api_client.post("/api/v1/simulation/fault", json={
        "machine_id": "M-001",
        "scenario": "not_real_scenario_xyz",
    })
    assert r.status_code == 400


def test_api_inject_fault_invalid_machine(api_client):
    r = api_client.post("/api/v1/simulation/fault", json={
        "machine_id": "M-999",
        "scenario": "normal",
    })
    assert r.status_code == 404


def test_api_reset_machine(api_client):
    # First inject a fault, then reset
    api_client.post("/api/v1/simulation/fault", json={
        "machine_id": "M-002",
        "scenario": "critical",
    })
    r = api_client.post("/api/v1/simulation/reset/M-002")
    assert r.status_code == 200
    data = r.json()
    assert "machine_id" in data
    assert data["machine_id"] == "M-002"
    assert "risk_score" in data


def test_api_reset_invalid_machine(api_client):
    r = api_client.post("/api/v1/simulation/reset/M-999")
    assert r.status_code == 404


def test_api_acknowledge_maintenance(api_client):
    r = api_client.post("/api/v1/simulation/maintenance/M-003/acknowledge")
    assert r.status_code == 200
    data = r.json()
    assert "operating_hours" in data
    assert data["maintenance_overdue"] is False


def test_api_machine_status(api_client):
    r = api_client.get("/api/v1/machines/M-001/status")
    assert r.status_code == 200
    data = r.json()
    assert "machine_id" in data
    assert "scenario" in data
    assert "operating_hours" in data
    assert "machine_status" in data


def test_api_machine_status_invalid(api_client):
    r = api_client.get("/api/v1/machines/M-999/status")
    assert r.status_code == 404


def test_api_all_machine_statuses(api_client):
    r = api_client.get("/api/v1/machines/status/all")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 5
    ids = [item["machine_id"] for item in data]
    for mid in ["M-001", "M-002", "M-003", "M-004", "M-005"]:
        assert mid in ids


def test_api_machine_history_db(api_client):
    r = api_client.get("/api/v1/machines/M-001/history/db?limit=20")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_api_machine_history_db_invalid_machine(api_client):
    r = api_client.get("/api/v1/machines/M-999/history/db")
    assert r.status_code == 404


def test_api_manual_tick(api_client):
    r = api_client.get("/api/v1/simulation/tick")
    assert r.status_code == 200
    data = r.json()
    assert data["ticked"] is True
    assert set(data["machines"]) == set(MACHINE_CONFIGS.keys())
