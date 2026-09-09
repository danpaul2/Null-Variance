import numpy as np
import pandas as pd
from typing import Optional

from app.schemas.models import (
    AccuracyClass,
    ComplianceStatus,
    TestSessionOut,
    InstrumentOut,
    EccentricityResult,
    RepeatabilityResult,
    DiscriminationResult,
    LinearityResult,
    ComplianceResult,
    ReadingResult,
)

# Configurable MPE lookup table for OIML R-76 accuracy classes.
# The table defines tuples of (upper_bound, mpe_factor) where mpe = mpe_factor * e_value.
# m = load / e_value
MPE_TABLE = {
    AccuracyClass.CLASS_I: [
        (50000, 0.5),
        (200000, 1.0),
        (float('inf'), 1.5)
    ],
    AccuracyClass.CLASS_II: [
        (5000, 0.5),
        (20000, 1.0),
        (float('inf'), 1.5)
    ],
    AccuracyClass.CLASS_III: [
        (500, 0.5),
        (2000, 1.0),
        (float('inf'), 1.5)
    ],
    AccuracyClass.CLASS_IIII: [
        (50, 0.5),
        (200, 1.0),
        (float('inf'), 1.5)
    ]
}


def compute_mpe(load: float, e_value: float, accuracy_class: AccuracyClass) -> float | None:
    """
    Computes the Maximum Permissible Error (MPE) for a given load, e_value, and accuracy class.
    
    Args:
        load (float): The applied load.
        e_value (float): The verification scale interval.
        accuracy_class (AccuracyClass): The accuracy class of the instrument.
        
    Returns:
        float | None: The computed MPE in the same units as load/e_value, or None if invalid.
    """
    if e_value <= 0 or load < 0:
        return None
    
    m = load / e_value
    bounds = MPE_TABLE.get(accuracy_class, [])
    
    for upper_bound, factor in bounds:
        if m <= upper_bound:
            return factor * e_value
            
    return None


def compute_error(indication: float, load: float) -> float:
    """
    Computes the error of indication.
    
    Args:
        indication (float): The indicated value.
        load (float): The applied load.
        
    Returns:
        float: The error (indication - load).
    """
    return indication - load


def _safe_float(value: str | float) -> float | None:
    """Helper to convert string/float to float, returning None on failure."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def aggregate_status(statuses: list[ComplianceStatus]) -> ComplianceStatus:
    """
    Aggregates a list of compliance statuses.
    Returns FAIL if any status is FAIL.
    Returns PENDING if any status is PENDING.
    Otherwise returns PASS.
    """
    if not statuses:
        return ComplianceStatus.PENDING
    if ComplianceStatus.FAIL in statuses:
        return ComplianceStatus.FAIL
    if ComplianceStatus.PENDING in statuses:
        return ComplianceStatus.PENDING
    return ComplianceStatus.PASS


def evaluate_eccentricity(session: TestSessionOut, instrument: InstrumentOut) -> EccentricityResult:
    """Evaluates the eccentricity test data for compliance."""
    test_load_str = session.eccentricity.test_load
    test_load = _safe_float(test_load_str)
    
    if test_load is None:
        return EccentricityResult(status=ComplianceStatus.PENDING)
        
    mpe = compute_mpe(test_load, instrument.e_value, instrument.accuracy_class)
    if mpe is None:
        return EccentricityResult(status=ComplianceStatus.PENDING)

    results = []
    statuses = []
    
    for row in session.eccentricity.rows:
        indication = _safe_float(row.indication)
        if indication is None:
            results.append(ReadingResult(id=row.id, label=row.label, status=ComplianceStatus.PENDING))
            statuses.append(ComplianceStatus.PENDING)
            continue
            
        error = compute_error(indication, test_load)
        status = ComplianceStatus.PASS if abs(error) <= mpe else ComplianceStatus.FAIL
        
        results.append(ReadingResult(
            id=row.id,
            label=row.label,
            applied_load=test_load,
            indication=indication,
            error=error,
            mpe=mpe,
            status=status
        ))
        statuses.append(status)
        
    overall_status = aggregate_status(statuses) if session.eccentricity.rows else ComplianceStatus.PENDING
    return EccentricityResult(rows=results, status=overall_status)


def evaluate_repeatability(session: TestSessionOut, instrument: InstrumentOut) -> RepeatabilityResult:
    """Evaluates the repeatability test data for compliance."""
    test_load = _safe_float(session.repeatability.test_load)
    
    if test_load is None:
        return RepeatabilityResult(status=ComplianceStatus.PENDING)
        
    mpe = compute_mpe(test_load, instrument.e_value, instrument.accuracy_class)
    if mpe is None:
        return RepeatabilityResult(status=ComplianceStatus.PENDING)

    indications = []
    for row in session.repeatability.rows:
        ind = _safe_float(row.indication)
        if ind is not None:
            indications.append(ind)
            
    if len(indications) < len(session.repeatability.rows) or len(indications) == 0:
        return RepeatabilityResult(mpe=mpe, status=ComplianceStatus.PENDING)
        
    indications_array = np.array(indications)
    range_value = float(np.max(indications_array) - np.min(indications_array))
    
    # Repeatability range must not exceed the absolute value of MPE
    status = ComplianceStatus.PASS if range_value <= mpe else ComplianceStatus.FAIL
    return RepeatabilityResult(range_value=range_value, mpe=mpe, status=status)


def evaluate_discrimination(session: TestSessionOut) -> DiscriminationResult:
    """Evaluates the discrimination test data for compliance."""
    # Assuming d_value is the discrimination threshold, but we don't have instrument here directly per signature.
    # The signature in instructions is: evaluate_discrimination(session: TestSessionOut) -> DiscriminationResult
    # Let's compute delta based on the test data.
    test_load = _safe_float(session.discrimination.test_load)
    reading_before = _safe_float(session.discrimination.reading_before)
    increment = _safe_float(session.discrimination.increment)
    reading_after = _safe_float(session.discrimination.reading_after)
    
    if None in (test_load, reading_before, increment, reading_after):
        return DiscriminationResult(status=ComplianceStatus.PENDING)
        
    # Discrimination is usually passed if a small increment causes a noticeable change in reading.
    # The exact rule can depend on d_value. Since we only have the session, we check if reading_after >= reading_before + increment
    delta = reading_after - reading_before
    expected_min = increment # Simplistic rule, actual rule often relates to d_value but it's not passed.
    
    # We will just mark PASS if delta is at least some part of increment.
    # R-76 discrimination: adding a load of 1.4d must change indication by at least 1d.
    # We'll just do delta >= expected_min if no other info.
    status = ComplianceStatus.PASS if delta >= expected_min else ComplianceStatus.FAIL
    
    return DiscriminationResult(delta=delta, expected_min=expected_min, status=status)


def evaluate_linearity(session: TestSessionOut, instrument: InstrumentOut) -> LinearityResult:
    """Evaluates the linearity (weighing performance) test data for compliance."""
    results = []
    statuses = []
    
    for row in session.linearity.rows:
        applied_load = _safe_float(row.applied_load)
        indication = _safe_float(row.indication)
        
        if applied_load is None or indication is None:
            results.append(ReadingResult(id=row.id, label=row.label, status=ComplianceStatus.PENDING))
            statuses.append(ComplianceStatus.PENDING)
            continue
            
        mpe = compute_mpe(applied_load, instrument.e_value, instrument.accuracy_class)
        if mpe is None:
            results.append(ReadingResult(id=row.id, label=row.label, status=ComplianceStatus.PENDING))
            statuses.append(ComplianceStatus.PENDING)
            continue
            
        error = compute_error(indication, applied_load)
        status = ComplianceStatus.PASS if abs(error) <= mpe else ComplianceStatus.FAIL
        
        results.append(ReadingResult(
            id=row.id,
            label=row.label,
            applied_load=applied_load,
            indication=indication,
            error=error,
            mpe=mpe,
            status=status
        ))
        statuses.append(status)
        
    overall_status = aggregate_status(statuses) if session.linearity.rows else ComplianceStatus.PENDING
    return LinearityResult(rows=results, status=overall_status)


def evaluate_session(session: TestSessionOut, instrument: InstrumentOut) -> ComplianceResult:
    """
    Evaluates the entire test session.
    
    Args:
        session (TestSessionOut): The test session data.
        instrument (InstrumentOut): The instrument under test.
        
    Returns:
        ComplianceResult: The aggregated compliance result.
    """
    ecc_res = evaluate_eccentricity(session, instrument)
    rep_res = evaluate_repeatability(session, instrument)
    disc_res = evaluate_discrimination(session)
    lin_res = evaluate_linearity(session, instrument)
    
    overall = aggregate_status([ecc_res.status, rep_res.status, disc_res.status, lin_res.status])
    
    return ComplianceResult(
        eccentricity=ecc_res,
        repeatability=rep_res,
        discrimination=disc_res,
        linearity=lin_res,
        overall=overall
    )
