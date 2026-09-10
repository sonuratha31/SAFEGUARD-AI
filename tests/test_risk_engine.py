"""
SAFEGUARD AI - Tests for Risk Engine
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from backend.risk_engine.engine import RiskEngine, score_to_level


@pytest.fixture
def engine():
    return RiskEngine()


def test_score_to_level():
    assert score_to_level(0) == "low"
    assert score_to_level(20) == "low"
    assert score_to_level(21) == "moderate"
    assert score_to_level(40) == "moderate"
    assert score_to_level(41) == "elevated"
    assert score_to_level(60) == "elevated"
    assert score_to_level(61) == "high"
    assert score_to_level(80) == "high"
    assert score_to_level(81) == "critical"
    assert score_to_level(100) == "critical"


def test_normal_operation_zero_risk(engine):
    """Normal operation should produce zero or near-zero risk."""
    result = engine.assess(
        machine_id="M-001",
        temperature=42.0,
        vibration=1.8,
        rpm=3500.0,
        pressure=55.0,
        load=60.0,
        guard_status=True,
        interlock_active=True,
        emergency_stop=False,
        door_locked=True,
        maintenance_overdue=False,
    )
    assert result.risk_score == 0.0
    assert result.risk_level == "low"
    assert len(result.risk_factors) == 0


def test_high_temperature_adds_risk(engine):
    """Temperature above threshold should add risk points."""
    result = engine.assess(
        machine_id="M-001",
        temperature=85.0,  # above 75°C safe max
        vibration=1.8,
        rpm=3500.0,
        pressure=55.0,
        load=60.0,
        guard_status=True,
        interlock_active=True,
        emergency_stop=False,
        door_locked=True,
    )
    assert result.risk_score > 0
    temp_factors = [f for f in result.risk_factors if f.category == "temperature"]
    assert len(temp_factors) == 1
    assert temp_factors[0].contribution > 0


def test_guard_open_is_critical(engine):
    """Open guard should add 10 pts and trigger high/critical risk."""
    result = engine.assess(
        machine_id="M-001",
        temperature=42.0,
        vibration=1.8,
        rpm=3500.0,
        pressure=55.0,
        load=60.0,
        guard_status=False,  # Guard open
        interlock_active=True,
        emergency_stop=False,
        door_locked=True,
    )
    guard_factors = [f for f in result.risk_factors if f.category == "guard"]
    assert len(guard_factors) == 1
    assert guard_factors[0].contribution == 10.0
    assert result.risk_score >= 10.0


def test_emergency_stop_adds_max_contribution(engine):
    """E-stop should add 20 pts."""
    result = engine.assess(
        machine_id="M-001",
        temperature=42.0,
        vibration=1.8,
        rpm=3500.0,
        pressure=55.0,
        load=60.0,
        guard_status=True,
        interlock_active=True,
        emergency_stop=True,
        door_locked=True,
    )
    estop_factors = [f for f in result.risk_factors if f.category == "emergency_stop"]
    assert len(estop_factors) == 1
    assert estop_factors[0].contribution == 20.0


def test_multiple_factors_accumulate(engine):
    """Multiple risk factors should accumulate."""
    result = engine.assess(
        machine_id="M-001",
        temperature=88.0,   # above threshold
        vibration=6.0,       # above threshold
        rpm=3500.0,
        pressure=55.0,
        load=60.0,
        guard_status=False,  # guard open
        interlock_active=False,  # interlock inactive
        emergency_stop=False,
        door_locked=True,
        maintenance_overdue=True,
    )
    assert result.risk_score > 40
    assert len(result.risk_factors) >= 4


def test_risk_score_capped_at_100(engine):
    """Risk score should never exceed 100."""
    result = engine.assess(
        machine_id="M-001",
        temperature=200.0,
        vibration=20.0,
        rpm=15000.0,
        pressure=500.0,
        load=150.0,
        guard_status=False,
        interlock_active=False,
        emergency_stop=True,
        door_locked=False,
        maintenance_overdue=True,
    )
    assert result.risk_score <= 100.0


def test_whatif_uses_real_engine(engine):
    """What-If should use the real engine, not random values."""
    # Same inputs should produce same outputs
    result1 = engine.assess_whatif("M-001", {"temperature": 80.0, "guard_status": False})
    result2 = engine.assess_whatif("M-001", {"temperature": 80.0, "guard_status": False})
    assert result1.risk_score == result2.risk_score


def test_explanation_contains_machine_id(engine):
    """Risk explanation should mention the machine."""
    result = engine.assess(
        machine_id="M-002",
        temperature=45.0,
        vibration=2.5,
        rpm=900.0,
        pressure=180.0,
        load=70.0,
        guard_status=True,
        interlock_active=True,
        emergency_stop=False,
        door_locked=True,
    )
    assert "M-002" in result.explanation
