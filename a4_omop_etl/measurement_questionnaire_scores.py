"""
Questionnaire score measurements — numeric totals moved from OBSERVATION.

Measurement-domain totals and counts:
- STAITOTAL (STAI state score, 40219573)
- ASSCORE (ADL-PQ patient total)
- AISCORE (ADL-PQ study partner total)
- BR1NIGHT (hospital overnight stay count)
- INFHRS (study partner contact hours)
GDTOTAL and IESCORE have Observation-domain concepts and are emitted as
OBSERVATION in observation_questionnaires.py / observation.py.
"""

import pandas as pd

from . import concepts
from .helpers import prepare_source_df, finalize_measurement_df


def create_measurement_questionnaire_scores(
    psychwell_df: pd.DataFrame,
    adlpq_df: pd.DataFrame,
    adlpqsp_df: pd.DataFrame,
    ies_df: pd.DataFrame,
    ruib1_df: pd.DataFrame,
    spinfo_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records for numeric questionnaire scores
    that were moved from OBSERVATION domain.

    Sources & Field Mappings (concept_maps/questionnaires.csv group=measurement,
                              concept_maps/observations.csv group=measurement):
        psychwell -> STAITOTAL (40219573, STAI state score)
        adlpq    -> ASSCORE (2100000061, ADL-PQ patient total)
        adlpqsp  -> AISCORE (2100000067, ADL-PQ study partner total)
        ruib1    -> BR1NIGHT (2100000208, hospital overnight stays)
        spinfo   -> INFHRS (2100000081, study partner contact hours/week)
    """
    MEAS_CONCEPTS = concepts.load_questionnaire_measurement_concepts()
    OBS_MEAS_CONCEPTS = concepts.load_measurement_from_observations()

    measurements = []

    def _add_measurement(row, field, concept, source_prefix, meas_date=None):
        """Append a measurement row from a concept dict entry."""
        if meas_date is None:
            # Dated by the visit; Not-Done visits contribute their SV
            # window-end date via build_visit_linkage (NULL visit id). No
            # consent-date fallback — truly undated rows drop-and-report.
            meas_date = row.get('visit_start_date')

        measurements.append({
            'person_id': row['person_id'],
            'measurement_concept_id': concept['concept_id'],
            'measurement_date': meas_date,
            'value_as_number': float(row[field]),
            'unit_source_value': concept.get('unit', 'score'),
            'visit_occurrence_id': row.get('visit_occurrence_id'),
            'measurement_source_value': f'{source_prefix}:{field}',
        })

    # --- STAI Total from psychwell ---
    psych_merged = prepare_source_df(psychwell_df[psychwell_df['DONE'] == 1].copy() if 'DONE' in psychwell_df.columns else psychwell_df.copy(),
                                      person_df, date_anchor_df, visit_occurrence_df, visit_extra_cols=['visit_start_date'])
    print(f"  PSYCHWELL: {len(psychwell_df)} total -> {len(psych_merged)} valid")
    stai_count = 0
    for _, row in psych_merged.iterrows():
        # GDTOTAL is emitted as OBSERVATION (Observation-domain concept)
        # in observation_questionnaires.py, alongside the GDS items.
        if pd.notna(row.get('STAITOTAL')):
            _add_measurement(row, 'STAITOTAL', MEAS_CONCEPTS['STAITOTAL'], 'PSYCHWELL')
            stai_count += 1

    # --- ADL-PQ Patient Score ---
    adlpq_merged = prepare_source_df(adlpq_df[adlpq_df['DONE'] == 'Yes'].copy() if 'DONE' in adlpq_df.columns else adlpq_df.copy(),
                                      person_df, date_anchor_df, visit_occurrence_df, visit_extra_cols=['visit_start_date'])
    print(f"  ADLPQ: {len(adlpq_df)} total -> {len(adlpq_merged)} valid")
    adlpq_count = 0
    for _, row in adlpq_merged.iterrows():
        if pd.notna(row.get('ASSCORE')):
            _add_measurement(row, 'ASSCORE', MEAS_CONCEPTS['ASSCORE'], 'ADLPQ')
            adlpq_count += 1

    # --- ADL-PQ Study Partner Score ---
    adlpqsp_merged = prepare_source_df(adlpqsp_df[adlpqsp_df['DONE'] == 'Yes'].copy() if 'DONE' in adlpqsp_df.columns else adlpqsp_df.copy(),
                                        person_df, date_anchor_df, visit_occurrence_df, visit_extra_cols=['visit_start_date'])
    print(f"  ADLPQSP: {len(adlpqsp_df)} total -> {len(adlpqsp_merged)} valid")
    adlpqsp_count = 0
    for _, row in adlpqsp_merged.iterrows():
        if pd.notna(row.get('AISCORE')):
            _add_measurement(row, 'AISCORE', MEAS_CONCEPTS['AISCORE'], 'ADLPQSP')
            adlpqsp_count += 1

    # IESCORE is emitted as OBSERVATION (Observation-domain concept)
    # in observation.py, alongside the IES items.

    # --- BR1NIGHT (hospital overnight stays count) ---
    ruib1_merged = prepare_source_df(ruib1_df, person_df, date_anchor_df, visit_occurrence_df,
                                     visit_extra_cols=['visit_start_date'])
    print(f"  RUIB1: {len(ruib1_df)} total -> {len(ruib1_merged)} matched")
    ruib1_count = 0
    for _, row in ruib1_merged.iterrows():
        if pd.notna(row.get('BR1NIGHT')):
            # Dated by the visit (incl. Not-Done window-end dates); truly
            # undated rows drop-and-report downstream.
            meas_date = row.get('visit_start_date')
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': MEAS_CONCEPTS['RUIB1_NIGHTS']['concept_id'],
                'measurement_date': meas_date,
                'value_as_number': float(row['BR1NIGHT']),
                'unit_source_value': 'nights',
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"RUIB1:BR1NIGHT:{row.get('VISCODE', 'NA')}",
            })
            ruib1_count += 1

    # --- INFHRS (study partner contact hours) ---
    sp_merged = prepare_source_df(spinfo_df, person_df, date_anchor_df, visit_occurrence_df,
                                  visit_extra_cols=['visit_start_date'])
    print(f"  SPINFO (INFHRS): {len(spinfo_df)} total -> {len(sp_merged)} matched")
    infhrs_count = 0
    for _, row in sp_merged.iterrows():
        # Dictionary range is 0..168: zero in-person hours is a valid answer.
        if pd.notna(row.get('INFHRS')) and row.get('INFHRS') >= 0:
            # Dated by the visit (incl. Not-Done window-end dates); truly
            # undated rows drop-and-report downstream.
            meas_date = row.get('visit_start_date')
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': OBS_MEAS_CONCEPTS['CONTACT_HRS']['concept_id'],
                'measurement_date': meas_date,
                'value_as_number': float(row['INFHRS']),
                'unit_source_value': 'hours/week',
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"SPINFO:INFHRS:BPID={row.get('BPID', 'NA')}",
            })
            infhrs_count += 1

    # Build DataFrame
    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"Created questionnaire score MEASUREMENT with {len(measurement_df)} records")
    print(f"  STAI: {stai_count}, ADL-PQ: {adlpq_count}, ADL-PQ SP: {adlpqsp_count}")

    return measurement_df
