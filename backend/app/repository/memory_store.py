from datetime import datetime
import uuid
from typing import Dict, List, Optional
import bcrypt

from app.schemas.models import (
    InstrumentOut, TestSessionOut, UserOut, UserRole, ActivityLogEntry, AttachmentOut,
    InstrumentCreate, TestSessionCreate, TestSessionUpdate, SessionStatus, AccuracyClass,
    EccentricityData, EccentricityRow, RepeatabilityData, RepeatabilityRow,
    DiscriminationData, LinearityData, LinearityRow
)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

class MemoryStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MemoryStore, cls).__new__(cls)
            cls._instance._init_store()
        return cls._instance

    def _init_store(self):
        self.users: Dict[str, dict] = {}
        self.instruments: Dict[str, InstrumentOut] = {}
        self.sessions: Dict[str, TestSessionOut] = {}
        self.activity_log: List[ActivityLogEntry] = []
        self.attachments: Dict[str, List[AttachmentOut]] = {}

        # 1. Seed Users
        self.create_user({
            "email": "mehta@lab.in",
            "full_name": "R. Mehta",
            "password": "password123",
            "role": UserRole.INSPECTOR
        })
        self.create_user({
            "email": "verma@lab.in",
            "full_name": "K. Verma",
            "password": "password123",
            "role": UserRole.REVIEWER
        })
        self.create_user({
            "email": "darshanreddy1906@gmail.com",
            "full_name": "Darshan Reddy",
            "password": "password123",
            "role": UserRole.INSPECTOR
        })

        # 2. Seed Instruments (including Class I, Class II, Class III)
        instruments_data = [
            InstrumentOut(
                id="INST-0001",
                manufacturer="Essae Digitronics",
                model="ED-II 30",
                serial_number="ED2-94821",
                accuracy_class=AccuracyClass.CLASS_III,
                max_capacity=30.0,
                e_value=0.01,
                d_value=0.01,
                owner="Sunrise Traders",
                location="Whitefield, Bengaluru",
                category="Class III - Retail"
            ),
            InstrumentOut(
                id="INST-0002",
                manufacturer="Avery India",
                model="AK-500",
                serial_number="AV-44810",
                accuracy_class=AccuracyClass.CLASS_III,
                max_capacity=500.0,
                e_value=0.1,
                d_value=0.1,
                owner="Karnataka Foods Pvt Ltd",
                location="Peenya Industrial Area",
                category="Class III - Industrial"
            ),
            InstrumentOut(
                id="INST-0003",
                manufacturer="Mettler-Toledo",
                model="XPR-2002",
                serial_number="MT-88192",
                accuracy_class=AccuracyClass.CLASS_II,
                max_capacity=2.0,
                e_value=0.0001,
                d_value=0.0001,
                owner="BioAnalytics Lab",
                location="Electronic City",
                category="Class II - Laboratory"
            ),
            InstrumentOut(
                id="INST-0004",
                manufacturer="Sartorius",
                model="Cubis II Micro",
                serial_number="SAR-10023",
                accuracy_class=AccuracyClass.CLASS_I,
                max_capacity=0.0021,
                e_value=0.000001,
                d_value=0.000001,
                owner="Precision Nanotech R&D",
                location="Cleanroom 1, Bengaluru",
                category="Class I - Special (Precision / Analytical)"
            ),
            InstrumentOut(
                id="INST-0005",
                manufacturer="Contech Instruments",
                model="CT-Pro 60",
                serial_number="CT-55190",
                accuracy_class=AccuracyClass.CLASS_III,
                max_capacity=60.0,
                e_value=0.02,
                d_value=0.02,
                owner="Metro Supermarket",
                location="Indiranagar",
                category="Class III - Retail"
            ),
            InstrumentOut(
                id="INST-0006",
                manufacturer="Aczet Pvt Ltd",
                model="ACZ-220",
                serial_number="ACZ-77123",
                accuracy_class=AccuracyClass.CLASS_III,
                max_capacity=220.0,
                e_value=0.05,
                d_value=0.05,
                owner="Green Valley Mart",
                location="HSR Layout",
                category="Class III - Retail"
            ),
        ]
        for inst in instruments_data:
            self.instruments[inst.id] = inst
        self._instrument_counter = len(instruments_data)

        # 3. Seed Sessions with complete observation data
        s1 = TestSessionOut(
            id="TS-2026-0001",
            instrument_id="INST-0001",
            tester="R. Mehta",
            test_date="2026-08-20",
            lab_location="CMRIT Metrology Lab, Bengaluru",
            temperature="26",
            humidity="52",
            status=SessionStatus.APPROVED,
            eccentricity=EccentricityData(
                test_load="15",
                rows=[
                    EccentricityRow(id="center", label="Center", indication="15"),
                    EccentricityRow(id="frontLeft", label="Front-Left", indication="15"),
                    EccentricityRow(id="frontRight", label="Front-Right", indication="15"),
                    EccentricityRow(id="rearLeft", label="Rear-Left", indication="15"),
                    EccentricityRow(id="rearRight", label="Rear-Right", indication="15"),
                ]
            ),
            repeatability=RepeatabilityData(
                test_load="15",
                rows=[
                    RepeatabilityRow(id="t1", label="Trial 1", indication="15"),
                    RepeatabilityRow(id="t2", label="Trial 2", indication="15"),
                    RepeatabilityRow(id="t3", label="Trial 3", indication="15"),
                ]
            ),
            discrimination=DiscriminationData(test_load="15", reading_before="15.00", increment="0.02", reading_after="15.02"),
            linearity=LinearityData(
                rows=[
                    LinearityRow(id="p10", label="10% of Max", applied_load="3", indication="3"),
                    LinearityRow(id="p25", label="25% of Max", applied_load="7.5", indication="7.5"),
                    LinearityRow(id="p50", label="50% of Max", applied_load="15", indication="15"),
                    LinearityRow(id="p75", label="75% of Max", applied_load="22.5", indication="22.5"),
                    LinearityRow(id="p100", label="100% of Max", applied_load="30", indication="30"),
                ]
            ),
            attachments=[
                AttachmentOut(id="a1", file_name="nameplate_photo.jpg", file_size="842 KB"),
                AttachmentOut(id="a2", file_name="calibration_certificate.pdf", file_size="1.1 MB"),
            ]
        )

        s2 = TestSessionOut(
            id="TS-2026-0002",
            instrument_id="INST-0002",
            tester="S. Iyer",
            test_date="2026-08-25",
            lab_location="Peenya Site Lab",
            temperature="29",
            humidity="48",
            status=SessionStatus.REJECTED,
            rejection_reason="Eccentricity error exceeded allowable MPE threshold on Front-Left quadrant.",
            eccentricity=EccentricityData(
                test_load="250",
                rows=[
                    EccentricityRow(id="center", label="Center", indication="250"),
                    EccentricityRow(id="frontLeft", label="Front-Left", indication="255"),
                    EccentricityRow(id="frontRight", label="Front-Right", indication="250"),
                    EccentricityRow(id="rearLeft", label="Rear-Left", indication="250"),
                    EccentricityRow(id="rearRight", label="Rear-Right", indication="250"),
                ]
            ),
            repeatability=RepeatabilityData(
                test_load="250",
                rows=[
                    RepeatabilityRow(id="t1", label="Trial 1", indication="250"),
                    RepeatabilityRow(id="t2", label="Trial 2", indication="250"),
                    RepeatabilityRow(id="t3", label="Trial 3", indication="250"),
                ]
            ),
            discrimination=DiscriminationData(test_load="250", reading_before="250.00", increment="0.15", reading_after="250.15"),
            linearity=LinearityData(
                rows=[
                    LinearityRow(id="p10", label="10% of Max", applied_load="50", indication="50"),
                    LinearityRow(id="p25", label="25% of Max", applied_load="125", indication="125"),
                    LinearityRow(id="p50", label="50% of Max", applied_load="250", indication="250"),
                    LinearityRow(id="p75", label="75% of Max", applied_load="375", indication="375"),
                    LinearityRow(id="p100", label="100% of Max", applied_load="500", indication="500"),
                ]
            ),
            attachments=[]
        )

        s3 = TestSessionOut(
            id="TS-2026-0003",
            instrument_id="INST-0003",
            tester="A. Sharma",
            test_date="2026-08-28",
            lab_location="Electronic City Cleanroom",
            temperature="22",
            humidity="40",
            status=SessionStatus.PENDING_REVIEW,
            eccentricity=EccentricityData(
                test_load="1",
                rows=[
                    EccentricityRow(id="center", label="Center", indication="1"),
                    EccentricityRow(id="frontLeft", label="Front-Left", indication="1"),
                    EccentricityRow(id="frontRight", label="Front-Right", indication="1"),
                    EccentricityRow(id="rearLeft", label="Rear-Left", indication="1"),
                    EccentricityRow(id="rearRight", label="Rear-Right", indication="1"),
                ]
            ),
            repeatability=RepeatabilityData(
                test_load="1",
                rows=[
                    RepeatabilityRow(id="t1", label="Trial 1", indication="1"),
                    RepeatabilityRow(id="t2", label="Trial 2", indication="1"),
                    RepeatabilityRow(id="t3", label="Trial 3", indication="1"),
                ]
            ),
            discrimination=DiscriminationData(test_load="1", reading_before="1.0000", increment="0.00015", reading_after="1.00015"),
            linearity=LinearityData(
                rows=[
                    LinearityRow(id="p10", label="10% of Max", applied_load="0.2", indication="0.2"),
                    LinearityRow(id="p25", label="25% of Max", applied_load="0.5", indication="0.5"),
                    LinearityRow(id="p50", label="50% of Max", applied_load="1", indication="1"),
                    LinearityRow(id="p75", label="75% of Max", applied_load="1.5", indication="1.5"),
                    LinearityRow(id="p100", label="100% of Max", applied_load="2", indication="2"),
                ]
            ),
            attachments=[AttachmentOut(id="a3", file_name="lab_certificate.pdf", file_size="480 KB")]
        )

        s4 = TestSessionOut(
            id="TS-2026-0004",
            instrument_id="INST-0004",
            tester="P. Nair",
            test_date="2026-09-01",
            lab_location="Cleanroom Metrology Suite",
            temperature="20",
            humidity="38",
            status=SessionStatus.PENDING_REVIEW,
            eccentricity=EccentricityData(
                test_load="0.001",
                rows=[
                    EccentricityRow(id="center", label="Center", indication="0.001000"),
                    EccentricityRow(id="frontLeft", label="Front-Left", indication="0.001000"),
                    EccentricityRow(id="frontRight", label="Front-Right", indication="0.001000"),
                    EccentricityRow(id="rearLeft", label="Rear-Left", indication="0.001000"),
                    EccentricityRow(id="rearRight", label="Rear-Right", indication="0.001000"),
                ]
            ),
            repeatability=RepeatabilityData(
                test_load="0.001",
                rows=[
                    RepeatabilityRow(id="t1", label="Trial 1", indication="0.001000"),
                    RepeatabilityRow(id="t2", label="Trial 2", indication="0.001000"),
                    RepeatabilityRow(id="t3", label="Trial 3", indication="0.001000"),
                ]
            ),
            discrimination=DiscriminationData(test_load="0.001", reading_before="0.001000", increment="0.000002", reading_after="0.001002"),
            linearity=LinearityData(
                rows=[
                    LinearityRow(id="p10", label="10% of Max", applied_load="0.0002", indication="0.000200"),
                    LinearityRow(id="p25", label="25% of Max", applied_load="0.0005", indication="0.000500"),
                    LinearityRow(id="p50", label="50% of Max", applied_load="0.001", indication="0.001000"),
                    LinearityRow(id="p75", label="75% of Max", applied_load="0.0015", indication="0.001500"),
                    LinearityRow(id="p100", label="100% of Max", applied_load="0.002", indication="0.002000"),
                ]
            ),
            attachments=[]
        )

        s5 = TestSessionOut(
            id="TS-2026-0005",
            instrument_id="INST-0005",
            tester="R. Mehta",
            test_date="2026-09-03",
            lab_location="Indiranagar Site Lab",
            temperature="28",
            humidity="50",
            status=SessionStatus.DRAFT,
            eccentricity=EccentricityData(
                test_load="30",
                rows=[
                    EccentricityRow(id="center", label="Center", indication="30"),
                    EccentricityRow(id="frontLeft", label="Front-Left", indication=""),
                    EccentricityRow(id="frontRight", label="Front-Right", indication=""),
                    EccentricityRow(id="rearLeft", label="Rear-Left", indication=""),
                    EccentricityRow(id="rearRight", label="Rear-Right", indication=""),
                ]
            ),
            repeatability=RepeatabilityData(
                test_load="",
                rows=[
                    RepeatabilityRow(id="t1", label="Trial 1", indication=""),
                    RepeatabilityRow(id="t2", label="Trial 2", indication=""),
                    RepeatabilityRow(id="t3", label="Trial 3", indication=""),
                ]
            ),
            discrimination=DiscriminationData(test_load="", reading_before="", increment="", reading_after=""),
            linearity=LinearityData(
                rows=[
                    LinearityRow(id="p10", label="10% of Max", applied_load="", indication=""),
                    LinearityRow(id="p25", label="25% of Max", applied_load="", indication=""),
                    LinearityRow(id="p50", label="50% of Max", applied_load="", indication=""),
                    LinearityRow(id="p75", label="75% of Max", applied_load="", indication=""),
                    LinearityRow(id="p100", label="100% of Max", applied_load="", indication=""),
                ]
            ),
            attachments=[]
        )

        for s in [s1, s2, s3, s4, s5]:
            self.sessions[s.id] = s
        self._session_counter = 5

        # 4. Seed Activity Log
        self.activity_log = [
            ActivityLogEntry(time="Just now", text="System initialized with OIML R-76 metrology test suite", user="System"),
            ActivityLogEntry(time="03 Sep 2026", text="R. Mehta started a new test session for INST-0005", user="R. Mehta"),
            ActivityLogEntry(time="01 Sep 2026", text="P. Nair submitted test session TS-2026-0004 for review", user="P. Nair"),
            ActivityLogEntry(time="29 Aug 2026", text="Reviewer rejected test session TS-2026-0002", user="K. Verma"),
            ActivityLogEntry(time="28 Aug 2026", text="A. Sharma submitted test session TS-2026-0003 for review", user="A. Sharma"),
            ActivityLogEntry(time="25 Aug 2026", text="S. Iyer completed test session TS-2026-0002", user="S. Iyer"),
            ActivityLogEntry(time="21 Aug 2026", text="Reviewer approved test session TS-2026-0001", user="K. Verma"),
        ]

    def next_instrument_id(self) -> str:
        self._instrument_counter += 1
        return f"INST-{self._instrument_counter:04d}"

    def next_session_id(self) -> str:
        self._session_counter += 1
        return f"TS-2026-{self._session_counter:04d}"

    def get_user_by_email(self, email: str) -> Optional[dict]:
        return self.users.get(email)

    def create_user(self, data: dict) -> UserOut:
        hashed_password = hash_password(data["password"])
        user_id = str(uuid.uuid4())
        user_dict = {
            "id": user_id,
            "email": data["email"],
            "full_name": data["full_name"],
            "role": data["role"],
            "is_active": True,
            "hashed_password": hashed_password
        }
        self.users[data["email"]] = user_dict
        return UserOut(**user_dict)

    def get_instruments(self) -> List[InstrumentOut]:
        return list(self.instruments.values())

    def search_instruments(self, query: str) -> List[InstrumentOut]:
        query = query.lower()
        return [inst for inst in self.instruments.values() 
                if query in inst.manufacturer.lower() or query in inst.model.lower() or (inst.serial_number and query in inst.serial_number.lower())]

    def get_instrument_by_id(self, id: str) -> Optional[InstrumentOut]:
        return self.instruments.get(id)

    def create_instrument(self, data: InstrumentCreate) -> InstrumentOut:
        inst_id = self.next_instrument_id()
        inst = InstrumentOut(
            id=inst_id,
            **data.model_dump()
        )
        self.instruments[inst_id] = inst
        return inst

    def get_sessions(self) -> List[TestSessionOut]:
        return list(self.sessions.values())

    def get_session_by_id(self, id: str) -> Optional[TestSessionOut]:
        return self.sessions.get(id)

    def get_sessions_by_instrument(self, instrument_id: str) -> List[TestSessionOut]:
        return [s for s in self.sessions.values() if s.instrument_id == instrument_id]

    def get_sessions_by_status(self, status: SessionStatus) -> List[TestSessionOut]:
        return [s for s in self.sessions.values() if s.status == status]

    def create_session(self, data: TestSessionCreate) -> TestSessionOut:
        sess_id = self.next_session_id()
        
        # Build empty positions
        ecc_rows = [
            EccentricityRow(id=pid, label=lbl) 
            for pid, lbl in [("center", "Center"), ("frontLeft", "Front-Left"), 
                             ("frontRight", "Front-Right"), ("rearLeft", "Rear-Left"), 
                             ("rearRight", "Rear-Right")]
        ]
        rep_rows = [
            RepeatabilityRow(id=tid, label=lbl)
            for tid, lbl in [("t1", "Trial 1"), ("t2", "Trial 2"), ("t3", "Trial 3")]
        ]
        lin_rows = [
            LinearityRow(id=pid, label=lbl)
            for pid, lbl in [("p10", "10% of Max"), ("p25", "25% of Max"), 
                             ("p50", "50% of Max"), ("p75", "75% of Max"), 
                             ("p100", "100% of Max")]
        ]

        sess = TestSessionOut(
            id=sess_id,
            instrument_id=data.instrument_id,
            tester=data.tester,
            test_date=data.test_date,
            lab_location=data.lab_location,
            temperature=data.temperature,
            humidity=data.humidity,
            status=SessionStatus.DRAFT,
            eccentricity=EccentricityData(rows=ecc_rows),
            repeatability=RepeatabilityData(rows=rep_rows),
            discrimination=DiscriminationData(),
            linearity=LinearityData(rows=lin_rows),
            attachments=[]
        )
        self.sessions[sess_id] = sess
        return sess

    def update_session(self, id: str, data: TestSessionUpdate) -> Optional[TestSessionOut]:
        sess = self.sessions.get(id)
        if not sess:
            return None
            
        sess_dict = sess.model_dump()
        if data.eccentricity is not None:
            sess_dict["eccentricity"] = data.eccentricity.model_dump()
        if data.repeatability is not None:
            sess_dict["repeatability"] = data.repeatability.model_dump()
        if data.discrimination is not None:
            sess_dict["discrimination"] = data.discrimination.model_dump()
        if data.linearity is not None:
            sess_dict["linearity"] = data.linearity.model_dump()
            
        updated_sess = TestSessionOut(**sess_dict)
        self.sessions[id] = updated_sess
        return updated_sess

    def add_activity(self, text: str, user: str = None):
        self.activity_log.insert(0, ActivityLogEntry(
            time=datetime.now().strftime("%d %b %Y %H:%M"),
            text=text,
            user=user
        ))

    def get_activity_log(self, limit: int = 20) -> List[ActivityLogEntry]:
        return self.activity_log[:limit]

    def add_attachment(self, session_id: str, file_name: str, file_size: str, mime_type: str) -> AttachmentOut:
        att = AttachmentOut(
            id=str(uuid.uuid4()),
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type
        )
        if session_id not in self.attachments:
            self.attachments[session_id] = []
        self.attachments[session_id].append(att)
        
        # also update the session's attachments list
        if session_id in self.sessions:
            self.sessions[session_id].attachments.append(att)
            
        return att

    def get_attachments_by_session(self, session_id: str) -> List[AttachmentOut]:
        return self.attachments.get(session_id, [])

store = MemoryStore()
