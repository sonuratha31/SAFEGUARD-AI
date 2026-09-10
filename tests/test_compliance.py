"""
SAFEGUARD AI - Tests for Compliance Engine
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from backend.compliance.engine import ComplianceEngine, _check_guard, _check_temperature
from backend.rag.pipeline import rag_pipeline


@pytest.fixture
def engine():
    return ComplianceEngine()


def test_guard_compliant(engine):
    results = engine.run_compliance_check(
        machine_id="M-001",
        machine_type="cnc_machine",
        temperature=42.0,
        vibration=1.8,
        pressure=55.0,
        guard_status=True,
        interlock_active=True,
        emergency_stop=False,
        maintenance_overdue=False,
    )
    guard_check = next((r for r in results if "guard" in r.requirement.lower()), None)
    assert guard_check is not None
    assert guard_check.status == "compliant"
    assert guard_check.risk_level == "low"


def test_guard_non_compliant(engine):
    results = engine.run_compliance_check(
        machine_id="M-001",
        machine_type="cnc_machine",
        temperature=42.0,
        vibration=1.8,
        pressure=55.0,
        guard_status=False,  # open
        interlock_active=True,
        emergency_stop=False,
        maintenance_overdue=False,
    )
    guard_check = next((r for r in results if "guard" in r.requirement.lower()), None)
    assert guard_check is not None
    assert guard_check.status == "non_compliant"
    assert guard_check.risk_level == "critical"


def test_temperature_compliance_zones(engine):
    # Normal → compliant
    results = engine.run_compliance_check(
        machine_id="M-001", machine_type="cnc_machine",
        temperature=60.0, vibration=1.8, pressure=55.0,
        guard_status=True, interlock_active=True,
        emergency_stop=False, maintenance_overdue=False,
    )
    temp_check = next((r for r in results if "temperature" in r.requirement.lower()), None)
    assert temp_check is not None
    assert temp_check.status == "compliant"

    # Above safe max → partial or non-compliant
    results2 = engine.run_compliance_check(
        machine_id="M-001", machine_type="cnc_machine",
        temperature=82.0, vibration=1.8, pressure=55.0,  # above 75°C safe max
        guard_status=True, interlock_active=True,
        emergency_stop=False, maintenance_overdue=False,
    )
    temp_check2 = next((r for r in results2 if "temperature" in r.requirement.lower()), None)
    assert temp_check2 is not None
    assert temp_check2.status in ("partially_compliant", "non_compliant")


def test_overall_status_with_non_compliant(engine):
    results = engine.run_compliance_check(
        machine_id="M-001", machine_type="cnc_machine",
        temperature=42.0, vibration=1.8, pressure=55.0,
        guard_status=False, interlock_active=True,
        emergency_stop=False, maintenance_overdue=False,
    )
    overall = engine.overall_status(results)
    assert overall == "non_compliant"


def test_compliance_score_all_compliant(engine):
    results = engine.run_compliance_check(
        machine_id="M-001", machine_type="cnc_machine",
        temperature=42.0, vibration=1.8, pressure=55.0,
        guard_status=True, interlock_active=True,
        emergency_stop=False, maintenance_overdue=False,
    )
    score = engine.compliance_score(results)
    # Score should be high (all green except possibly some inferred)
    assert score >= 70.0


def test_maintenance_overdue_non_compliant(engine):
    results = engine.run_compliance_check(
        machine_id="M-001", machine_type="cnc_machine",
        temperature=42.0, vibration=1.8, pressure=55.0,
        guard_status=True, interlock_active=True,
        emergency_stop=False, maintenance_overdue=True,
    )
    maint_check = next((r for r in results if "maintenance" in r.requirement.lower()), None)
    assert maint_check is not None
    assert maint_check.status == "non_compliant"
