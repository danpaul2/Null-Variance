from sqlalchemy import (
    Column, String, Float, Boolean, Text, DateTime,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.database import Base
from app.schemas.models import UserRole, AccuracyClass, SessionStatus

def gen_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SAEnum(UserRole, name="userrole_enum"), nullable=False, default=UserRole.INSPECTOR)
    is_active = Column(Boolean, default=True, nullable=False)

class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(String, primary_key=True)
    manufacturer = Column(String, nullable=False)
    model = Column(String, nullable=False)
    serial_number = Column(String, nullable=True)
    accuracy_class = Column(SAEnum(AccuracyClass, name="accuracyclass_enum"), nullable=False)
    max_capacity = Column(Float, nullable=False)
    e_value = Column(Float, nullable=False)
    d_value = Column(Float, nullable=True)
    owner = Column(String, default="")
    location = Column(String, default="")
    category = Column(String, nullable=True)

    sessions = relationship("TestSession", back_populates="instrument")

class TestSession(Base):
    __tablename__ = "test_sessions"

    id = Column(String, primary_key=True)
    instrument_id = Column(String, ForeignKey("instruments.id"), nullable=False, index=True)
    tester = Column(String, nullable=False)
    test_date = Column(String, nullable=False)
    lab_location = Column(String, default="")
    temperature = Column(String, default="")
    humidity = Column(String, default="")
    status = Column(SAEnum(SessionStatus, name="sessionstatus_enum"), nullable=False, default=SessionStatus.DRAFT)
    rejection_reason = Column(Text, nullable=True)

    eccentricity_data = Column(JSON, nullable=True, default=dict)
    repeatability_data = Column(JSON, nullable=True, default=dict)
    discrimination_data = Column(JSON, nullable=True, default=dict)
    linearity_data = Column(JSON, nullable=True, default=dict)

    instrument = relationship("Instrument", back_populates="sessions")
    attachments = relationship("Attachment", back_populates="session", cascade="all, delete-orphan")

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("test_sessions.id"), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    file_size = Column(String, default="")
    mime_type = Column(String, nullable=True)

    session = relationship("TestSession", back_populates="attachments")

class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(String, primary_key=True, default=gen_uuid)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    text = Column(Text, nullable=False)
    user_name = Column(String, nullable=True)
