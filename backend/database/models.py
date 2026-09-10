"""
SAFEGUARD AI - Database Models
SQLAlchemy ORM models for all application data.
"""
from datetime import datetime, timezone
from typing import Optional
import enum

from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, Text,
    ForeignKey, Enum, JSON, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class MachineStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    WARNING = "warning"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceStatus(str, enum.Enum):
    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    UNKNOWN = "unknown"


class AlertSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    machine_type = Column(String(50), nullable=False)
    location = Column(String(100))
    manufacturer = Column(String(100))
    model_number = Column(String(100))
    installation_date = Column(DateTime)
    last_maintenance = Column(DateTime)
    next_maintenance_due = Column(DateTime)
    status = Column(Enum(MachineStatus), default=MachineStatus.OPERATIONAL)
    is_active = Column(Boolean, default=True)
    config = Column(JSON)  # thresholds and machine-specific config
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    readings = relationship("MachineReading", back_populates="machine", cascade="all, delete-orphan")
    risk_events = relationship("RiskEvent", back_populates="machine", cascade="all, delete-orphan")
    compliance_checks = relationship("ComplianceCheck", back_populates="machine", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="machine", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="machine", cascade="all, delete-orphan")
    maintenance_records = relationship("MaintenanceRecord", back_populates="machine", cascade="all, delete-orphan")


class MachineReading(Base):
    __tablename__ = "machine_readings"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(String(50), ForeignKey("machines.machine_id"), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Telemetry fields
    temperature = Column(Float)         # °C
    vibration = Column(Float)           # mm/s RMS
    rpm = Column(Float)                 # rotations per minute
    pressure = Column(Float)            # bar
    load = Column(Float)                # % of rated load
    current = Column(Float)             # Amperes
    voltage = Column(Float)             # Volts
    power_consumption = Column(Float)   # kW

    # Safety status
    guard_status = Column(Boolean, default=True)    # True = guard in place
    interlock_active = Column(Boolean, default=True)
    emergency_stop = Column(Boolean, default=False)
    door_locked = Column(Boolean, default=True)

    # Calculated
    risk_score = Column(Float, default=0.0)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.LOW)
    anomaly_detected = Column(Boolean, default=False)
    anomaly_score = Column(Float, default=0.0)

    # Simulation metadata
    is_simulated = Column(Boolean, default=True)
    simulation_scenario = Column(String(50))  # normal, degrading, anomaly, etc.

    machine = relationship("Machine", back_populates="readings")

    __table_args__ = (
        Index("ix_machine_readings_machine_ts", "machine_id", "timestamp"),
    )


class SafetyDocument(Base):
    __tablename__ = "safety_documents"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(100), unique=True, nullable=False)
    title = Column(String(300), nullable=False)
    document_type = Column(String(50))   # standard, regulation, manual, guideline
    source = Column(String(200))         # ISO 13849, OSHA 1910, etc.
    file_path = Column(String(500))
    file_type = Column(String(20))       # pdf, txt, docx
    machine_categories = Column(JSON)    # list of applicable machine types
    topics = Column(JSON)                # list of topics covered
    version = Column(String(50))
    effective_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    chunk_count = Column(Integer, default=0)
    indexed_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(100), ForeignKey("safety_documents.doc_id"), nullable=False)
    chunk_id = Column(String(150), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    section = Column(String(200))
    topic = Column(String(200))
    topics = Column(JSON)                    # list of topics for this chunk
    machine_categories = Column(JSON)        # applicable machine types
    char_count = Column(Integer, default=0)  # character count of content
    page_number = Column(Integer)
    embedding_vector_id = Column(String(200))  # ID in the vector store
    extra_metadata = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("SafetyDocument", back_populates="chunks")


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(String(50), ForeignKey("machines.machine_id"), nullable=False)
    check_id = Column(String(100), unique=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    requirement = Column(Text, nullable=False)
    current_condition = Column(Text)
    expected_condition = Column(Text)
    status = Column(Enum(ComplianceStatus), nullable=False)
    risk_level = Column(Enum(RiskLevel))
    evidence = Column(JSON)             # list of retrieved evidence chunks
    source = Column(String(200))
    explanation = Column(Text)
    evidence_type = Column(String(50))  # verified, inferred, prediction, unknown
    standard_reference = Column(String(200))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    machine = relationship("Machine", back_populates="compliance_checks")


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(String(50), ForeignKey("machines.machine_id"), nullable=False)
    event_id = Column(String(100), unique=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    risk_score = Column(Float, nullable=False)
    previous_risk_score = Column(Float)
    risk_level = Column(Enum(RiskLevel), nullable=False)
    risk_factors = Column(JSON)     # list of {factor, contribution, value, threshold}
    trend = Column(String(20))      # increasing, decreasing, stable
    is_prediction = Column(Boolean, default=False)
    prediction_horizon_hours = Column(Float)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)

    machine = relationship("Machine", back_populates="risk_events")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String(100), unique=True, nullable=False)
    machine_id = Column(String(50), ForeignKey("machines.machine_id"), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    severity = Column(Enum(AlertSeverity), nullable=False)
    category = Column(String(100))   # temperature, vibration, guard, compliance, etc.
    title = Column(String(300), nullable=False)
    message = Column(Text, nullable=False)
    risk_score = Column(Float)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(100))
    acknowledged_at = Column(DateTime)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    related_reading_id = Column(Integer)
    alert_metadata = Column(JSON)

    machine = relationship("Machine", back_populates="alerts")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    rec_id = Column(String(100), unique=True, nullable=False)
    machine_id = Column(String(50), ForeignKey("machines.machine_id"), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    issue = Column(Text, nullable=False)
    severity = Column(Enum(RiskLevel), nullable=False)
    immediate_action = Column(Text)
    corrective_action = Column(Text)
    preventive_action = Column(Text)
    priority = Column(Integer)          # 1 = highest
    reason = Column(Text)
    supporting_evidence = Column(JSON)  # RAG evidence chunks
    is_ai_generated = Column(Boolean, default=True)
    status = Column(String(50), default="open")  # open, in_progress, resolved
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    machine = relationship("Machine", back_populates="recommendations")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(String(100), unique=True, nullable=False)
    machine_id = Column(String(50), ForeignKey("machines.machine_id"), nullable=False)
    performed_at = Column(DateTime, nullable=False)
    maintenance_type = Column(String(100))   # preventive, corrective, emergency
    description = Column(Text)
    performed_by = Column(String(100))
    parts_replaced = Column(JSON)
    cost = Column(Float)
    duration_hours = Column(Float)
    next_scheduled = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    machine = relationship("Machine", back_populates="maintenance_records")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(100), unique=True, nullable=False)
    machine_id = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    severity = Column(Enum(AlertSeverity), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    root_cause = Column(Text)
    contributing_factors = Column(JSON)
    injury_occurred = Column(Boolean, default=False)
    property_damage = Column(Boolean, default=False)
    corrective_actions_taken = Column(JSON)
    preventive_measures = Column(JSON)
    status = Column(String(50), default="open")  # open, investigating, closed
    closed_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
