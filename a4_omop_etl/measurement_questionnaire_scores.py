"""
Questionnaire score measurements — numeric totals moved from OBSERVATION.

Per OMOP CDM alignment, numeric instrument total scores belong in MEASUREMENT:
- GDTOTAL (GDS total 0-15)
- STAITOTAL (STAI total)
- ASSCORE (ADL-PQ patient total)
- AISCORE (ADL-PQ study partner total)
- IESCORE (Impact of Events Scale total)
- BR1NIGHT (hospital overnight stay count)
- INFHRS (study partner contact hours)
"""

import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date, finalize_measurement_df


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
        psychwell -> GDTOTAL (3051694, GDS total) | STAITOTAL (2100000060, STAI total)
        adlpq    -> ASSCORE (2100000061, ADL-PQ patient total)
        adlpqsp  -> AISCORE (2100000067, ADL-PQ study partner total)
        ies      -> IESCORE (1761510, IES-R total) | Date: IEDATE_DAYS_CONSENT
        ruib1    -> BR1NIGHT (2100000208, hospital overnight stays)
        spinfo   -> INFHRS (2100000081, study partner contact hours/week)
    """
    MEAS_CONCEPTS = concepts.load_questionnaire_measurement_concepts()
    OBS_MEAS_CONCEPTS = concepts.load_measurement_from_observations()

    measurements = []

    def _add_measurement(row, field, concept, source_prefix, meas_date=None):
        """Append a measurement row from a concept dict entry."""
        if meas_date is None:
            meas_date = row.get('visit_start_date')
            if pd.isna(meas_date):
                meas_date = row.get('synthetic_consent_date')

        measurements.append({
            'person_id': row['person_id'],
            'measurement_concept_id': concept['concept_id'],
            'measurement_date': meas_date,
            'value_as_number': float(row[field]),
            'unit_source_value': concept.get('unit', 'score'),
            'visit_occurrence_id': row.get('visit_occurrence_id'),
            'measurement_source_value': f'{source_prefix}:{field}',
        })

    # --- GDS Total + STAI Total from psychwell ---
    psych_merged = prepare_source_df(psychwell_df[psychwell_df['DONE'] == 1].copy() if 'DONE' in psychwell_df.columns else psychwell_df.copy(),
                                      person_df, date_anchor_df, visit_occurrence_df, visit_extra_cols=['visit_start_date'])
    print(f"  PSYCHWELL: {len(psychwell_df)} total -> {len(psych_merged)} valid")
    gds_count = stai_count = 0
    for _, row in psych_merged.iterrows():
        if pd.notna(row.get('GDTOTAL')):
            _add_measurement(row, 'GDTOTAL', MEAS_CONCEPTS['GDTOTAL'], 'PSYCHWELL')
            gds_count += 1
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

    # --- IES Total Score ---
    ies_done = ies_df[ies_df['DONE'] == 1].copy() if 'DONE' in ies_df.columns else ies_df.copy()
    ies_merged = prepare_source_df(ies_done, person_df, date_anchor_df)
    print(f"  IES: {len(ies_df)} total -> {len(ies_merged)} valid")
    ies_count = 0
    for _, row in ies_merged.iterrows():
        if pd.notna(row.get('IESCORE')):
            meas_date = calc_days_to_date(row, 'IEDATE_DAYS_CONSENT') or row['synthetic_consent_date']
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': MEAS_CONCEPTS['IESCORE']['concept_id'],
                'measurement_date': meas_date,
                'value_as_number': float(row['IESCORE']),
                'unit_source_value': 'score',
                'visit_occurrence_id': None,
                'measurement_source_value': f"IES:IESCORE:{row.get('VISCODE', 'NA')}",
            })
            ies_count += 1

    # --- BR1NIGHT (hospital overnight stays count) ---
    ruib1_merged = prepare_source_df(ruib1_df, person_df, date_anchor_df, visit_occurrence_df,
                                     visit_extra_cols=['visit_start_date'])
    print(f"  RUIB1: {len(ruib1_df)} total -> {len(ruib1_merged)} matched")
    ruib1_count = 0
    for _, row in ruib1_merged.iterrows():
        if pd.notna(row.get('BR1NIGHT')):
            meas_date = row.get('visit_start_date') if pd.notna(row.get('visit_start_date')) else row['synthetic_consent_date']
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
        if pd.notna(row.get('INFHRS')) and row.get('INFHRS') > 0:
            meas_date = row.get('visit_start_date') if pd.notna(row.get('visit_start_date')) else row['synthetic_consent_date']
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
    print(f"  GDS: {gds_count}, STAI: {stai_count}, ADL-PQ: {adlpq_count}, ADL-PQ SP: {adlpqsp_count}")
    print(f"  IES: {ies_count}, BR1NIGHT: {ruib1_count}, INFHRS: {infhrs_count}")

    return measurement_df
