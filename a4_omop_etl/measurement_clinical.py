"""
Clinical measurement ETL functions.

Transforms vitals, labs, and ECG data into OMOP MEASUREMENT records.
"""

import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date, finalize_measurement_df, concat_and_assign_ids


def create_measurement_vitals(
    vitals_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from vitals.csv.

    Source: vitals.csv | Filter: DONE=1 | Date: visit_start_date

    Field Mappings (concept_maps/vitals.csv):
        STDWT    -> Weight (3025315, kg)
        STDHT    -> Height (3036277, cm)
        VSBPSYS  -> Systolic BP (3004249, mmHg)
        VSBPDIA  -> Diastolic BP (3012888, mmHg)
        VSPULSE  -> Heart rate (3027018, beats/min)
        VSRESP   -> Respiratory rate (3024171, breaths/min)
        STDTEMP  -> Temperature (3020891, Cel)
    """
    VITALS_CONCEPTS = concepts.load_vitals_concepts()

    # Filter to completed vitals only (DONE = 1)
    vitals_filtered = vitals_df[vitals_df['DONE'] == 1].copy()
    print(f"  Vitals: {len(vitals_df)} total -> {len(vitals_filtered)} (DONE=1)")

    vitals_filtered = prepare_source_df(vitals_filtered, person_df, date_anchor_df,
                                         visit_occurrence_df, visit_extra_cols=['visit_start_date'])

    # Melt vitals into long format (one row per measurement)
    vital_cols = ['STDWT', 'STDHT', 'VSBPSYS', 'VSBPDIA', 'VSPULSE', 'VSRESP', 'STDTEMP']
    measurements = []

    for _, row in vitals_filtered.iterrows():
        for col in vital_cols:
            if pd.notna(row.get(col)):
                concept = VITALS_CONCEPTS.get(col, {})
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': concept.get('concept_id', 0),
                    'measurement_date': row.get('visit_start_date'),
                    'value_as_number': float(row[col]),
                    'unit_source_value': concept.get('unit', ''),
                    'visit_occurrence_id': row.get('visit_occurrence_id'),
                    'measurement_source_value': col,
                    'unit_concept_id': concept.get('unit_concept_id', 0),
                    'value_source_value': str(row[col]),
                })

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"  Created {len(measurement_df)} vital sign measurements")
    return measurement_df


def create_measurement_labs(
    labs_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from clrm_lab.csv.

    Source: clrm_lab.csv | Filter: TSTSTAT='D' | Date: LBDTM_DAYS_CONSENT

    Field Mappings (concept_maps/labs.csv, 97 entries):
        LBTESTCD lookup -> concept_id (hematology, chemistry,
        urinalysis, coagulation, immunology, drug-related panels)
        value_as_number = LBORRES (numeric) or LBSTRESN
    """
    LAB_CONCEPTS = concepts.load_lab_concepts()

    # Filter to completed tests only
    labs_filtered = labs_df[labs_df['TSTSTAT'] == 'D'].copy()
    print(f"  Labs: {len(labs_df)} total -> {len(labs_filtered)} (TSTSTAT='D')")

    labs_filtered = prepare_source_df(labs_filtered, person_df, date_anchor_df, visit_occurrence_df)
    labs_filtered['measurement_date'] = labs_filtered.apply(
        calc_days_to_date, args=('LBDTM_DAYS_CONSENT',), axis=1
    )

    # Map to OMOP concepts
    labs_filtered['measurement_concept_id'] = labs_filtered['LBTESTCD'].map(LAB_CONCEPTS).fillna(0).astype(int)

    # Build measurement records
    measurement_df = pd.DataFrame({
        'person_id': labs_filtered['person_id'],
        'measurement_concept_id': labs_filtered['measurement_concept_id'],
        'measurement_date': labs_filtered['measurement_date'],
        'value_as_number': pd.to_numeric(labs_filtered['SIRESN'], errors='coerce'),
        'range_low': pd.to_numeric(labs_filtered['SINRLO'], errors='coerce'),
        'range_high': pd.to_numeric(labs_filtered['SINRHI'], errors='coerce'),
        'visit_occurrence_id': labs_filtered['visit_occurrence_id'],
        'measurement_source_value': labs_filtered['LBTESTCD'] + ': ' + labs_filtered['LBTEST'],
        'unit_source_value': labs_filtered['SIU'],
        'value_source_value': labs_filtered['SIRESC'].astype(str),
    })
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"  Created {len(measurement_df)} lab measurements")
    return measurement_df


def create_measurement_ecg(
    ecg_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from clrm_ecg.csv.

    Source: clrm_ecg.csv | Filter: TSTSTAT='D', numeric tests | Date: LBDTM_DAYS_CONSENT

    Field Mappings (concept_maps/ecg.csv):
        RATE -> Heart rate (3027018, beats/min)
        QT   -> QT interval (4116637, ms)
        QRS  -> QRS duration (3022022, ms)
        PR   -> PR interval (4092020, ms)
        RR   -> R-R interval (3013078, ms)
    """
    ECG_CONCEPTS = concepts.load_ecg_concepts()

    # Filter to numeric ECG measurements only (exclude text assessments)
    numeric_tests = ['RATE', 'QT', 'QRS', 'PR', 'RR']
    ecg_filtered = ecg_df[
        (ecg_df['TSTSTAT'] == 'D') &
        (ecg_df['LBTESTCD'].isin(numeric_tests))
    ].copy()
    print(f"  ECG: {len(ecg_df)} total -> {len(ecg_filtered)} (numeric measurements)")

    ecg_filtered = prepare_source_df(ecg_filtered, person_df, date_anchor_df, visit_occurrence_df)
    ecg_filtered['measurement_date'] = ecg_filtered.apply(
        calc_days_to_date, args=('LBDTM_DAYS_CONSENT',), axis=1
    )

    # Map to OMOP concepts
    ecg_filtered['measurement_concept_id'] = ecg_filtered['LBTESTCD'].apply(
        lambda x: ECG_CONCEPTS.get(x, {}).get('concept_id', 0)
    )

    # Build measurement records
    measurement_df = pd.DataFrame({
        'person_id': ecg_filtered['person_id'],
        'measurement_concept_id': ecg_filtered['measurement_concept_id'],
        'measurement_date': ecg_filtered['measurement_date'],
        'value_as_number': pd.to_numeric(ecg_filtered['SIRESN'], errors='coerce'),
        'range_low': pd.to_numeric(ecg_filtered['SINRLO'], errors='coerce'),
        'range_high': pd.to_numeric(ecg_filtered['SINRHI'], errors='coerce'),
        'visit_occurrence_id': ecg_filtered['visit_occurrence_id'],
        'measurement_source_value': ecg_filtered['LBTESTCD'] + ': ' + ecg_filtered['LBTEST'],
        'unit_source_value': ecg_filtered['SIU'],
        'value_source_value': ecg_filtered['SIRESC'].astype(str),
    })
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"  Created {len(measurement_df)} ECG measurements")
    return measurement_df


def create_measurement_clinical(
    vitals_df: pd.DataFrame,
    labs_df: pd.DataFrame,
    ecg_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Create combined OMOP MEASUREMENT table from clinical sources.

    Combines vitals, labs, and ECG into single MEASUREMENT table.
    """
    vitals_meas = create_measurement_vitals(
        vitals_df, person_df, visit_occurrence_df, date_anchor_df
    )

    labs_meas = create_measurement_labs(
        labs_df, person_df, visit_occurrence_df, date_anchor_df
    )

    ecg_meas = create_measurement_ecg(
        ecg_df, person_df, visit_occurrence_df, date_anchor_df
    )

    # Combine all measurements
    measurement = concat_and_assign_ids([vitals_meas, labs_meas, ecg_meas], 'measurement_id')

    print(f"Created MEASUREMENT table with {len(measurement)} total records")
    print(f"  - Vitals: {len(vitals_meas)}, Labs: {len(labs_meas)}, ECG: {len(ecg_meas)}")

    return measurement
