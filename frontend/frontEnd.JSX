import { useState, useMemo, useEffect, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import API from "./src/api/client";

/* ---------------------------------------------------------------------- */
/* Constants                                                               */
/* ---------------------------------------------------------------------- */

const ECCENTRICITY_POSITIONS = [
  { id: "center", label: "Center" },
  { id: "frontLeft", label: "Front-Left" },
  { id: "frontRight", label: "Front-Right" },
  { id: "rearLeft", label: "Rear-Left" },
  { id: "rearRight", label: "Rear-Right" },
];

const REPEATABILITY_TRIALS = [
  { id: "t1", label: "Trial 1" },
  { id: "t2", label: "Trial 2" },
  { id: "t3", label: "Trial 3" },
];

const LINEARITY_POINTS = [
  { id: "p10", label: "10% of Max" },
  { id: "p25", label: "25% of Max" },
  { id: "p50", label: "50% of Max" },
  { id: "p75", label: "75% of Max" },
  { id: "p100", label: "100% of Max" },
];

/* ---------------------------------------------------------------------- */
/* Calculation helpers                                                    */
/* ---------------------------------------------------------------------- */

function computeMPE(load, e, accuracyClass = "CLASS_III") {
  const l = parseFloat(load);
  const eVal = parseFloat(e);
  if (isNaN(l) || isNaN(eVal) || eVal <= 0) return null;
  const m = l / eVal; // number of verification scale intervals (m = L / e)

  const cls = (accuracyClass || "CLASS_III").toUpperCase();
  let multiplier = 0.5;

  if (cls.includes("CLASS_I") && !cls.includes("CLASS_II")) {
    // Class I (Special): 0 to 50000 -> 0.5e, 50000 to 200000 -> 1.0e, > 200000 -> 1.5e
    if (m > 200000) multiplier = 1.5;
    else if (m > 50000) multiplier = 1.0;
  } else if (cls.includes("CLASS_II") && !cls.includes("CLASS_III")) {
    // Class II (High): 0 to 5000 -> 0.5e, 5000 to 20000 -> 1.0e, > 20000 -> 1.5e
    if (m > 20000) multiplier = 1.5;
    else if (m > 5000) multiplier = 1.0;
  } else if (cls.includes("CLASS_IIII")) {
    // Class IIII (Ordinary): 0 to 50 -> 0.5e, 50 to 200 -> 1.0e, > 200 -> 1.5e
    if (m > 200) multiplier = 1.5;
    else if (m > 50) multiplier = 1.0;
  } else {
    // Class III (Medium): 0 to 500 -> 0.5e, 500 to 2000 -> 1.0e, > 2000 -> 1.5e
    if (m > 2000) multiplier = 1.5;
    else if (m > 500) multiplier = 1.0;
  }

  return eVal * multiplier;
}

function computeReading(load, indication, e, accuracyClass = "CLASS_III") {
  const l = parseFloat(load);
  const i = parseFloat(indication);
  const hasL = !isNaN(l);
  const hasI = !isNaN(i);
  let error = null;
  if (hasL && hasI) error = i - l;
  const mpe = hasL ? computeMPE(load, e, accuracyClass) : null;
  let status = "PENDING";
  if (error !== null && mpe !== null) status = Math.abs(error) <= mpe ? "PASS" : "FAIL";
  return { error, mpe, status };
}

function aggregateStatus(statuses) {
  if (statuses.length === 0) return "PENDING";
  if (statuses.includes("FAIL")) return "FAIL";
  if (statuses.includes("PENDING")) return "PENDING";
  return "PASS";
}

function getSessionCompliance(session, instrument) {
  const e = instrument ? (instrument.eValue ?? instrument.e_value) : null;
  let accClass = "CLASS_III";
  if (instrument) {
    if (instrument.accuracyClass) accClass = instrument.accuracyClass;
    else if (instrument.accuracy_class) accClass = instrument.accuracy_class;
    else if (instrument.category) {
      if (instrument.category.includes("Class I") && !instrument.category.includes("Class II")) accClass = "CLASS_I";
      else if (instrument.category.includes("Class II") && !instrument.category.includes("Class III")) accClass = "CLASS_II";
      else if (instrument.category.includes("Class IIII")) accClass = "CLASS_IIII";
    }
  }

  const eccRows = session.eccentricity.rows.map((r) => ({
    ...r,
    appliedLoad: session.eccentricity.testLoad,
    ...computeReading(session.eccentricity.testLoad, r.indication, e, accClass),
  }));
  const eccStatus = aggregateStatus(eccRows.map((r) => r.status));

  const repIndications = session.repeatability.rows.map((r) => parseFloat(r.indication));
  const repFilled = repIndications.length > 0 && repIndications.every((v) => !isNaN(v));
  let repRange = null;
  let repMpe = null;
  let repStatus = "PENDING";
  if (repFilled) {
    repRange = Math.max(...repIndications) - Math.min(...repIndications);
    repMpe = computeMPE(session.repeatability.testLoad, e, accClass);
    if (repMpe !== null) repStatus = repRange <= repMpe ? "PASS" : "FAIL";
  }

  const disc = session.discrimination;
  const discBefore = parseFloat(disc.readingBefore);
  const discAfter = parseFloat(disc.readingAfter);
  const discIncrement = parseFloat(disc.increment);
  let discDelta = null;
  let discExpectedMin = null;
  let discStatus = "PENDING";
  if (!isNaN(discBefore) && !isNaN(discAfter) && !isNaN(discIncrement)) {
    discDelta = discAfter - discBefore;
    discExpectedMin = discIncrement * 0.5;
    discStatus = discDelta >= discExpectedMin ? "PASS" : "FAIL";
  }

  const linRows = session.linearity.rows.map((r) => ({
    ...r,
    ...computeReading(r.appliedLoad, r.indication, e, accClass),
  }));
  const linStatus = aggregateStatus(linRows.map((r) => r.status));

  const overall = aggregateStatus([eccStatus, repStatus, discStatus, linStatus]);

  return {
    eccentricity: { rows: eccRows, status: eccStatus },
    repeatability: { range: repRange, mpe: repMpe, status: repStatus },
    discrimination: { delta: discDelta, expectedMin: discExpectedMin, status: discStatus },
    linearity: { rows: linRows, status: linStatus },
    overall,
  };
}

function buildBlankTestData() {
  return {
    eccentricity: { testLoad: "", rows: ECCENTRICITY_POSITIONS.map((p) => ({ id: p.id, label: p.label, indication: "" })) },
    repeatability: { testLoad: "", rows: REPEATABILITY_TRIALS.map((t) => ({ id: t.id, label: t.label, indication: "" })) },
    discrimination: { testLoad: "", readingBefore: "", increment: "", readingAfter: "" },
    linearity: { rows: LINEARITY_POINTS.map((p) => ({ id: p.id, label: p.label, appliedLoad: "", indication: "" })) },
    attachments: [],
  };
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ---------------------------------------------------------------------- */
/* Mock seed data                                                          */
/* ---------------------------------------------------------------------- */

const initialInstruments = [
  { id: "INST-0001", manufacturer: "Essae Digitronics", model: "ED-II 30", category: "Class III - Medium (Retail)", maxCapacity: 30, eValue: 0.01, owner: "Sunrise Traders", location: "Whitefield, Bengaluru" },
  { id: "INST-0002", manufacturer: "Avery India", model: "AK-500", category: "Class III - Medium (Industrial)", maxCapacity: 500, eValue: 0.1, owner: "Karnataka Foods Pvt Ltd", location: "Peenya Industrial Area" },
  { id: "INST-0003", manufacturer: "Mettler-Toledo", model: "XPR-2002", category: "Class II - High (Laboratory)", maxCapacity: 2, eValue: 0.0001, owner: "BioAnalytics Lab", location: "Electronic City" },
  { id: "INST-0004", manufacturer: "Sartorius", model: "Cubis II Micro", category: "Class I - Special (Precision / Analytical)", maxCapacity: 0.0021, eValue: 0.000001, owner: "Precision Nanotech R&D", location: "Cleanroom 1, Bengaluru" },
  { id: "INST-0005", manufacturer: "Contech Instruments", model: "CT-Pro 60", category: "Class III - Medium (Retail)", maxCapacity: 60, eValue: 0.02, owner: "Metro Supermarket", location: "Indiranagar" },
  { id: "INST-0006", manufacturer: "Aczet Pvt Ltd", model: "ACZ-220", category: "Class III - Medium (Retail)", maxCapacity: 220, eValue: 0.05, owner: "Green Valley Mart", location: "HSR Layout" },
];

const initialSessions = [
  {
    id: "TS-2026-0001",
    instrumentId: "INST-0001",
    tester: "R. Mehta",
    testDate: "2026-08-20",
    labLocation: "CMRIT Metrology Lab, Bengaluru",
    temp: "26",
    humidity: "52",
    status: "APPROVED",
    eccentricity: {
      testLoad: "15",
      rows: [
        { id: "center", label: "Center", indication: "15" },
        { id: "frontLeft", label: "Front-Left", indication: "15" },
        { id: "frontRight", label: "Front-Right", indication: "15" },
        { id: "rearLeft", label: "Rear-Left", indication: "15" },
        { id: "rearRight", label: "Rear-Right", indication: "15" },
      ],
    },
    repeatability: {
      testLoad: "15",
      rows: [
        { id: "t1", label: "Trial 1", indication: "15" },
        { id: "t2", label: "Trial 2", indication: "15" },
        { id: "t3", label: "Trial 3", indication: "15" },
      ],
    },
    discrimination: { testLoad: "15", readingBefore: "15.00", increment: "0.02", readingAfter: "15.02" },
    linearity: {
      rows: [
        { id: "p10", label: "10% of Max", appliedLoad: "3", indication: "3" },
        { id: "p25", label: "25% of Max", appliedLoad: "7.5", indication: "7.5" },
        { id: "p50", label: "50% of Max", appliedLoad: "15", indication: "15" },
        { id: "p75", label: "75% of Max", appliedLoad: "22.5", indication: "22.5" },
        { id: "p100", label: "100% of Max", appliedLoad: "30", indication: "30" },
      ],
    },
    attachments: [
      { id: "a1", name: "nameplate_photo.jpg", size: "842 KB" },
      { id: "a2", name: "calibration_certificate.pdf", size: "1.1 MB" },
    ],
  },
  {
    id: "TS-2026-0002",
    instrumentId: "INST-0002",
    tester: "S. Iyer",
    testDate: "2026-08-25",
    labLocation: "Peenya Site Lab",
    temp: "29",
    humidity: "48",
    status: "REJECTED",
    eccentricity: {
      testLoad: "250",
      rows: [
        { id: "center", label: "Center", indication: "250" },
        { id: "frontLeft", label: "Front-Left", indication: "255" },
        { id: "frontRight", label: "Front-Right", indication: "250" },
        { id: "rearLeft", label: "Rear-Left", indication: "250" },
        { id: "rearRight", label: "Rear-Right", indication: "250" },
      ],
    },
    repeatability: {
      testLoad: "250",
      rows: [
        { id: "t1", label: "Trial 1", indication: "250" },
        { id: "t2", label: "Trial 2", indication: "250" },
        { id: "t3", label: "Trial 3", indication: "250" },
      ],
    },
    discrimination: { testLoad: "250", readingBefore: "250.00", increment: "0.15", readingAfter: "250.15" },
    linearity: {
      rows: [
        { id: "p10", label: "10% of Max", appliedLoad: "50", indication: "50" },
        { id: "p25", label: "25% of Max", appliedLoad: "125", indication: "125" },
        { id: "p50", label: "50% of Max", appliedLoad: "250", indication: "250" },
        { id: "p75", label: "75% of Max", appliedLoad: "375", indication: "375" },
        { id: "p100", label: "100% of Max", appliedLoad: "500", indication: "500" },
      ],
    },
    attachments: [],
  },
  {
    id: "TS-2026-0003",
    instrumentId: "INST-0003",
    tester: "A. Sharma",
    testDate: "2026-08-28",
    labLocation: "Electronic City Cleanroom",
    temp: "22",
    humidity: "40",
    status: "PENDING_REVIEW",
    eccentricity: {
      testLoad: "1",
      rows: [
        { id: "center", label: "Center", indication: "1" },
        { id: "frontLeft", label: "Front-Left", indication: "1" },
        { id: "frontRight", label: "Front-Right", indication: "1" },
        { id: "rearLeft", label: "Rear-Left", indication: "1" },
        { id: "rearRight", label: "Rear-Right", indication: "1" },
      ],
    },
    repeatability: {
      testLoad: "1",
      rows: [
        { id: "t1", label: "Trial 1", indication: "1" },
        { id: "t2", label: "Trial 2", indication: "1" },
        { id: "t3", label: "Trial 3", indication: "1" },
      ],
    },
    discrimination: { testLoad: "1", readingBefore: "1.0000", increment: "0.00015", readingAfter: "1.00015" },
    linearity: {
      rows: [
        { id: "p10", label: "10% of Max", appliedLoad: "0.2", indication: "0.2" },
        { id: "p25", label: "25% of Max", appliedLoad: "0.5", indication: "0.5" },
        { id: "p50", label: "50% of Max", appliedLoad: "1", indication: "1" },
        { id: "p75", label: "75% of Max", appliedLoad: "1.5", indication: "1.5" },
        { id: "p100", label: "100% of Max", appliedLoad: "2", indication: "2" },
      ],
    },
    attachments: [{ id: "a3", name: "lab_certificate.pdf", size: "480 KB" }],
  },
  {
    id: "TS-2026-0004",
    instrumentId: "INST-0004",
    tester: "P. Nair",
    testDate: "2026-09-01",
    labLocation: "Indiranagar Store Site",
    temp: "27",
    humidity: "58",
    status: "PENDING_REVIEW",
    eccentricity: {
      testLoad: "30",
      rows: [
        { id: "center", label: "Center", indication: "30" },
        { id: "frontLeft", label: "Front-Left", indication: "30" },
        { id: "frontRight", label: "Front-Right", indication: "30" },
        { id: "rearLeft", label: "Rear-Left", indication: "30" },
        { id: "rearRight", label: "Rear-Right", indication: "30" },
      ],
    },
    repeatability: {
      testLoad: "30",
      rows: [
        { id: "t1", label: "Trial 1", indication: "30" },
        { id: "t2", label: "Trial 2", indication: "30" },
        { id: "t3", label: "Trial 3", indication: "30" },
      ],
    },
    discrimination: { testLoad: "30", readingBefore: "30.00", increment: "0.03", readingAfter: "30.03" },
    linearity: {
      rows: [
        { id: "p10", label: "10% of Max", appliedLoad: "6", indication: "6" },
        { id: "p25", label: "25% of Max", appliedLoad: "15", indication: "15" },
        { id: "p50", label: "50% of Max", appliedLoad: "30", indication: "31" },
        { id: "p75", label: "75% of Max", appliedLoad: "45", indication: "45" },
        { id: "p100", label: "100% of Max", appliedLoad: "60", indication: "60" },
      ],
    },
    attachments: [],
  },
  {
    id: "TS-2026-0005",
    instrumentId: "INST-0005",
    tester: "R. Mehta",
    testDate: "2026-09-03",
    labLocation: "HSR Layout Store Site",
    temp: "28",
    humidity: "50",
    status: "DRAFT",
    eccentricity: {
      testLoad: "110",
      rows: [
        { id: "center", label: "Center", indication: "110" },
        { id: "frontLeft", label: "Front-Left", indication: "" },
        { id: "frontRight", label: "Front-Right", indication: "" },
        { id: "rearLeft", label: "Rear-Left", indication: "" },
        { id: "rearRight", label: "Rear-Right", indication: "" },
      ],
    },
    repeatability: {
      testLoad: "",
      rows: [
        { id: "t1", label: "Trial 1", indication: "" },
        { id: "t2", label: "Trial 2", indication: "" },
        { id: "t3", label: "Trial 3", indication: "" },
      ],
    },
    discrimination: { testLoad: "", readingBefore: "", increment: "", readingAfter: "" },
    linearity: {
      rows: [
        { id: "p10", label: "10% of Max", appliedLoad: "", indication: "" },
        { id: "p25", label: "25% of Max", appliedLoad: "", indication: "" },
        { id: "p50", label: "50% of Max", appliedLoad: "", indication: "" },
        { id: "p75", label: "75% of Max", appliedLoad: "", indication: "" },
        { id: "p100", label: "100% of Max", appliedLoad: "", indication: "" },
      ],
    },
    attachments: [],
  },
  {
    id: "TS-2026-0006",
    instrumentId: "INST-0001",
    tester: "S. Iyer",
    testDate: "2026-06-15",
    labLocation: "CMRIT Metrology Lab, Bengaluru",
    temp: "25",
    humidity: "55",
    status: "APPROVED",
    eccentricity: {
      testLoad: "15",
      rows: [
        { id: "center", label: "Center", indication: "15" },
        { id: "frontLeft", label: "Front-Left", indication: "15" },
        { id: "frontRight", label: "Front-Right", indication: "15" },
        { id: "rearLeft", label: "Rear-Left", indication: "15" },
        { id: "rearRight", label: "Rear-Right", indication: "15" },
      ],
    },
    repeatability: {
      testLoad: "15",
      rows: [
        { id: "t1", label: "Trial 1", indication: "15" },
        { id: "t2", label: "Trial 2", indication: "15" },
        { id: "t3", label: "Trial 3", indication: "15" },
      ],
    },
    discrimination: { testLoad: "15", readingBefore: "15.00", increment: "0.02", readingAfter: "15.02" },
    linearity: {
      rows: [
        { id: "p10", label: "10% of Max", appliedLoad: "3", indication: "3" },
        { id: "p25", label: "25% of Max", appliedLoad: "7.5", indication: "7.5" },
        { id: "p50", label: "50% of Max", appliedLoad: "15", indication: "15" },
        { id: "p75", label: "75% of Max", appliedLoad: "22.5", indication: "22.5" },
        { id: "p100", label: "100% of Max", appliedLoad: "30", indication: "30" },
      ],
    },
    attachments: [],
  },
];

const initialActivity = [
  { time: "03 Sep 2026", text: "R. Mehta started a new test session for INST-0005" },
  { time: "01 Sep 2026", text: "P. Nair submitted test session TS-2026-0004 for review" },
  { time: "29 Aug 2026", text: "Reviewer rejected test session TS-2026-0002" },
  { time: "28 Aug 2026", text: "A. Sharma submitted test session TS-2026-0003 for review" },
  { time: "25 Aug 2026", text: "S. Iyer completed test session TS-2026-0002" },
  { time: "21 Aug 2026", text: "Reviewer approved test session TS-2026-0001" },
];

/* ---------------------------------------------------------------------- */
/* Small presentational components                                        */
/* ---------------------------------------------------------------------- */

function ComplianceBadge({ status }) {
  const cls = status === "PASS" ? "badge-pass" : status === "FAIL" ? "badge-fail" : "badge-pending";
  return <span className={`badge ${cls}`}>{status}</span>;
}

function WorkflowBadge({ status }) {
  const map = {
    DRAFT: { cls: "badge-neutral", label: "Draft" },
    PENDING_REVIEW: { cls: "badge-pending", label: "Pending Review" },
    APPROVED: { cls: "badge-pass", label: "Approved" },
    REJECTED: { cls: "badge-fail", label: "Rejected" },
  };
  const m = map[status] || { cls: "badge-neutral", label: status };
  return <span className={`badge ${m.cls}`}>{m.label}</span>;
}

function GlobalStyles() {
  return (
    <style>{`
      .nawi-dashboard * { box-sizing: border-box; }
      .nawi-dashboard {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
        color: #222;
        background: #eef1f4;
        min-height: 100vh;
      }
      .nawi-dashboard .topbar {
        background: #0d3b66;
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 16px;
        border-bottom: 3px solid #0a2e50;
        flex-wrap: wrap;
        gap: 8px;
      }
      .nawi-dashboard .topbar-left { display: flex; align-items: center; gap: 10px; }
      .nawi-dashboard .hamburger-btn {
        background: transparent; border: 1px solid rgba(255,255,255,0.4); color: #fff;
        padding: 4px 9px; border-radius: 3px; cursor: pointer; font-size: 14px;
      }
      .nawi-dashboard .topbar-title { font-size: 16px; font-weight: 600; }
      .nawi-dashboard .topbar-right { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
      .nawi-dashboard .user-indicator {
        font-size: 13px; background: rgba(255,255,255,0.12); padding: 5px 10px;
        border-radius: 3px; border: 1px solid rgba(255,255,255,0.25);
      }
      .nawi-dashboard .btn {
        padding: 7px 14px; border-radius: 3px; border: 1px solid transparent; font-size: 13px; cursor: pointer;
      }
      .nawi-dashboard .btn-primary { background: #f2a900; color: #1a1a1a; border-color: #cf9200; font-weight: 600; }
      .nawi-dashboard .btn-primary:hover { background: #e09d00; }
      .nawi-dashboard .btn-secondary { background: #fff; color: #333; border-color: #c8c8c8; }
      .nawi-dashboard .btn-secondary:hover { background: #f2f2f2; }
      .nawi-dashboard .btn-danger { background: #fff; color: #b02a2a; border-color: #e3a9a9; }
      .nawi-dashboard .btn-danger:hover { background: #fdeaea; }
      .nawi-dashboard .layout { display: flex; align-items: flex-start; position: relative; }
      .nawi-dashboard .sidebar {
        width: 200px; background: #fff; border-right: 1px solid #d7dbe0;
        min-height: calc(100vh - 53px); padding: 14px 0; flex-shrink: 0; transition: margin-left 0.15s ease;
      }
      .nawi-dashboard .sidebar.closed { margin-left: -200px; }
      .nawi-dashboard .sidebar nav { display: flex; flex-direction: column; }
      .nawi-dashboard .nav-item {
        background: none; border: none; text-align: left; padding: 9px 18px; font-size: 13px;
        color: #444; cursor: pointer; border-left: 3px solid transparent;
      }
      .nawi-dashboard .nav-item:hover { background: #f3f5f7; }
      .nawi-dashboard .nav-item.active { background: #eaf1f8; border-left-color: #0d3b66; color: #0d3b66; font-weight: 600; }
      .nawi-dashboard .main-content { flex: 1; padding: 18px 22px; min-width: 0; }
      .nawi-dashboard .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
      .nawi-dashboard .kpi-card { background: #fff; border: 1px solid #d7dbe0; border-radius: 4px; padding: 14px 16px; }
      .nawi-dashboard .kpi-value { font-size: 26px; font-weight: 700; color: #0d3b66; }
      .nawi-dashboard .kpi-label { font-size: 12.5px; color: #666; margin-top: 4px; }
      .nawi-dashboard .split-view { display: grid; grid-template-columns: 380px 1fr; gap: 16px; align-items: start; }
      .nawi-dashboard .panel { background: #fff; border: 1px solid #d7dbe0; border-radius: 4px; padding: 16px; margin-bottom: 16px; }
      .nawi-dashboard .panel-title { font-size: 15px; margin: 0 0 12px; }
      .nawi-dashboard .narrow-panel { max-width: 560px; }
      .nawi-dashboard .tabs { display: flex; border-bottom: 1px solid #d7dbe0; margin-bottom: 14px; flex-wrap: wrap; }
      .nawi-dashboard .tab-btn {
        background: none; border: none; padding: 8px 10px; font-size: 13px; color: #555;
        cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px;
      }
      .nawi-dashboard .tab-btn.active { color: #0d3b66; border-bottom-color: #0d3b66; font-weight: 600; }
      .nawi-dashboard .form-grid { display: flex; flex-direction: column; gap: 12px; }
      .nawi-dashboard .form-grid-cols { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
      .nawi-dashboard .form-group { display: flex; flex-direction: column; gap: 4px; }
      .nawi-dashboard .form-group label { font-size: 12.5px; color: #444; font-weight: 600; }
      .nawi-dashboard .form-group input, .nawi-dashboard .form-group select {
        border: 1px solid #c8c8c8; border-radius: 3px; padding: 7px 8px; font-size: 13.5px; width: 100%;
      }
      .nawi-dashboard .form-group input:focus, .nawi-dashboard .form-group select:focus { outline: 2px solid #0d3b66; outline-offset: 1px; }
      .nawi-dashboard .inline-input { max-width: 200px; margin-bottom: 12px; }
      .nawi-dashboard .cell-input { width: 100px; }
      .nawi-dashboard .status-group { flex-direction: row; align-items: center; gap: 10px; }
      .nawi-dashboard .badge { display: inline-block; padding: 3px 9px; border-radius: 3px; font-size: 12px; font-weight: 600; white-space: nowrap; }
      .nawi-dashboard .badge-pass { background: #e6f4ea; color: #1e7e34; border: 1px solid #b8dfc0; }
      .nawi-dashboard .badge-fail { background: #fdeaea; color: #b02a2a; border: 1px solid #f0bcbc; }
      .nawi-dashboard .badge-pending { background: #fff4e0; color: #a66a00; border: 1px solid #f0d69b; }
      .nawi-dashboard .badge-neutral { background: #f0f1f3; color: #555; border: 1px solid #d7dbe0; }
      .nawi-dashboard .form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; border-top: 1px solid #eee; padding-top: 12px; flex-wrap: wrap; }
      .nawi-dashboard .table-panel-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
      .nawi-dashboard .header-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
      .nawi-dashboard .search-input { border: 1px solid #c8c8c8; border-radius: 3px; padding: 6px 9px; font-size: 13px; min-width: 220px; }
      .nawi-dashboard .table-scroll { overflow-x: auto; }
      .nawi-dashboard table { width: 100%; border-collapse: collapse; font-size: 13px; }
      .nawi-dashboard th { text-align: left; background: #f5f6f8; border-bottom: 2px solid #d7dbe0; padding: 8px; font-size: 12px; color: #444; }
      .nawi-dashboard td { padding: 8px; border-bottom: 1px solid #eceef1; }
      .nawi-dashboard tbody tr:hover { background: #fafbfc; }
      .nawi-dashboard .actions-cell { display: flex; gap: 6px; white-space: nowrap; }
      .nawi-dashboard .action-btn { border: 1px solid #c8c8c8; background: #fff; border-radius: 3px; padding: 4px 8px; font-size: 12px; cursor: pointer; }
      .nawi-dashboard .action-btn:hover { background: #f2f2f2; }
      .nawi-dashboard .empty-row { text-align: center; color: #888; padding: 18px; }
      .nawi-dashboard .back-btn { margin-bottom: 12px; }
      .nawi-dashboard .inline-form { background: #f9fafb; border: 1px solid #e3e6ea; border-radius: 4px; padding: 14px; margin-bottom: 14px; }
      .nawi-dashboard .detail-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px 20px; margin-bottom: 14px; }
      .nawi-dashboard .detail-grid > div { display: flex; flex-direction: column; font-size: 13px; }
      .nawi-dashboard .detail-label { font-size: 11.5px; color: #888; }
      .nawi-dashboard .session-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
      .nawi-dashboard .session-subtitle { font-size: 12.5px; color: #666; margin: 2px 0 0; }
      .nawi-dashboard .report-badges { display: flex; gap: 8px; }
      .nawi-dashboard .tab-overall { font-size: 13px; margin-top: 12px; }
      .nawi-dashboard .file-list { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
      .nawi-dashboard .file-list li { display: flex; align-items: center; gap: 10px; font-size: 13px; border: 1px solid #e3e6ea; border-radius: 3px; padding: 6px 10px; }
      .nawi-dashboard .file-size { color: #888; font-size: 12px; margin-left: auto; }
      .nawi-dashboard .chart-wrap { border: 1px solid #e3e6ea; border-radius: 4px; padding: 8px 4px; margin-bottom: 16px; }
      .nawi-dashboard .section-heading { font-size: 13.5px; margin: 18px 0 8px; color: #333; }
      .nawi-dashboard .summary-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 16px; }
      .nawi-dashboard .summary-card { border: 1px solid #e3e6ea; border-radius: 4px; padding: 12px; }
      .nawi-dashboard .summary-card h4 { margin: 0 0 6px; font-size: 13.5px; }
      .nawi-dashboard .summary-card p { margin: 3px 0; font-size: 12.5px; color: #444; }
      .nawi-dashboard .filter-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
      .nawi-dashboard .filter-row select { border: 1px solid #c8c8c8; border-radius: 3px; padding: 6px 8px; font-size: 13px; }
      .nawi-dashboard .date-filter { font-size: 12px; color: #555; display: flex; align-items: center; gap: 4px; }
      .nawi-dashboard .date-filter input { border: 1px solid #c8c8c8; border-radius: 3px; padding: 5px 6px; font-size: 12.5px; }
      .nawi-dashboard .report-doc { max-width: 900px; }
      .nawi-dashboard .activity-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
      .nawi-dashboard .activity-list li { display: flex; gap: 10px; font-size: 13px; border-bottom: 1px solid #f0f1f3; padding-bottom: 8px; }
      .nawi-dashboard .activity-time { color: #888; font-size: 12px; min-width: 78px; flex-shrink: 0; }
      .nawi-dashboard .login-screen { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #eef1f4; padding: 20px; }
      .nawi-dashboard .login-card { background: #fff; border: 1px solid #d7dbe0; border-radius: 4px; padding: 28px 30px; width: 100%; max-width: 360px; }
      .nawi-dashboard .login-title { font-size: 19px; margin: 0 0 2px; color: #0d3b66; }
      .nawi-dashboard .login-subtitle { font-size: 12.5px; color: #666; margin: 0 0 18px; }
      .nawi-dashboard .login-form { display: flex; flex-direction: column; gap: 12px; }
      .nawi-dashboard .login-btn { width: 100%; margin-top: 4px; padding: 9px; }
      .nawi-dashboard .login-hint { font-size: 11.5px; color: #888; margin-top: 14px; }
      .nawi-dashboard .login-divider { text-align: center; font-size: 11.5px; color: #999; margin: 16px 0 10px; }
      .nawi-dashboard .quick-login-row { display: flex; gap: 8px; }
      .nawi-dashboard .quick-login-btn { flex: 1; font-size: 12.5px; padding: 8px 6px; }
      @media (max-width: 900px) {
        .nawi-dashboard .split-view { grid-template-columns: 1fr; }
        .nawi-dashboard .kpi-row { grid-template-columns: repeat(2, 1fr); }
        .nawi-dashboard .sidebar { position: absolute; z-index: 5; height: 100%; }
        .nawi-dashboard .detail-grid, .nawi-dashboard .summary-cards, .nawi-dashboard .form-grid-cols {
          grid-template-columns: 1fr;
        }
      }
    `}</style>
  );
}

/* ---------------------------------------------------------------------- */
/* Login                                                                   */
/* ---------------------------------------------------------------------- */

function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("inspector");

  const submitLogin = () => {
    onLogin({ username: username.trim() || (role === "inspector" ? "R. Mehta" : "K. Verma"), password: password.trim(), role });
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submitLogin();
    }
  };

  const quickLogin = (quickRole) => {
    onLogin({ username: quickRole === "inspector" ? "R. Mehta" : "K. Verma", password: "password123", role: quickRole });
  };

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1 className="login-title">Legal Metrology Portal</h1>
        <p className="login-subtitle">OIML R-76 Testing &amp; Compliance System</p>
        <div className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input id="username" value={username} onChange={(e) => setUsername(e.target.value)} onKeyDown={handleKeyDown} placeholder="e.g. R. Mehta" />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} onKeyDown={handleKeyDown} placeholder="********" />
          </div>
          <div className="form-group">
            <label htmlFor="role">Login as</label>
            <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="inspector">Inspector / Lab Analyst</option>
              <option value="reviewer">Reviewer</option>
            </select>
          </div>
          <button type="button" className="btn btn-primary login-btn" onClick={submitLogin}>Login</button>
        </div>
        <div className="login-divider">or jump straight in</div>
        <div className="quick-login-row">
          <button type="button" className="btn btn-secondary quick-login-btn" onClick={() => quickLogin("inspector")}>Continue as Inspector</button>
          <button type="button" className="btn btn-secondary quick-login-btn" onClick={() => quickLogin("reviewer")}>Continue as Reviewer</button>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Dashboard                                                               */
/* ---------------------------------------------------------------------- */

function DashboardPage({ instruments, sessions, activityLog }) {
  const stats = useMemo(() => {
    let pass = 0;
    let fail = 0;
    let pendingReview = 0;
    sessions.forEach((s) => {
      const instrument = instruments.find((i) => i.id === s.instrumentId);
      const compliance = getSessionCompliance(s, instrument);
      if (compliance.overall === "PASS") pass++;
      if (compliance.overall === "FAIL") fail++;
      if (s.status === "PENDING_REVIEW") pendingReview++;
    });
    return { total: sessions.length, pass, fail, pendingReview };
  }, [instruments, sessions]);

  const kpis = [
    { label: "Total Instruments Tested", value: stats.total },
    { label: "Model Approvals Passed", value: stats.pass },
    { label: "Failed Compliance", value: stats.fail },
    { label: "Reports Pending Sign-off", value: stats.pendingReview },
  ];

  return (
    <div>
      <div className="kpi-row">
        {kpis.map((k) => (
          <div className="kpi-card" key={k.label}>
            <div className="kpi-value">{k.value}</div>
            <div className="kpi-label">{k.label}</div>
          </div>
        ))}
      </div>
      <div className="panel">
        <h3 className="panel-title">Recent Activity</h3>
        <ul className="activity-list">
          {activityLog.slice(0, 8).map((a, idx) => (
            <li key={idx}>
              <span className="activity-time">{a.time}</span>
              <span className="activity-text">{a.text}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Instruments: list + search + registration + detail/history              */
/* ---------------------------------------------------------------------- */

function InstrumentsPage({ instruments, sessions, onRegister, selectedInstrumentId, onSelectInstrument, onStartSession, onOpenSession }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [formState, setFormState] = useState({ manufacturer: "", model: "", category: "Class III - Medium (Retail)", maxCapacity: "", eValue: "", owner: "", location: "" });

  const filtered = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return instruments;
    return instruments.filter(
      (i) =>
        i.id.toLowerCase().includes(term) ||
        i.manufacturer.toLowerCase().includes(term) ||
        i.model.toLowerCase().includes(term) ||
        i.owner.toLowerCase().includes(term)
    );
  }, [instruments, searchTerm]);

  const selectedInstrument = instruments.find((i) => i.id === selectedInstrumentId);

  const handleFormChange = (field) => (e) => setFormState((prev) => ({ ...prev, [field]: e.target.value }));

  const handleRegister = (e) => {
    e.preventDefault();
    onRegister(formState);
    setFormState({ manufacturer: "", model: "", category: "Class III - Medium (Retail)", maxCapacity: "", eValue: "", owner: "", location: "" });
    setShowForm(false);
  };

  if (selectedInstrument) {
    const history = sessions.filter((s) => s.instrumentId === selectedInstrument.id);
    return (
      <div>
        <button className="btn btn-secondary back-btn" onClick={() => onSelectInstrument(null)}>&larr; Back to Instruments</button>
        <div className="panel">
          <h3 className="panel-title">{selectedInstrument.id} ({selectedInstrument.manufacturer} {selectedInstrument.model})</h3>
          <div className="detail-grid">
            <div><span className="detail-label">Category</span><span>{selectedInstrument.category}</span></div>
            <div><span className="detail-label">Max Capacity</span><span>{selectedInstrument.maxCapacity} kg</span></div>
            <div><span className="detail-label">Verification Interval (e)</span><span>{selectedInstrument.eValue} kg</span></div>
            <div><span className="detail-label">Owner / Facility</span><span>{selectedInstrument.owner}</span></div>
            <div><span className="detail-label">Location</span><span>{selectedInstrument.location}</span></div>
          </div>
          <button className="btn btn-primary" onClick={() => onStartSession(selectedInstrument.id)}>+ New Test Session</button>
        </div>
        <div className="panel">
          <h3 className="panel-title">Test History</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th>Session ID</th><th>Test Date</th><th>Tester</th><th>Workflow</th><th>Compliance</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {history.map((s) => {
                  const compliance = getSessionCompliance(s, selectedInstrument);
                  return (
                    <tr key={s.id}>
                      <td>{s.id}</td>
                      <td>{s.testDate}</td>
                      <td>{s.tester}</td>
                      <td><WorkflowBadge status={s.status} /></td>
                      <td><ComplianceBadge status={compliance.overall} /></td>
                      <td>
                        {s.status === "DRAFT" ? (
                          <button className="action-btn" onClick={() => onOpenSession(s.id, "edit", "instruments")}>Continue Editing</button>
                        ) : (
                          <button className="action-btn" onClick={() => onOpenSession(s.id, "view", "instruments")}>View Report</button>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {history.length === 0 && <tr><td colSpan={6} className="empty-row">No test sessions recorded yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="table-panel-header">
        <h3 className="panel-title">Registered Instruments</h3>
        <div className="header-actions">
          <input className="search-input" placeholder="Search by ID, Manufacturer, Model or Owner" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
          <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>{showForm ? "Cancel" : "+ Register Instrument"}</button>
        </div>
      </div>

      {showForm && (
        <form className="inline-form" onSubmit={handleRegister}>
          <div className="form-grid-cols">
            <div className="form-group">
              <label>Manufacturer</label>
              <input required value={formState.manufacturer} onChange={handleFormChange("manufacturer")} placeholder="e.g. Avery India" />
            </div>
            <div className="form-group">
              <label>Model</label>
              <input required value={formState.model} onChange={handleFormChange("model")} placeholder="e.g. AK-500" />
            </div>
            <div className="form-group">
              <label>Category / Accuracy Class</label>
              <select value={formState.category} onChange={handleFormChange("category")}>
                <option>Class I - Special (Precision / Analytical)</option>
                <option>Class II - High (Laboratory)</option>
                <option>Class III - Medium (Retail)</option>
                <option>Class III - Medium (Industrial)</option>
                <option>Class IIII - Ordinary</option>
              </select>
            </div>
            <div className="form-group">
              <label>Max Capacity (kg)</label>
              <input required value={formState.maxCapacity} onChange={handleFormChange("maxCapacity")} placeholder="e.g. 500" />
            </div>
            <div className="form-group">
              <label>Verification Interval (e)</label>
              <input required value={formState.eValue} onChange={handleFormChange("eValue")} placeholder="e.g. 0.1" />
            </div>
            <div className="form-group">
              <label>Owner / Facility</label>
              <input required value={formState.owner} onChange={handleFormChange("owner")} placeholder="e.g. Karnataka Foods Pvt Ltd" />
            </div>
            <div className="form-group">
              <label>Location</label>
              <input required value={formState.location} onChange={handleFormChange("location")} placeholder="e.g. Peenya Industrial Area" />
            </div>
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary">Register Instrument</button>
          </div>
        </form>
      )}

      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Instrument ID</th><th>Manufacturer</th><th>Model</th><th>Category</th><th>Owner</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {filtered.map((i) => (
              <tr key={i.id}>
                <td>{i.id}</td>
                <td>{i.manufacturer}</td>
                <td>{i.model}</td>
                <td>{i.category}</td>
                <td>{i.owner}</td>
                <td><button className="action-btn" onClick={() => onSelectInstrument(i.id)}>View</button></td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={6} className="empty-row">No matching instruments found.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* New Test Session                                                        */
/* ---------------------------------------------------------------------- */

function NewSessionPage({ instruments, preselectedInstrumentId, onStart, onCancel }) {
  const [instrumentId, setInstrumentId] = useState(preselectedInstrumentId || (instruments[0] ? instruments[0].id : ""));
  const [tester, setTester] = useState("");
  const [labLocation, setLabLocation] = useState("");
  const [temp, setTemp] = useState("");
  const [humidity, setHumidity] = useState("");
  const [testDate, setTestDate] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!instrumentId) return;
    onStart({
      instrumentId,
      tester: tester.trim() || "Unassigned",
      labLocation: labLocation.trim() || "Not specified",
      temp,
      humidity,
      testDate: testDate || "Not set",
    });
  };

  return (
    <div className="panel narrow-panel">
      <h3 className="panel-title">Start a New Test Session</h3>
      <form onSubmit={handleSubmit} className="form-grid">
        <div className="form-group">
          <label>Instrument</label>
          <select value={instrumentId} onChange={(e) => setInstrumentId(e.target.value)}>
            {instruments.map((i) => (
              <option key={i.id} value={i.id}>{i.id} ({i.manufacturer} {i.model})</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>Tester Name</label>
          <input value={tester} onChange={(e) => setTester(e.target.value)} placeholder="e.g. R. Mehta" />
        </div>
        <div className="form-group">
          <label>Lab / Test Location</label>
          <input value={labLocation} onChange={(e) => setLabLocation(e.target.value)} placeholder="e.g. CMRIT Metrology Lab" />
        </div>
        <div className="form-group">
          <label>Test Date</label>
          <input type="date" value={testDate} onChange={(e) => setTestDate(e.target.value)} />
        </div>
        <div className="form-group">
          <label>Ambient Temperature (&deg;C)</label>
          <input value={temp} onChange={(e) => setTemp(e.target.value)} placeholder="e.g. 27" />
        </div>
        <div className="form-group">
          <label>Relative Humidity (%RH)</label>
          <input value={humidity} onChange={(e) => setHumidity(e.target.value)} placeholder="e.g. 55" />
        </div>
        <div className="form-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button type="submit" className="btn btn-primary">Start Test Session</button>
        </div>
      </form>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Test Entry: Eccentricity / Repeatability / Discrimination / Linearity   */
/* + Attachments                                                           */
/* ---------------------------------------------------------------------- */

function TestEntryPage({ session, instrument, updateSession, onBack, onViewCompliance }) {
  const [activeTab, setActiveTab] = useState(1);

  const compliance = useMemo(() => getSessionCompliance(session, instrument), [session, instrument]);

  const updateEcc = (field, value) => updateSession(session.id, (s) => ({ ...s, eccentricity: { ...s.eccentricity, [field]: value } }));
  const updateEccRow = (rowId, value) =>
    updateSession(session.id, (s) => ({
      ...s,
      eccentricity: { ...s.eccentricity, rows: s.eccentricity.rows.map((r) => (r.id === rowId ? { ...r, indication: value } : r)) },
    }));
  const updateRep = (field, value) => updateSession(session.id, (s) => ({ ...s, repeatability: { ...s.repeatability, [field]: value } }));
  const updateRepRow = (rowId, value) =>
    updateSession(session.id, (s) => ({
      ...s,
      repeatability: { ...s.repeatability, rows: s.repeatability.rows.map((r) => (r.id === rowId ? { ...r, indication: value } : r)) },
    }));
  const updateDisc = (field, value) => updateSession(session.id, (s) => ({ ...s, discrimination: { ...s.discrimination, [field]: value } }));
  const updateLinRow = (rowId, field, value) =>
    updateSession(session.id, (s) => ({
      ...s,
      linearity: { ...s.linearity, rows: s.linearity.rows.map((r) => (r.id === rowId ? { ...r, [field]: value } : r)) },
    }));

  const handleFiles = (e) => {
    const files = Array.from(e.target.files || []).map((f) => ({
      id: `${Date.now()}-${f.name}`,
      name: f.name,
      size: formatFileSize(f.size),
    }));
    updateSession(session.id, (s) => ({ ...s, attachments: [...s.attachments, ...files] }));
    e.target.value = "";
  };
  const removeFile = (id) => updateSession(session.id, (s) => ({ ...s, attachments: s.attachments.filter((a) => a.id !== id) }));

  const tabs = [
    { id: 1, label: "Eccentricity" },
    { id: 2, label: "Repeatability" },
    { id: 3, label: "Discrimination" },
    { id: 4, label: "Linearity" },
    { id: 5, label: "Attachments" },
  ];

  return (
    <div className="panel">
      <div className="session-header">
        <div>
          <h3 className="panel-title">Test Entry - {session.id}</h3>
          <p className="session-subtitle">
            {instrument ? `${instrument.id} (${instrument.manufacturer} ${instrument.model})` : "Instrument not found"} - Tester: {session.tester}
          </p>
        </div>
        <WorkflowBadge status={session.status} />
      </div>

      <div className="tabs">
        {tabs.map((t) => (
          <button key={t.id} className={`tab-btn ${activeTab === t.id ? "active" : ""}`} onClick={() => setActiveTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 1 && (
        <div>
          <div className="form-group inline-input">
            <label>Test Load (kg)</label>
            <input value={session.eccentricity.testLoad} onChange={(e) => updateEcc("testLoad", e.target.value)} placeholder="e.g. 15" />
          </div>
          <div className="table-scroll">
            <table>
              <thead><tr><th>Position</th><th>Indication</th><th>Error</th><th>MPE</th><th>Status</th></tr></thead>
              <tbody>
                {compliance.eccentricity.rows.map((r) => {
                  const rawRow = session.eccentricity.rows.find((row) => row.id === r.id);
                  return (
                    <tr key={r.id}>
                      <td>{r.label}</td>
                      <td><input className="cell-input" value={rawRow.indication} onChange={(e) => updateEccRow(r.id, e.target.value)} placeholder="e.g. 15.01" /></td>
                      <td>{r.error !== null ? r.error.toFixed(3) : "-"}</td>
                      <td>{r.mpe !== null ? `+/- ${r.mpe.toFixed(3)}` : "-"}</td>
                      <td><ComplianceBadge status={r.status} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="tab-overall">Overall Eccentricity Result: <ComplianceBadge status={compliance.eccentricity.status} /></p>
        </div>
      )}

      {activeTab === 2 && (
        <div>
          <div className="form-group inline-input">
            <label>Test Load (kg)</label>
            <input value={session.repeatability.testLoad} onChange={(e) => updateRep("testLoad", e.target.value)} placeholder="e.g. 15" />
          </div>
          <div className="table-scroll">
            <table>
              <thead><tr><th>Trial</th><th>Indication</th></tr></thead>
              <tbody>
                {session.repeatability.rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.label}</td>
                    <td><input className="cell-input" value={r.indication} onChange={(e) => updateRepRow(r.id, e.target.value)} placeholder="e.g. 15.00" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="tab-overall">
            Range (Max - Min): {compliance.repeatability.range !== null ? compliance.repeatability.range.toFixed(3) : "-"}
            {" | "}MPE: {compliance.repeatability.mpe !== null ? `+/- ${compliance.repeatability.mpe.toFixed(3)}` : "-"}{" "}
            <ComplianceBadge status={compliance.repeatability.status} />
          </p>
        </div>
      )}

      {activeTab === 3 && (
        <div className="form-grid">
          <div className="form-group">
            <label>Test Load (kg)</label>
            <input value={session.discrimination.testLoad} onChange={(e) => updateDisc("testLoad", e.target.value)} placeholder="e.g. 15" />
          </div>
          <div className="form-group">
            <label>Reading Before Increment</label>
            <input value={session.discrimination.readingBefore} onChange={(e) => updateDisc("readingBefore", e.target.value)} placeholder="e.g. 15.00" />
          </div>
          <div className="form-group">
            <label>Small Increment Added</label>
            <input value={session.discrimination.increment} onChange={(e) => updateDisc("increment", e.target.value)} placeholder="e.g. 0.02" />
          </div>
          <div className="form-group">
            <label>Reading After Increment</label>
            <input value={session.discrimination.readingAfter} onChange={(e) => updateDisc("readingAfter", e.target.value)} placeholder="e.g. 15.02" />
          </div>
          <p className="tab-overall">
            Change Observed: {compliance.discrimination.delta !== null ? compliance.discrimination.delta.toFixed(5) : "-"}
            {" | "}Minimum Expected: {compliance.discrimination.expectedMin !== null ? compliance.discrimination.expectedMin.toFixed(5) : "-"}{" "}
            <ComplianceBadge status={compliance.discrimination.status} />
          </p>
        </div>
      )}

      {activeTab === 4 && (
        <div>
          <div className="table-scroll">
            <table>
              <thead><tr><th>Point</th><th>Applied Load</th><th>Indication</th><th>Error</th><th>MPE</th><th>Status</th></tr></thead>
              <tbody>
                {compliance.linearity.rows.map((r) => {
                  const rawRow = session.linearity.rows.find((row) => row.id === r.id);
                  return (
                    <tr key={r.id}>
                      <td>{r.label}</td>
                      <td><input className="cell-input" value={rawRow.appliedLoad} onChange={(e) => updateLinRow(r.id, "appliedLoad", e.target.value)} placeholder="e.g. 7.5" /></td>
                      <td><input className="cell-input" value={rawRow.indication} onChange={(e) => updateLinRow(r.id, "indication", e.target.value)} placeholder="e.g. 7.5" /></td>
                      <td>{r.error !== null ? r.error.toFixed(3) : "-"}</td>
                      <td>{r.mpe !== null ? `+/- ${r.mpe.toFixed(3)}` : "-"}</td>
                      <td><ComplianceBadge status={r.status} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="tab-overall">Overall Linearity Result: <ComplianceBadge status={compliance.linearity.status} /></p>
        </div>
      )}

      {activeTab === 5 && (
        <div>
          <div className="form-group">
            <label>Upload Photos / Documents</label>
            <input type="file" multiple onChange={handleFiles} />
          </div>
          <ul className="file-list">
            {session.attachments.map((a) => (
              <li key={a.id}>
                <span>{a.name}</span>
                <span className="file-size">{a.size}</span>
                <button className="action-btn" onClick={() => removeFile(a.id)}>Remove</button>
              </li>
            ))}
            {session.attachments.length === 0 && <li className="empty-row">No files attached yet.</li>}
          </ul>
        </div>
      )}

      <div className="form-actions">
        <button className="btn btn-secondary" onClick={onBack}>Back</button>
        <button className="btn btn-primary" onClick={onViewCompliance}>View Compliance Results</button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Compliance Results: table + chart                                       */
/* ---------------------------------------------------------------------- */

function ComplianceResultsPage({ session, instrument, onBack, onProceed }) {
  const compliance = useMemo(() => getSessionCompliance(session, instrument), [session, instrument]);

  const chartData = useMemo(() => {
    const rows = [];
    compliance.eccentricity.rows.forEach((r) => {
      rows.push({ name: `Ecc. ${r.label}`, absError: r.error !== null ? Math.abs(r.error) : 0, mpe: r.mpe || 0, status: r.status });
    });
    compliance.linearity.rows.forEach((r) => {
      rows.push({ name: `Lin. ${r.label}`, absError: r.error !== null ? Math.abs(r.error) : 0, mpe: r.mpe || 0, status: r.status });
    });
    return rows;
  }, [compliance]);

  const statusColor = (status) => (status === "PASS" ? "#1e7e34" : status === "FAIL" ? "#b02a2a" : "#999999");

  return (
    <div className="panel">
      <div className="session-header">
        <div>
          <h3 className="panel-title">Compliance Results - {session.id}</h3>
          <p className="session-subtitle">{instrument ? `${instrument.id} (${instrument.manufacturer} ${instrument.model})` : "Instrument not found"}</p>
        </div>
        <ComplianceBadge status={compliance.overall} />
      </div>

      <h4 className="section-heading">Eccentricity &amp; Linearity - Error vs MPE</h4>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e3e6ea" />
            <XAxis dataKey="name" angle={-35} textAnchor="end" interval={0} height={70} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="absError" name="Absolute Error">
              {chartData.map((entry, idx) => (
                <Cell key={idx} fill={statusColor(entry.status)} />
              ))}
            </Bar>
            <Bar dataKey="mpe" name="MPE Threshold" fill="#c7ccd3" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="table-scroll">
        <table>
          <thead><tr><th>Test Type</th><th>Point</th><th>Applied Load</th><th>Indication</th><th>Error</th><th>MPE</th><th>Status</th></tr></thead>
          <tbody>
            {compliance.eccentricity.rows.map((r) => (
              <tr key={`ecc-${r.id}`}>
                <td>Eccentricity</td><td>{r.label}</td><td>{r.appliedLoad || "-"}</td><td>{r.indication || "-"}</td>
                <td>{r.error !== null ? r.error.toFixed(3) : "-"}</td><td>{r.mpe !== null ? `+/- ${r.mpe.toFixed(3)}` : "-"}</td>
                <td><ComplianceBadge status={r.status} /></td>
              </tr>
            ))}
            {compliance.linearity.rows.map((r) => (
              <tr key={`lin-${r.id}`}>
                <td>Linearity</td><td>{r.label}</td><td>{r.appliedLoad || "-"}</td><td>{r.indication || "-"}</td>
                <td>{r.error !== null ? r.error.toFixed(3) : "-"}</td><td>{r.mpe !== null ? `+/- ${r.mpe.toFixed(3)}` : "-"}</td>
                <td><ComplianceBadge status={r.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="summary-cards">
        <div className="summary-card">
          <h4>Repeatability</h4>
          <p>Test Load: {session.repeatability.testLoad || "-"} kg</p>
          <p>Readings: {session.repeatability.rows.map((r) => r.indication || "-").join(", ")}</p>
          <p>Range: {compliance.repeatability.range !== null ? compliance.repeatability.range.toFixed(3) : "-"} | MPE: {compliance.repeatability.mpe !== null ? `+/- ${compliance.repeatability.mpe.toFixed(3)}` : "-"}</p>
          <ComplianceBadge status={compliance.repeatability.status} />
        </div>
        <div className="summary-card">
          <h4>Discrimination</h4>
          <p>Test Load: {session.discrimination.testLoad || "-"} kg</p>
          <p>Before: {session.discrimination.readingBefore || "-"} | Increment: {session.discrimination.increment || "-"} | After: {session.discrimination.readingAfter || "-"}</p>
          <p>Change Observed: {compliance.discrimination.delta !== null ? compliance.discrimination.delta.toFixed(5) : "-"}</p>
          <ComplianceBadge status={compliance.discrimination.status} />
        </div>
      </div>

      <div className="form-actions">
        <button className="btn btn-secondary" onClick={onBack}>Back to Test Entry</button>
        <button className="btn btn-primary" onClick={onProceed}>Proceed to Report Preview</button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Report Preview + export + submit/approve/reject                         */
/* ---------------------------------------------------------------------- */

function ReportPreviewPage({ session, instrument, role, onBack, onSubmitForReview, onApprove, onReject }) {
  const compliance = useMemo(() => getSessionCompliance(session, instrument), [session, instrument]);
  const [downloading, setDownloading] = useState(null);

  const handleDownload = async (type) => {
    try {
      setDownloading(type);
      const endpoint = type === "PDF" ? "pdf" : "docx";
      const res = await API.get(`/reports/${session.id}/${endpoint}`, { responseType: "blob" });
      const ext = type === "PDF" ? "pdf" : "docx";
      const mime = type === "PDF" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      const blob = new Blob([res.data], { type: mime });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `${session.id}_OIML_R76_Report.${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(`Download error for ${type}:`, err);
      alert(`Could not download ${type} report. Please check server status.`);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="panel report-doc">
      <div className="session-header">
        <div>
          <h3 className="panel-title">NAWI Test Report - {session.id}</h3>
          <p className="session-subtitle">Generated per OIML R-76 International Recommendation</p>
        </div>
        <div className="report-badges">
          <WorkflowBadge status={session.status} />
          <ComplianceBadge status={compliance.overall} />
        </div>
      </div>

      <div className="detail-grid">
        <div><span className="detail-label">Instrument</span><span>{instrument ? `${instrument.id} (${instrument.manufacturer} ${instrument.model})` : "Not found"}</span></div>
        <div><span className="detail-label">Category / Accuracy Class</span><span>{instrument ? (instrument.category || instrument.accuracy_class) : "-"}</span></div>
        <div><span className="detail-label">Max Capacity / e</span><span>{instrument ? `${instrument.maxCapacity ?? instrument.max_capacity} kg / ${instrument.eValue ?? instrument.e_value} kg` : "-"}</span></div>
        <div><span className="detail-label">Owner / Facility</span><span>{instrument ? instrument.owner : "-"}</span></div>
        <div><span className="detail-label">Tester</span><span>{session.tester}</span></div>
        <div><span className="detail-label">Test Date</span><span>{session.testDate}</span></div>
        <div><span className="detail-label">Lab / Location</span><span>{session.labLocation}</span></div>
        <div><span className="detail-label">Ambient Conditions</span><span>{session.temp}&deg;C, {session.humidity}%RH</span></div>
      </div>

      <h4 className="section-heading">Eccentricity Test</h4>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Position</th><th>Applied Load</th><th>Indication</th><th>Error</th><th>MPE</th><th>Status</th></tr></thead>
          <tbody>
            {compliance.eccentricity.rows.map((r) => (
              <tr key={r.id}><td>{r.label}</td><td>{r.appliedLoad || "-"}</td><td>{r.indication || "-"}</td><td>{r.error !== null ? r.error.toFixed(3) : "-"}</td><td>{r.mpe !== null ? `+/- ${r.mpe.toFixed(3)}` : "-"}</td><td><ComplianceBadge status={r.status} /></td></tr>
            ))}
          </tbody>
        </table>
      </div>

      <h4 className="section-heading">Linearity Test</h4>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Point</th><th>Applied Load</th><th>Indication</th><th>Error</th><th>MPE</th><th>Status</th></tr></thead>
          <tbody>
            {compliance.linearity.rows.map((r) => (
              <tr key={r.id}><td>{r.label}</td><td>{r.appliedLoad || "-"}</td><td>{r.indication || "-"}</td><td>{r.error !== null ? r.error.toFixed(3) : "-"}</td><td>{r.mpe !== null ? `+/- ${r.mpe.toFixed(3)}` : "-"}</td><td><ComplianceBadge status={r.status} /></td></tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="summary-cards">
        <div className="summary-card">
          <h4>Repeatability</h4>
          <p>Range: {compliance.repeatability.range !== null ? compliance.repeatability.range.toFixed(3) : "-"} | MPE: {compliance.repeatability.mpe !== null ? `+/- ${compliance.repeatability.mpe.toFixed(3)}` : "-"}</p>
          <ComplianceBadge status={compliance.repeatability.status} />
        </div>
        <div className="summary-card">
          <h4>Discrimination</h4>
          <p>Change Observed: {compliance.discrimination.delta !== null ? compliance.discrimination.delta.toFixed(5) : "-"}</p>
          <ComplianceBadge status={compliance.discrimination.status} />
        </div>
      </div>

      <h4 className="section-heading">Attachments</h4>
      <ul className="file-list">
        {session.attachments.map((a) => <li key={a.id}><span>{a.name}</span><span className="file-size">{a.size}</span></li>)}
        {session.attachments.length === 0 && <li className="empty-row">No attachments.</li>}
      </ul>

      <div className="form-actions">
        <button className="btn btn-secondary" onClick={onBack}>Back</button>
        <button className="btn btn-secondary" disabled={downloading !== null} onClick={() => handleDownload("PDF")}>
          {downloading === "PDF" ? "Generating PDF..." : "📥 Download PDF"}
        </button>
        <button className="btn btn-secondary" disabled={downloading !== null} onClick={() => handleDownload("Word")}>
          {downloading === "Word" ? "Generating Word..." : "📥 Download Word (.docx)"}
        </button>
        {role === "inspector" && session.status === "DRAFT" && (
          <button className="btn btn-primary" onClick={onSubmitForReview}>Submit for Review</button>
        )}
        {role === "reviewer" && session.status === "PENDING_REVIEW" && (
          <>
            <button className="btn btn-primary" onClick={onApprove}>Approve</button>
            <button className="btn btn-danger" onClick={onReject}>Reject</button>
          </>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Report Repository                                                        */
/* ---------------------------------------------------------------------- */

function ReportRepositoryPage({ instruments, sessions, onOpenSession }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [testerFilter, setTesterFilter] = useState("ALL");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const submitted = useMemo(() => sessions.filter((s) => s.status !== "DRAFT"), [sessions]);
  const testers = useMemo(() => Array.from(new Set(submitted.map((s) => s.tester))), [submitted]);

  const filtered = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return submitted.filter((s) => {
      const instrument = instruments.find((i) => i.id === s.instrumentId);
      const compliance = getSessionCompliance(s, instrument);
      const matchesTerm =
        !term ||
        s.instrumentId.toLowerCase().includes(term) ||
        (instrument && instrument.manufacturer.toLowerCase().includes(term)) ||
        (instrument && instrument.model.toLowerCase().includes(term));
      const matchesStatus = statusFilter === "ALL" || compliance.overall === statusFilter;
      const matchesTester = testerFilter === "ALL" || s.tester === testerFilter;
      const matchesFrom = !fromDate || s.testDate >= fromDate;
      const matchesTo = !toDate || s.testDate <= toDate;
      return matchesTerm && matchesStatus && matchesTester && matchesFrom && matchesTo;
    });
  }, [submitted, instruments, searchTerm, statusFilter, testerFilter, fromDate, toDate]);

  return (
    <div className="panel">
      <div className="table-panel-header">
        <h3 className="panel-title">Report Repository</h3>
      </div>
      <div className="filter-row">
        <input className="search-input" placeholder="Search Instrument ID, Manufacturer or Model" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="ALL">All Statuses</option>
          <option value="PASS">Pass</option>
          <option value="FAIL">Fail</option>
          <option value="PENDING">Pending</option>
        </select>
        <select value={testerFilter} onChange={(e) => setTesterFilter(e.target.value)}>
          <option value="ALL">All Testers</option>
          {testers.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <label className="date-filter">From <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} /></label>
        <label className="date-filter">To <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} /></label>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Instrument ID</th><th>Manufacturer</th><th>Model</th><th>Test Date</th><th>Tester</th><th>Workflow</th><th>Compliance</th><th>Actions</th></tr></thead>
          <tbody>
            {filtered.map((s) => {
              const instrument = instruments.find((i) => i.id === s.instrumentId);
              const compliance = getSessionCompliance(s, instrument);
              return (
                <tr key={s.id}>
                  <td>{s.instrumentId}</td>
                  <td>{instrument ? instrument.manufacturer : "-"}</td>
                  <td>{instrument ? instrument.model : "-"}</td>
                  <td>{s.testDate}</td>
                  <td>{s.tester}</td>
                  <td><WorkflowBadge status={s.status} /></td>
                  <td><ComplianceBadge status={compliance.overall} /></td>
                  <td className="actions-cell">
                    <button className="action-btn" onClick={() => onOpenSession(s.id, "view", "reportRepository")}>View Report</button>
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && <tr><td colSpan={8} className="empty-row">No matching reports found.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Reviewer Approval Queue                                                  */
/* ---------------------------------------------------------------------- */

function ReviewerQueuePage({ instruments, sessions, onOpenSession, onApprove, onReject }) {
  const pending = sessions.filter((s) => s.status === "PENDING_REVIEW");

  return (
    <div className="panel">
      <h3 className="panel-title">Reviewer Approval Queue</h3>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Instrument ID</th><th>Manufacturer</th><th>Model</th><th>Tester</th><th>Test Date</th><th>Compliance</th><th>Actions</th></tr></thead>
          <tbody>
            {pending.map((s) => {
              const instrument = instruments.find((i) => i.id === s.instrumentId);
              const compliance = getSessionCompliance(s, instrument);
              return (
                <tr key={s.id}>
                  <td>{s.instrumentId}</td>
                  <td>{instrument ? instrument.manufacturer : "-"}</td>
                  <td>{instrument ? instrument.model : "-"}</td>
                  <td>{s.tester}</td>
                  <td>{s.testDate}</td>
                  <td><ComplianceBadge status={compliance.overall} /></td>
                  <td className="actions-cell">
                    <button className="action-btn" onClick={() => onOpenSession(s.id, "view", "reviewerQueue")}>View Report</button>
                    <button className="action-btn" onClick={() => onApprove(s.id)}>Approve</button>
                    <button className="action-btn" onClick={() => onReject(s.id)}>Reject</button>
                  </td>
                </tr>
              );
            })}
            {pending.length === 0 && <tr><td colSpan={7} className="empty-row">Nothing awaiting review.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Main App                                                                 */
/* ---------------------------------------------------------------------- */

export default function NawiPortalApp() {
  const [auth, setAuth] = useState(() => {
    try {
      const u = localStorage.getItem("nawi_user");
      const t = localStorage.getItem("nawi_token");
      if (u && t) return JSON.parse(u);
    } catch {}
    return { loggedIn: false, role: "inspector", username: "" };
  });
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentPage, setCurrentPage] = useState("dashboard");
  const [instruments, setInstruments] = useState(initialInstruments);
  const [sessions, setSessions] = useState(initialSessions);
  const [activityLog, setActivityLog] = useState(initialActivity);
  const [selectedInstrumentId, setSelectedInstrumentId] = useState(null);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [returnPage, setReturnPage] = useState("reportRepository");
  const [preselectedInstrumentId, setPreselectedInstrumentId] = useState(null);
  const [instrumentCounter, setInstrumentCounter] = useState(initialInstruments.length);
  const [sessionCounter, setSessionCounter] = useState(initialSessions.length);
  const [useBackend, setUseBackend] = useState(true);

  /* ---- Data fetching helpers ---- */

  const fetchInstruments = useCallback(async () => {
    try {
      const res = await API.get("/instruments");
      setInstruments(res.data);
      setInstrumentCounter(res.data.length);
    } catch {
      /* backend unavailable — keep current state */
    }
  }, []);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await API.get("/sessions");
      /* Map backend snake_case fields to frontend camelCase */
      const mapped = res.data.map((s) => ({
        id: s.id,
        instrumentId: s.instrument_id,
        tester: s.tester,
        testDate: s.test_date,
        labLocation: s.lab_location,
        temp: s.temperature,
        humidity: s.humidity,
        status: s.status,
        rejectionReason: s.rejection_reason || null,
        eccentricity: {
          testLoad: s.eccentricity?.test_load || "",
          rows: (s.eccentricity?.rows || []).map((r) => ({ id: r.id, label: r.label, indication: r.indication || "" })),
        },
        repeatability: {
          testLoad: s.repeatability?.test_load || "",
          rows: (s.repeatability?.rows || []).map((r) => ({ id: r.id, label: r.label, indication: r.indication || "" })),
        },
        discrimination: {
          testLoad: s.discrimination?.test_load || "",
          readingBefore: s.discrimination?.reading_before || "",
          increment: s.discrimination?.increment || "",
          readingAfter: s.discrimination?.reading_after || "",
        },
        linearity: {
          rows: (s.linearity?.rows || []).map((r) => ({
            id: r.id,
            label: r.label,
            appliedLoad: r.applied_load || "",
            indication: r.indication || "",
          })),
        },
        attachments: (s.attachments || []).map((a) => ({
          id: a.id,
          name: a.file_name,
          size: a.file_size || "",
        })),
      }));
      setSessions(mapped);
      setSessionCounter(mapped.length);
    } catch {
      /* backend unavailable */
    }
  }, []);

  const fetchActivity = useCallback(async () => {
    try {
      const res = await API.get("/activity");
      setActivityLog(res.data);
    } catch {
      /* backend unavailable */
    }
  }, []);

  const refreshAll = useCallback(() => {
    fetchInstruments();
    fetchSessions();
    fetchActivity();
  }, [fetchInstruments, fetchSessions, fetchActivity]);

  /* ---- Load data after login ---- */
  useEffect(() => {
    if (auth.loggedIn && useBackend) {
      refreshAll();
    }
  }, [auth.loggedIn, useBackend, refreshAll]);

  const logActivity = (text) => {
    if (useBackend) {
      API.post("/activity", null, { params: { text, user: auth.username || "User" } }).catch(() => {});
    }
    setActivityLog((prev) => [{ time: "Just now", text }, ...prev]);
  };

  /* ---- Auth ---- */

  const handleLogin = async ({ username, password, role }) => {
    let email = (username && username.includes("@")) ? username.trim() : (role === "inspector" ? "mehta@lab.in" : "verma@lab.in");
    if (username && username.toLowerCase().includes("darshan")) {
      email = "darshanreddy1906@gmail.com";
    }
    const pwd = password || "password123";

    if (useBackend) {
      try {
        const res = await API.post("/auth/login", { email, password: pwd });
        localStorage.setItem("nawi_token", res.data.access_token);
        const userObj = { loggedIn: true, role: res.data.role.toLowerCase(), username: res.data.username || username };
        localStorage.setItem("nawi_user", JSON.stringify(userObj));
        setAuth(userObj);
        setCurrentPage("dashboard");
        return;
      } catch (err) {
        console.warn("Backend auth failed, continuing with local session:", err);
      }
    }
    const userObj = { loggedIn: true, role, username: username.trim() || (role === "inspector" ? "R. Mehta" : "K. Verma") };
    localStorage.setItem("nawi_user", JSON.stringify(userObj));
    setAuth(userObj);
    setCurrentPage("dashboard");
  };

  const handleLogout = () => {
    localStorage.removeItem("nawi_token");
    localStorage.removeItem("nawi_user");
    setAuth({ loggedIn: false, role: "inspector", username: "" });
  };

  const navigate = (page) => {
    setSelectedInstrumentId(null);
    setPreselectedInstrumentId(null);
    setCurrentPage(page);
  };

  /* ---- Instruments ---- */

  const handleRegisterInstrument = async (formState) => {
    let accClass = "CLASS_III";
    if (formState.category.includes("Class I") && !formState.category.includes("Class II")) accClass = "CLASS_I";
    else if (formState.category.includes("Class II") && !formState.category.includes("Class III")) accClass = "CLASS_II";
    else if (formState.category.includes("Class IIII")) accClass = "CLASS_IIII";

    if (useBackend) {
      try {
        await API.post("/instruments", {
          manufacturer: formState.manufacturer,
          model: formState.model,
          category: formState.category,
          max_capacity: parseFloat(formState.maxCapacity) || 0,
          e_value: parseFloat(formState.eValue) || 0,
          owner: formState.owner,
          location: formState.location,
          accuracy_class: accClass,
        });
        fetchInstruments();
        fetchActivity();
        return;
      } catch { /* fall through */ }
    }
    const nextNum = instrumentCounter + 1;
    const id = `INST-${String(nextNum).padStart(4, "0")}`;
    const newInstrument = {
      id,
      manufacturer: formState.manufacturer,
      model: formState.model,
      category: formState.category,
      maxCapacity: parseFloat(formState.maxCapacity) || 0,
      eValue: parseFloat(formState.eValue) || 0,
      owner: formState.owner,
      location: formState.location,
    };
    setInstruments((prev) => [...prev, newInstrument]);
    setInstrumentCounter(nextNum);
    logActivity(`${auth.username || "A user"} registered new instrument ${id}`);
  };

  /* ---- Sessions ---- */

  const handleStartSession = (instrumentId) => {
    setPreselectedInstrumentId(instrumentId);
    setCurrentPage("newSession");
  };

  const handleCreateSession = async (sessionInfo) => {
    if (useBackend) {
      try {
        const res = await API.post("/sessions", {
          instrument_id: sessionInfo.instrumentId,
          tester: sessionInfo.tester,
          test_date: sessionInfo.testDate,
          lab_location: sessionInfo.labLocation,
          temperature: sessionInfo.temp,
          humidity: sessionInfo.humidity,
        });
        await fetchSessions();
        setSelectedSessionId(res.data.id);
        fetchActivity();
        setCurrentPage("testEntry");
        return;
      } catch { /* fall through */ }
    }
    const nextNum = sessionCounter + 1;
    const id = `TS-2026-${String(nextNum).padStart(4, "0")}`;
    const newSession = {
      id,
      instrumentId: sessionInfo.instrumentId,
      tester: sessionInfo.tester,
      testDate: sessionInfo.testDate,
      labLocation: sessionInfo.labLocation,
      temp: sessionInfo.temp,
      humidity: sessionInfo.humidity,
      status: "DRAFT",
      ...buildBlankTestData(),
    };
    setSessions((prev) => [...prev, newSession]);
    setSessionCounter(nextNum);
    setSelectedSessionId(id);
    logActivity(`${sessionInfo.tester} started a new test session for ${sessionInfo.instrumentId}`);
    setCurrentPage("testEntry");
  };

  const updateSession = (sessionId, patchFn) => {
    setSessions((prev) => prev.map((s) => (s.id === sessionId ? patchFn(s) : s)));
    /* Debounced save to backend */
    if (useBackend) {
      const updated = patchFn(sessions.find((s) => s.id === sessionId));
      if (updated) {
        API.put(`/sessions/${sessionId}`, {
          eccentricity: {
            test_load: updated.eccentricity?.testLoad || "",
            rows: (updated.eccentricity?.rows || []).map((r) => ({ id: r.id, label: r.label, indication: r.indication || "" })),
          },
          repeatability: {
            test_load: updated.repeatability?.testLoad || "",
            rows: (updated.repeatability?.rows || []).map((r) => ({ id: r.id, label: r.label, indication: r.indication || "" })),
          },
          discrimination: {
            test_load: updated.discrimination?.testLoad || "",
            reading_before: updated.discrimination?.readingBefore || "",
            increment: updated.discrimination?.increment || "",
            reading_after: updated.discrimination?.readingAfter || "",
          },
          linearity: {
            rows: (updated.linearity?.rows || []).map((r) => ({
              id: r.id,
              label: r.label,
              applied_load: r.appliedLoad || "",
              indication: r.indication || "",
            })),
          },
        }).catch(() => {});
      }
    }
  };

  const handleOpenSession = (sessionId, mode, from) => {
    setSelectedSessionId(sessionId);
    setReturnPage(from);
    setCurrentPage(mode === "edit" ? "testEntry" : "reportPreview");
  };

  /* ---- Workflow transitions ---- */

  const handleSubmitForReview = async () => {
    if (useBackend) {
      try {
        await API.patch(`/sessions/${selectedSessionId}/submit`);
        fetchSessions();
        fetchActivity();
        setCurrentPage("reportRepository");
        return;
      } catch { /* fall through */ }
    }
    const session = sessions.find((s) => s.id === selectedSessionId);
    updateSession(selectedSessionId, (s) => ({ ...s, status: "PENDING_REVIEW" }));
    logActivity(`${session ? session.tester : "Inspector"} submitted test session ${selectedSessionId} for review`);
    setCurrentPage("reportRepository");
  };

  const handleApprove = async (sessionId) => {
    const id = sessionId || selectedSessionId;
    if (useBackend) {
      try {
        await API.patch(`/sessions/${id}/approve`);
        fetchSessions();
        fetchActivity();
        if (!sessionId) setCurrentPage(returnPage);
        return;
      } catch { /* fall through */ }
    }
    updateSession(id, (s) => ({ ...s, status: "APPROVED" }));
    logActivity(`Reviewer approved test session ${id}`);
    if (!sessionId) setCurrentPage(returnPage);
  };

  const handleReject = async (sessionId) => {
    const id = sessionId || selectedSessionId;
    const reason = prompt("Enter rejection reason:");
    if (!reason) return;
    if (useBackend) {
      try {
        await API.patch(`/sessions/${id}/reject`, { rejection_reason: reason });
        fetchSessions();
        fetchActivity();
        if (!sessionId) setCurrentPage(returnPage);
        return;
      } catch { /* fall through */ }
    }
    updateSession(id, (s) => ({ ...s, status: "REJECTED", rejectionReason: reason }));
    logActivity(`Reviewer rejected test session ${id}`);
    if (!sessionId) setCurrentPage(returnPage);
  };

  /* ---- Login screen ---- */

  if (!auth.loggedIn) {
    return (
      <div className="nawi-dashboard">
        <GlobalStyles />
        <LoginPage onLogin={handleLogin} />
      </div>
    );
  }

  const selectedSession = sessions.find((s) => s.id === selectedSessionId);
  const selectedInstrumentForSession = selectedSession ? instruments.find((i) => i.id === selectedSession.instrumentId) : null;

  const roleLabel = auth.role === "inspector" ? "Inspector / Lab Analyst" : "Reviewer";
  const navItems =
    auth.role === "inspector"
      ? [
          { key: "dashboard", label: "Dashboard" },
          { key: "instruments", label: "Instruments" },
          { key: "newSession", label: "New Test Session" },
          { key: "reportRepository", label: "Report Repository" },
        ]
      : [
          { key: "dashboard", label: "Dashboard" },
          { key: "reportRepository", label: "Report Repository" },
          { key: "reviewerQueue", label: "Approval Queue" },
        ];

  return (
    <div className="nawi-dashboard">
      <GlobalStyles />
      <div className="topbar">
        <div className="topbar-left">
          <button className="hamburger-btn" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle menu">&#9776;</button>
          <span className="topbar-title">Legal Metrology Portal - OIML R-76 Testing</span>
        </div>
        <div className="topbar-right">
          <span className="user-indicator">{auth.username || "User"} - {roleLabel}</span>
          {auth.role === "inspector" && (
            <button className="btn btn-primary" onClick={() => navigate("newSession")}>+ New Test Session</button>
          )}
          <button className="btn btn-secondary" onClick={handleLogout}>Logout</button>
        </div>
      </div>

      <div className="layout">
        <div className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
          <nav>
            {navItems.map((item) => (
              <button key={item.key} className={`nav-item ${currentPage === item.key ? "active" : ""}`} onClick={() => navigate(item.key)}>
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="main-content">
          {currentPage === "dashboard" && (
            <DashboardPage instruments={instruments} sessions={sessions} activityLog={activityLog} />
          )}

          {currentPage === "instruments" && (
            <InstrumentsPage
              instruments={instruments}
              sessions={sessions}
              onRegister={handleRegisterInstrument}
              selectedInstrumentId={selectedInstrumentId}
              onSelectInstrument={setSelectedInstrumentId}
              onStartSession={handleStartSession}
              onOpenSession={handleOpenSession}
            />
          )}

          {currentPage === "newSession" && (
            <NewSessionPage
              instruments={instruments}
              preselectedInstrumentId={preselectedInstrumentId}
              onStart={handleCreateSession}
              onCancel={() => navigate("instruments")}
            />
          )}

          {currentPage === "testEntry" &&
            (selectedSession ? (
              <TestEntryPage
                session={selectedSession}
                instrument={selectedInstrumentForSession}
                updateSession={updateSession}
                onBack={() => setCurrentPage("instruments")}
                onViewCompliance={() => setCurrentPage("complianceResults")}
              />
            ) : (
              <div className="panel">No active test session. Start one from Instruments or New Test Session.</div>
            ))}

          {currentPage === "complianceResults" &&
            (selectedSession ? (
              <ComplianceResultsPage
                session={selectedSession}
                instrument={selectedInstrumentForSession}
                onBack={() => setCurrentPage("testEntry")}
                onProceed={() => {
                  setReturnPage("complianceResults");
                  setCurrentPage("reportPreview");
                }}
              />
            ) : (
              <div className="panel">No active test session.</div>
            ))}

          {currentPage === "reportPreview" &&
            (selectedSession ? (
              <ReportPreviewPage
                session={selectedSession}
                instrument={selectedInstrumentForSession}
                role={auth.role}
                onBack={() => setCurrentPage(returnPage)}
                onSubmitForReview={handleSubmitForReview}
                onApprove={() => handleApprove(null)}
                onReject={() => handleReject(null)}
              />
            ) : (
              <div className="panel">No report selected.</div>
            ))}

          {currentPage === "reportRepository" && (
            <ReportRepositoryPage instruments={instruments} sessions={sessions} onOpenSession={handleOpenSession} />
          )}

          {currentPage === "reviewerQueue" && auth.role === "reviewer" && (
            <ReviewerQueuePage instruments={instruments} sessions={sessions} onOpenSession={handleOpenSession} onApprove={handleApprove} onReject={handleReject} />
          )}
        </div>
      </div>
    </div>
  );
}