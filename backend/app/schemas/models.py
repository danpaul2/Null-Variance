"""
Pydantic v2 schemas for the NAWI OIML R-76 application.

All request/response models are defined here. Field names are aligned
with the expected future PostgreSQL/SQLAlchemy column names so the
in-memory repository can be swapped out transparently.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, EmailStr


# ------------------------------------------------------------------ #
# Enums                                                               #
# ------------------------------------------------------------------ #

class UserRole(str, Enum):
    INSPECTOR = "INSPECTOR"
    REVIEWER = "REVIEWER"
    ADMIN = "ADMIN"


class AccuracyClass(str, Enum):
    CLASS_I = "CLASS_I"
    CLASS_II = "CLASS_II"
    CLASS_III = "CLASS_III"
    CLASS_IIII = "CLASS_IIII"


class SessionStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ComplianceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"


# ------------------------------------------------------------------ #
# Auth                                                                #
# ------------------------------------------------------------------ #

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    username: str


class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: UserRole = UserRole.INSPECTOR


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool = True


# ------------------------------------------------------------------ #
# Instruments                                                         #
# ------------------------------------------------------------------ #

class InstrumentCreate(BaseModel):
    manufacturer: str
    model: str
    serial_number: Optional[str] = None
    accuracy_class: AccuracyClass = AccuracyClass.CLASS_III
    max_capacity: float = Field(gt=0, description="Maximum capacity in kg")
    e_value: float = Field(gt=0, description="Verification scale interval (e) in kg")
    d_value: Optional[float] = Field(
        default=None, ge=0,
        description="Actual scale interval (d) in kg, defaults to e_value"
    )
    owner: str = ""
    location: str = ""
    category: Optional[str] = None


class InstrumentOut(BaseModel):
    id: str
    manufacturer: str
    model: str
    serial_number: Optional[str] = None
    accuracy_class: AccuracyClass
    max_capacity: float
    e_value: float
    d_value: Optional[float] = None
    owner: str = ""
    location: str = ""
    category: Optional[str] = None


# ------------------------------------------------------------------ #
# Test Readings (sub-models embedded in TestSession)                  #
# ------------------------------------------------------------------ #

class EccentricityRow(BaseModel):
    id: str
    label: str
    indication: str = ""


class EccentricityData(BaseModel):
    test_load: str = ""
    rows: list[EccentricityRow] = []


class RepeatabilityRow(BaseModel):
    id: str
    label: str
    indication: str = ""


class RepeatabilityData(BaseModel):
    test_load: str = ""
    rows: list[RepeatabilityRow] = []


class DiscriminationData(BaseModel):
    test_load: str = ""
    reading_before: str = ""
    increment: str = ""
    reading_after: str = ""


class LinearityRow(BaseModel):
    id: str
    label: str
    applied_load: str = ""
    indication: str = ""


class LinearityData(BaseModel):
    rows: list[LinearityRow] = []


class AttachmentOut(BaseModel):
    id: str
    file_name: str
    file_size: str = ""
    mime_type: Optional[str] = None


# ------------------------------------------------------------------ #
# Test Session                                                        #
# ------------------------------------------------------------------ #

class TestSessionCreate(BaseModel):
    instrument_id: str
    tester: str
    test_date: str
    lab_location: str = ""
    temperature: str = ""
    humidity: str = ""


class TestSessionUpdate(BaseModel):
    """Partial update payload for saving test observations."""
    eccentricity: Optional[EccentricityData] = None
    repeatability: Optional[RepeatabilityData] = None
    discrimination: Optional[DiscriminationData] = None
    linearity: Optional[LinearityData] = None


class TestSessionOut(BaseModel):
    id: str
    instrument_id: str
    tester: str
    test_date: str
    lab_location: str
    temperature: str
    humidity: str
    status: SessionStatus
    rejection_reason: Optional[str] = None
    eccentricity: EccentricityData
    repeatability: RepeatabilityData
    discrimination: DiscriminationData
    linearity: LinearityData
    attachments: list[AttachmentOut] = []


class RejectRequest(BaseModel):
    rejection_reason: str = Field(
        min_length=1,
        description="Reason for rejecting the test session"
    )


# ------------------------------------------------------------------ #
# Compliance Results                                                  #
# ------------------------------------------------------------------ #

class ReadingResult(BaseModel):
    id: str
    label: str
    applied_load: Optional[float] = None
    indication: Optional[float] = None
    error: Optional[float] = None
    mpe: Optional[float] = None
    status: ComplianceStatus = ComplianceStatus.PENDING


class EccentricityResult(BaseModel):
    rows: list[ReadingResult] = []
    status: ComplianceStatus = ComplianceStatus.PENDING


class RepeatabilityResult(BaseModel):
    range_value: Optional[float] = None
    mpe: Optional[float] = None
    status: ComplianceStatus = ComplianceStatus.PENDING


class DiscriminationResult(BaseModel):
    delta: Optional[float] = None
    expected_min: Optional[float] = None
    status: ComplianceStatus = ComplianceStatus.PENDING


class LinearityResult(BaseModel):
    rows: list[ReadingResult] = []
    status: ComplianceStatus = ComplianceStatus.PENDING


class ComplianceResult(BaseModel):
    eccentricity: EccentricityResult = EccentricityResult()
    repeatability: RepeatabilityResult = RepeatabilityResult()
    discrimination: DiscriminationResult = DiscriminationResult()
    linearity: LinearityResult = LinearityResult()
    overall: ComplianceStatus = ComplianceStatus.PENDING


# ------------------------------------------------------------------ #
# Activity Log                                                        #
# ------------------------------------------------------------------ #

class ActivityLogEntry(BaseModel):
    time: str
    text: str
    user: Optional[str] = None
