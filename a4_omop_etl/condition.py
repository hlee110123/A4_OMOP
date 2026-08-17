"""
Physical & Neurological Exam findings from phyneuro.csv.

Routing follows OMOP CDM v5.4 domain conventions:
- Abnormal exam findings (value=2) -> CONDITION_OCCURRENCE.
  Concepts are SNOMED Clinical Findings in the Condition domain.
- Normal findings (value=1) -> dropped from output. OMOP convention
  treats absence of disease as inferable from absence of a condition row;
  exam completion is implicit from visit_occurrence + DONE=1.
- 'Not examined' (value=3) -> skipped.
- Edema severity (PXEDSEV, ordinal 0-4) -> MEASUREMENT (custom concept).
"""

import pandas as pd

from . import concepts
from .helpers import prepare_source_df, finalize_measurement_df


def create_phyneuro_observations_and_measurements(
    phyneuro_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame
) -> tuple:
    """
    Create OMOP CONDITION_OCCURRENCE + MEASUREMENT records from phyneuro.csv.

    Source: phyneuro.csv | Date: visit_start_date

    Field Mappings (concept_maps/conditions.csv):
        CONDITION_OCCURRENCE — 16 exam fields, only when value=2 (Abnormal):
            Physical: PXHEADEY, PXCARD, PXPULM, PXABDOM, PXMUSCUL,
                      PXEDEMA, PXSKIN, PXOTHER
            Neuro:    NXGAIT, NXMOTOR, NXSENSOR, NXTREMOR, NXFINGER,
                      NXHEEL, NXNERVE, NXOTHER

        MEASUREMENT:
            PXEDSEV -> Edema Severity Score (custom 2100000500, ordinal 0-4)

    Returns:
        (condition_occurrence_df, measurement_df)
    """
    PHYNEURO_CONCEPTS = concepts.load_condition_concepts()

    # DONE is only populated at follow-up visits; at screening (VISCODE=1) the CRF
    # omits it entirely. Treat missing as done — verified: those 5,695 rows carry a
    # median 16/16 exam fields, while DONE==0 rows carry none.
    phyneuro_filtered = phyneuro_df[phyneuro_df['DONE'].fillna(1) == 1].copy()
    print(f"  Phyneuro: {len(phyneuro_df)} total -> {len(phyneuro_filtered)} (DONE=1 or missing)")

    phyneuro_merged = prepare_source_df(phyneuro_filtered, person_df, date_anchor_df,
                                        visit_occurrence_df, visit_extra_cols=['visit_start_date'])

    # All 16 exam finding fields (1=Normal, 2=Abnormal, 3=Not examined)
    physical_fields = ['PXHEADEY', 'PXCARD', 'PXPULM', 'PXABDOM', 'PXMUSCUL', 'PXEDEMA', 'PXSKIN', 'PXOTHER']
    neuro_fields = ['NXGAIT', 'NXMOTOR', 'NXSENSOR', 'NXTREMOR', 'NXFINGER', 'NXHEEL', 'NXNERVE', 'NXOTHER']
    all_exam_fields = physical_fields + neuro_fields

    conditions = []
    measurements = []

    for _, row in phyneuro_merged.iterrows():
        cond_date = row.get('visit_start_date')
        if pd.isna(cond_date):
            cond_date = row.get('synthetic_consent_date')

        for field in all_exam_fields:
            val = row.get(field)
            if pd.notna(val) and val == 2:
                concept_info = PHYNEURO_CONCEPTS.get(field, {'concept_id': 0, 'name': field})
                conditions.append({
                    'person_id': row['person_id'],
                    'condition_concept_id': concept_info['concept_id'],
                    'condition_start_date': cond_date,
                    'condition_end_date': None,  # point-in-time finding
                    'visit_occurrence_id': row.get('visit_occurrence_id'),
                    'condition_source_value': f'PHYNEURO:{field}=Abnormal',
                })

        # PXEDSEV ordinal severity (0=Trace through 4=4+)
        if pd.notna(row.get('PXEDSEV')):
            edsev_concept = PHYNEURO_CONCEPTS.get('PXEDSEV', {'concept_id': 2100000500, 'name': 'Edema Severity'})
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': edsev_concept['concept_id'],
                'measurement_date': cond_date,
                'value_as_number': float(row['PXEDSEV']),
                'unit_source_value': 'grade',
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f'PHYNEURO:PXEDSEV={int(row["PXEDSEV"])}',
            })

    # Build CONDITION_OCCURRENCE DataFrame with all OMOP CDM v5.4 boilerplate
    condition_df = pd.DataFrame(conditions) if conditions else pd.DataFrame()
    if len(condition_df) > 0:
        condition_df['condition_occurrence_id'] = range(1, 1 + len(condition_df))
        condition_df['condition_type_concept_id'] = 32809  # Case Report Form
        condition_df['condition_start_datetime'] = None
        condition_df['condition_end_datetime'] = None
        condition_df['stop_reason'] = None
        condition_df['provider_id'] = None
        condition_df['visit_detail_id'] = None
        condition_df['condition_source_concept_id'] = 0
        condition_df['condition_status_source_value'] = None
        condition_df['condition_status_concept_id'] = 0
        # Reorder columns to standard OMOP order
        condition_df = condition_df[[
            'condition_occurrence_id', 'person_id', 'condition_concept_id',
            'condition_start_date', 'condition_start_datetime',
            'condition_end_date', 'condition_end_datetime',
            'condition_type_concept_id', 'stop_reason', 'provider_id',
            'visit_occurrence_id', 'visit_detail_id',
            'condition_source_value', 'condition_source_concept_id',
            'condition_status_source_value', 'condition_status_concept_id',
        ]]

    # Build measurement DataFrame
    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"  Created {len(condition_df)} phyneuro condition_occurrence records (Abnormal findings)")
    print(f"  Created {len(measurement_df)} phyneuro measurements (PXEDSEV)")

    return condition_df, measurement_df
