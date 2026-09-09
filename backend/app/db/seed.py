"""
app/db/seed.py
--------------
Seeds demo instruments, users, sessions, and activity log into
PostgreSQL on first startup (only runs when tables are empty).
"""

import uuid
from datetime import datetime

import bcrypt

from app.db.models import User, Instrument, TestSession, ActivityLog
from app.schemas.models import UserRole, AccuracyClass, SessionStatus


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _default_ecc(load: str):
    return {
        "test_load": load,
        "rows": [
            {"id": "center",     "label": "Center",      "indication": load},
            {"id": "frontLeft",  "label": "Front-Left",  "indication": load},
            {"id": "frontRight", "label": "Front-Right", "indication": load},
            {"id": "rearLeft",   "label": "Rear-Left",   "indication": load},
            {"id": "rearRight",  "label": "Rear-Right",  "indication": load},
        ]
    }


def _default_rep(load: str):
    return {
        "test_load": load,
        "rows": [
            {"id": "t1", "label": "Trial 1", "indication": load},
            {"id": "t2", "label": "Trial 2", "indication": load},
            {"id": "t3", "label": "Trial 3", "indication": load},
        ]
    }


def _default_lin(points):
    return {
        "rows": [
            {"id": p[0], "label": p[1], "applied_load": p[2], "indication": p[2]}
            for p in points
        ]
    }


def seed_database(db):
    """Seed demo data. Called at startup; skips if data already exists."""
    if db.query(User).count() > 0:
        return  # already seeded

    print("Seeding database with demo data...")

    # Users
    users = [
        User(id=str(uuid.uuid4()), email="mehta@lab.in",   full_name="R. Mehta",      hashed_password=_hash("password123"), role=UserRole.INSPECTOR),
        User(id=str(uuid.uuid4()), email="verma@lab.in",   full_name="K. Verma",      hashed_password=_hash("password123"), role=UserRole.REVIEWER),
        User(id=str(uuid.uuid4()), email="darshanreddy1906@gmail.com", full_name="Darshan Reddy", hashed_password=_hash("password123"), role=UserRole.INSPECTOR),
    ]
    db.add_all(users)

    # Instruments
    instruments = [
        Instrument(id="INST-0001", manufacturer="Essae Digitronics",  model="ED-II 30",       serial_number="ED2-94821",  accuracy_class=AccuracyClass.CLASS_III, max_capacity=30.0,    e_value=0.01,     d_value=0.01,     owner="Sunrise Traders",          location="Whitefield, Bengaluru", category="Class III - Retail"),
        Instrument(id="INST-0002", manufacturer="Avery India",         model="AK-500",         serial_number="AV-44810",   accuracy_class=AccuracyClass.CLASS_III, max_capacity=500.0,   e_value=0.1,      d_value=0.1,      owner="Karnataka Foods Pvt Ltd",  location="Peenya Industrial Area", category="Class III - Industrial"),
        Instrument(id="INST-0003", manufacturer="Mettler-Toledo",      model="XPR-2002",       serial_number="MT-88192",   accuracy_class=AccuracyClass.CLASS_II,  max_capacity=2.0,     e_value=0.0001,   d_value=0.0001,   owner="BioAnalytics Lab",         location="Electronic City", category="Class II - Laboratory"),
        Instrument(id="INST-0004", manufacturer="Sartorius",           model="Cubis II Micro", serial_number="SAR-10023",  accuracy_class=AccuracyClass.CLASS_I,   max_capacity=0.0021,  e_value=0.000001, d_value=0.000001, owner="Precision Nanotech R&D",  location="Cleanroom 1, Bengaluru", category="Class I - Special (Precision / Analytical)"),
        Instrument(id="INST-0005", manufacturer="Contech Instruments", model="CT-Pro 60",      serial_number="CT-55190",   accuracy_class=AccuracyClass.CLASS_III, max_capacity=60.0,    e_value=0.02,     d_value=0.02,     owner="Metro Supermarket",        location="Indiranagar", category="Class III - Retail"),
        Instrument(id="INST-0006", manufacturer="Aczet Pvt Ltd",       model="ACZ-220",        serial_number="ACZ-77123",  accuracy_class=AccuracyClass.CLASS_III, max_capacity=220.0,   e_value=0.05,     d_value=0.05,     owner="Green Valley Mart",        location="HSR Layout", category="Class III - Retail"),
    ]
    db.add_all(instruments)

    # Sessions
    sessions = [
        TestSession(
            id="TS-2026-0001", instrument_id="INST-0001", tester="R. Mehta",
            test_date="2026-08-20", lab_location="CMRIT Metrology Lab, Bengaluru",
            temperature="26", humidity="52", status=SessionStatus.APPROVED,
            eccentricity_data=_default_ecc("15"),
            repeatability_data=_default_rep("15"),
            discrimination_data={"test_load":"15","reading_before":"15.00","increment":"0.02","reading_after":"15.02"},
            linearity_data=_default_lin([("p10","10% of Max","3"),("p25","25% of Max","7.5"),("p50","50% of Max","15"),("p75","75% of Max","22.5"),("p100","100% of Max","30")]),
        ),
        TestSession(
            id="TS-2026-0002", instrument_id="INST-0002", tester="S. Iyer",
            test_date="2026-08-25", lab_location="Peenya Site Lab",
            temperature="29", humidity="48", status=SessionStatus.REJECTED,
            rejection_reason="Eccentricity error exceeded allowable MPE threshold on Front-Left quadrant.",
            eccentricity_data={
                "test_load": "250",
                "rows": [
                    {"id":"center","label":"Center","indication":"250"},
                    {"id":"frontLeft","label":"Front-Left","indication":"255"},
                    {"id":"frontRight","label":"Front-Right","indication":"250"},
                    {"id":"rearLeft","label":"Rear-Left","indication":"250"},
                    {"id":"rearRight","label":"Rear-Right","indication":"250"},
                ]
            },
            repeatability_data=_default_rep("250"),
            discrimination_data={"test_load":"250","reading_before":"250.00","increment":"0.15","reading_after":"250.15"},
            linearity_data=_default_lin([("p10","10% of Max","50"),("p25","25% of Max","125"),("p50","50% of Max","250"),("p75","75% of Max","375"),("p100","100% of Max","500")]),
        ),
        TestSession(
            id="TS-2026-0003", instrument_id="INST-0003", tester="A. Sharma",
            test_date="2026-08-28", lab_location="Electronic City Cleanroom",
            temperature="22", humidity="40", status=SessionStatus.PENDING_REVIEW,
            eccentricity_data=_default_ecc("1"),
            repeatability_data=_default_rep("1"),
            discrimination_data={"test_load":"1","reading_before":"1.0000","increment":"0.00015","reading_after":"1.00015"},
            linearity_data=_default_lin([("p10","10% of Max","0.2"),("p25","25% of Max","0.5"),("p50","50% of Max","1"),("p75","75% of Max","1.5"),("p100","100% of Max","2")]),
        ),
        TestSession(
            id="TS-2026-0004", instrument_id="INST-0004", tester="P. Nair",
            test_date="2026-09-01", lab_location="Cleanroom Metrology Suite",
            temperature="20", humidity="38", status=SessionStatus.PENDING_REVIEW,
            eccentricity_data=_default_ecc("0.001"),
            repeatability_data=_default_rep("0.001"),
            discrimination_data={"test_load":"0.001","reading_before":"0.001000","increment":"0.000002","reading_after":"0.001002"},
            linearity_data=_default_lin([("p10","10% of Max","0.0002"),("p25","25% of Max","0.0005"),("p50","50% of Max","0.001"),("p75","75% of Max","0.0015"),("p100","100% of Max","0.002")]),
        ),
        TestSession(
            id="TS-2026-0005", instrument_id="INST-0005", tester="R. Mehta",
            test_date="2026-09-03", lab_location="Indiranagar Site Lab",
            temperature="28", humidity="50", status=SessionStatus.DRAFT,
            eccentricity_data={"test_load":"30","rows":[{"id":"center","label":"Center","indication":"30"},{"id":"frontLeft","label":"Front-Left","indication":""},{"id":"frontRight","label":"Front-Right","indication":""},{"id":"rearLeft","label":"Rear-Left","indication":""},{"id":"rearRight","label":"Rear-Right","indication":""}]},
            repeatability_data={"test_load":"","rows":[{"id":"t1","label":"Trial 1","indication":""},{"id":"t2","label":"Trial 2","indication":""},{"id":"t3","label":"Trial 3","indication":""}]},
            discrimination_data={"test_load":"","reading_before":"","increment":"","reading_after":""},
            linearity_data={"rows":[{"id":"p10","label":"10% of Max","applied_load":"","indication":""},{"id":"p25","label":"25% of Max","applied_load":"","indication":""},{"id":"p50","label":"50% of Max","applied_load":"","indication":""},{"id":"p75","label":"75% of Max","applied_load":"","indication":""},{"id":"p100","label":"100% of Max","applied_load":"","indication":""}]},
        ),
    ]
    db.add_all(sessions)

    # Activity log
    logs = [
        ActivityLog(text="System initialized with OIML R-76 metrology test suite", user_name="System", created_at=datetime(2026, 9, 9, 0, 0, 0)),
        ActivityLog(text="R. Mehta started a new test session for INST-0005",       user_name="R. Mehta", created_at=datetime(2026, 9, 3)),
        ActivityLog(text="P. Nair submitted test session TS-2026-0004 for review",  user_name="P. Nair",  created_at=datetime(2026, 9, 1)),
        ActivityLog(text="Reviewer rejected test session TS-2026-0002",              user_name="K. Verma", created_at=datetime(2026, 8, 29)),
        ActivityLog(text="A. Sharma submitted test session TS-2026-0003 for review",user_name="A. Sharma",created_at=datetime(2026, 8, 28)),
        ActivityLog(text="S. Iyer completed test session TS-2026-0002",              user_name="S. Iyer",  created_at=datetime(2026, 8, 25)),
        ActivityLog(text="Reviewer approved test session TS-2026-0001",              user_name="K. Verma", created_at=datetime(2026, 8, 21)),
    ]
    db.add_all(logs)

    db.commit()
    print("Database seeded successfully.")
