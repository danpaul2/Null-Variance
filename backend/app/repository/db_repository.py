"""
app/repository/db_repository.py
--------------------------------
Database-backed repository. Drop-in replacement for MemoryStore.
Uses SQLAlchemy session injected via FastAPI dependency injection.
Public interface is identical to MemoryStore so all routes need
only a one-word rename: get_store -> get_db.
"""

import uuid
from datetime import datetime
from typing import List, Optional

import bcrypt
from sqlalchemy.orm import Session

from app.db import models as m
from app.schemas.models import (
    InstrumentOut, InstrumentCreate,
    TestSessionOut, TestSessionCreate, TestSessionUpdate,
    AttachmentOut, ActivityLogEntry, UserOut, UserRole,
    SessionStatus, AccuracyClass,
    EccentricityData, RepeatabilityData, DiscriminationData, LinearityData,
    EccentricityRow, RepeatabilityRow, LinearityRow
)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── helpers to convert ORM rows → Pydantic ──────────────────────────────────

def _inst_to_schema(row: m.Instrument) -> InstrumentOut:
    return InstrumentOut(
        id=row.id, manufacturer=row.manufacturer, model=row.model,
        serial_number=row.serial_number,
        accuracy_class=row.accuracy_class,
        max_capacity=row.max_capacity, e_value=row.e_value, d_value=row.d_value,
        owner=row.owner or "", location=row.location or "",
        category=row.category,
    )


def _ecc_from_json(data: dict) -> EccentricityData:
    if not data:
        return EccentricityData()
    return EccentricityData(
        test_load=data.get("test_load", ""),
        rows=[EccentricityRow(**r) for r in data.get("rows", [])]
    )


def _rep_from_json(data: dict) -> RepeatabilityData:
    if not data:
        return RepeatabilityData()
    return RepeatabilityData(
        test_load=data.get("test_load", ""),
        rows=[RepeatabilityRow(**r) for r in data.get("rows", [])]
    )


def _disc_from_json(data: dict) -> DiscriminationData:
    if not data:
        return DiscriminationData()
    return DiscriminationData(**{k: data.get(k, "") for k in ["test_load", "reading_before", "increment", "reading_after"]})


def _lin_from_json(data: dict) -> LinearityData:
    if not data:
        return LinearityData()
    return LinearityData(rows=[LinearityRow(**r) for r in data.get("rows", [])])


def _att_to_schema(row: m.Attachment) -> AttachmentOut:
    return AttachmentOut(id=row.id, file_name=row.file_name, file_size=row.file_size or "", mime_type=row.mime_type)


def _sess_to_schema(row: m.TestSession) -> TestSessionOut:
    attachments = [_att_to_schema(a) for a in (row.attachments or [])]
    return TestSessionOut(
        id=row.id, instrument_id=row.instrument_id,
        tester=row.tester, test_date=row.test_date,
        lab_location=row.lab_location or "",
        temperature=row.temperature or "",
        humidity=row.humidity or "",
        status=row.status,
        rejection_reason=row.rejection_reason,
        eccentricity=_ecc_from_json(row.eccentricity_data or {}),
        repeatability=_rep_from_json(row.repeatability_data or {}),
        discrimination=_disc_from_json(row.discrimination_data or {}),
        linearity=_lin_from_json(row.linearity_data or {}),
        attachments=attachments,
    )


# ── Repository class ─────────────────────────────────────────────────────────

class DBRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Users ────────────────────────────────────────────────────────────────

    def get_user_by_email(self, email: str) -> Optional[dict]:
        row = self.db.query(m.User).filter(m.User.email == email).first()
        if not row:
            return None
        return {
            "id": row.id, "email": row.email, "full_name": row.full_name,
            "role": row.role, "is_active": row.is_active,
            "hashed_password": row.hashed_password,
        }

    def create_user(self, data: dict) -> UserOut:
        hashed = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
        row = m.User(
            id=str(uuid.uuid4()),
            email=data["email"],
            full_name=data["full_name"],
            hashed_password=hashed,
            role=data["role"],
            is_active=True,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return UserOut(id=row.id, email=row.email, full_name=row.full_name, role=row.role, is_active=row.is_active)

    # ── Instruments ──────────────────────────────────────────────────────────

    def get_instruments(self) -> List[InstrumentOut]:
        rows = self.db.query(m.Instrument).order_by(m.Instrument.id).all()
        return [_inst_to_schema(r) for r in rows]

    def search_instruments(self, query: str) -> List[InstrumentOut]:
        q = f"%{query.lower()}%"
        rows = self.db.query(m.Instrument).filter(
            m.Instrument.manufacturer.ilike(q) |
            m.Instrument.model.ilike(q) |
            m.Instrument.serial_number.ilike(q)
        ).all()
        return [_inst_to_schema(r) for r in rows]

    def get_instrument_by_id(self, id: str) -> Optional[InstrumentOut]:
        row = self.db.query(m.Instrument).filter(m.Instrument.id == id).first()
        return _inst_to_schema(row) if row else None

    def create_instrument(self, data: InstrumentCreate) -> InstrumentOut:
        # Determine next ID
        count = self.db.query(m.Instrument).count()
        new_id = f"INST-{count + 1:04d}"
        # Ensure uniqueness
        while self.db.query(m.Instrument).filter(m.Instrument.id == new_id).first():
            count += 1
            new_id = f"INST-{count + 1:04d}"

        row = m.Instrument(id=new_id, **data.model_dump())
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _inst_to_schema(row)

    # ── Test Sessions ────────────────────────────────────────────────────────

    def get_sessions(self) -> List[TestSessionOut]:
        rows = self.db.query(m.TestSession).order_by(m.TestSession.id).all()
        return [_sess_to_schema(r) for r in rows]

    def get_session_by_id(self, id: str) -> Optional[TestSessionOut]:
        row = self.db.query(m.TestSession).filter(m.TestSession.id == id).first()
        return _sess_to_schema(row) if row else None

    def get_sessions_by_instrument(self, instrument_id: str) -> List[TestSessionOut]:
        rows = self.db.query(m.TestSession).filter(m.TestSession.instrument_id == instrument_id).all()
        return [_sess_to_schema(r) for r in rows]

    def get_sessions_by_status(self, status: SessionStatus) -> List[TestSessionOut]:
        rows = self.db.query(m.TestSession).filter(m.TestSession.status == status).all()
        return [_sess_to_schema(r) for r in rows]

    def create_session(self, data: TestSessionCreate) -> TestSessionOut:
        count = self.db.query(m.TestSession).count()
        new_id = f"TS-{datetime.now().year}-{count + 1:04d}"
        while self.db.query(m.TestSession).filter(m.TestSession.id == new_id).first():
            count += 1
            new_id = f"TS-{datetime.now().year}-{count + 1:04d}"

        default_ecc = {"test_load": "", "rows": [
            {"id": "center",     "label": "Center",      "indication": ""},
            {"id": "frontLeft",  "label": "Front-Left",  "indication": ""},
            {"id": "frontRight", "label": "Front-Right", "indication": ""},
            {"id": "rearLeft",   "label": "Rear-Left",   "indication": ""},
            {"id": "rearRight",  "label": "Rear-Right",  "indication": ""},
        ]}
        default_rep = {"test_load": "", "rows": [
            {"id": "t1", "label": "Trial 1", "indication": ""},
            {"id": "t2", "label": "Trial 2", "indication": ""},
            {"id": "t3", "label": "Trial 3", "indication": ""},
        ]}
        default_lin = {"rows": [
            {"id": "p10",  "label": "10% of Max",  "applied_load": "", "indication": ""},
            {"id": "p25",  "label": "25% of Max",  "applied_load": "", "indication": ""},
            {"id": "p50",  "label": "50% of Max",  "applied_load": "", "indication": ""},
            {"id": "p75",  "label": "75% of Max",  "applied_load": "", "indication": ""},
            {"id": "p100", "label": "100% of Max", "applied_load": "", "indication": ""},
        ]}

        row = m.TestSession(
            id=new_id,
            instrument_id=data.instrument_id,
            tester=data.tester,
            test_date=data.test_date,
            lab_location=data.lab_location,
            temperature=data.temperature,
            humidity=data.humidity,
            status=SessionStatus.DRAFT,
            eccentricity_data=default_ecc,
            repeatability_data=default_rep,
            discrimination_data={"test_load": "", "reading_before": "", "increment": "", "reading_after": ""},
            linearity_data=default_lin,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _sess_to_schema(row)

    def update_session(self, id: str, data: TestSessionUpdate) -> Optional[TestSessionOut]:
        row = self.db.query(m.TestSession).filter(m.TestSession.id == id).first()
        if not row:
            return None
        if data.eccentricity is not None:
            row.eccentricity_data = data.eccentricity.model_dump()
        if data.repeatability is not None:
            row.repeatability_data = data.repeatability.model_dump()
        if data.discrimination is not None:
            row.discrimination_data = data.discrimination.model_dump()
        if data.linearity is not None:
            row.linearity_data = data.linearity.model_dump()
        self.db.commit()
        self.db.refresh(row)
        return _sess_to_schema(row)

    def set_session_status(self, id: str, status: SessionStatus, reason: str = None) -> Optional[TestSessionOut]:
        row = self.db.query(m.TestSession).filter(m.TestSession.id == id).first()
        if not row:
            return None
        row.status = status
        if reason is not None:
            row.rejection_reason = reason
        self.db.commit()
        self.db.refresh(row)
        return _sess_to_schema(row)

    # ── Activity Log ─────────────────────────────────────────────────────────

    def add_activity(self, text: str, user: str = None):
        log = m.ActivityLog(id=str(uuid.uuid4()), text=text, user_name=user, created_at=datetime.utcnow())
        self.db.add(log)
        self.db.commit()

    def get_activity_log(self, limit: int = 20) -> List[ActivityLogEntry]:
        rows = self.db.query(m.ActivityLog).order_by(m.ActivityLog.created_at.desc()).limit(limit).all()
        results = []
        for row in rows:
            ts = row.created_at
            now = datetime.utcnow()
            diff = now - ts
            if diff.total_seconds() < 120:
                time_str = "Just now"
            elif diff.days == 0:
                h = int(diff.total_seconds() // 3600)
                time_str = f"{h}h ago"
            else:
                time_str = ts.strftime("%d %b %Y")
            results.append(ActivityLogEntry(time=time_str, text=row.text, user=row.user_name))
        return results

    # ── Attachments ──────────────────────────────────────────────────────────

    def add_attachment(self, session_id: str, file_name: str, file_size: str, mime_type: str) -> AttachmentOut:
        row = m.Attachment(
            id=str(uuid.uuid4()),
            session_id=session_id,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _att_to_schema(row)

    def get_attachments_by_session(self, session_id: str) -> List[AttachmentOut]:
        rows = self.db.query(m.Attachment).filter(m.Attachment.session_id == session_id).all()
        return [_att_to_schema(r) for r in rows]

    def delete_attachment(self, attachment_id: str) -> bool:
        row = self.db.query(m.Attachment).filter(m.Attachment.id == attachment_id).first()
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
