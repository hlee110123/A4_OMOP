"""
Questionnaire observations — AD Concern items and ADLPQ item-level responses.

Numeric total scores (GDTOTAL, STAITOTAL, ASSCORE, AISCORE, IESCORE)
have been moved to MEASUREMENT domain per OMOP CDM alignment.
AD Concern items remain in OBSERVATION as qualitative concern ratings.
ADLPQ individual items are categorical functional assessments.
"""

import pandas as pd
from . import concepts
from .helpers import prepare_source_df, build_observation_record, finalize_observation_df

QUESTIONNAIRE_CONCEPTS = concepts.load_questionnaire_concepts()
ADLPQ_ITEM_CONCEPTS = concepts.load_adlpq_item_concepts()


def create_observation_questionnaires(
    concerns_df: pd.DataFrame,
    adlpq_df: pd.DataFrame,
    psychwell_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION records from questionnaire files.

    Sources: concerns.csv (AD Concerns), adlpq.csv (ADL-PQ items),
             psychwell.csv (GDS individual items)
    Filter: DONE=1/Yes | Date: visit_start_date

    Field Mappings (concept_maps/questionnaires.csv):
        group=primary:
            AD Concerns: CADDVLP (2100000062), CADKNOW (2100000063),
                         CADBLIEV (2100000064), CADWRST (2100000065),
                         CADCNCRN (2100000066)
            GDS items (15): LOINC 3048xxx-3053xxx (binary 0/1 depression screen)
        group=adlpq_item:
            19 individual ADL-PQ items (CDISC/SNOMED/custom concepts)
            from reviewer mapping spreadsheet

    Note: GDTOTAL/STAITOTAL/ASSCORE/AISCORE totals moved to measurement domain.
    """
    observations = []

    # --- AD Concern items ---
    filtered = concerns_df.copy()
    print(f"  AD Concerns: {len(filtered)} total")

    merged = prepare_source_df(filtered, person_df, date_anchor_df, visit_occurrence_df,
                                visit_extra_cols=['visit_start_date'])

    concern_fields = ['CADDVLP', 'CADKNOW', 'CADBLIEV', 'CADWRST', 'CADCNCRN']
    concern_count = 0
    for _, row in merged.iterrows():
        for field in concern_fields:
            if field in row and pd.notna(row[field]):
                concept = QUESTIONNAIRE_CONCEPTS.get(field, {'concept_id': 0, 'name': field, 'unit': 'score'})

                obs_date = row.get('visit_start_date')
                if pd.isna(obs_date):
                    obs_date = row['synthetic_consent_date']

                observations.append(build_observation_record(
                    person_id=row['person_id'],
                    observation_concept_id=concept['concept_id'],
                    observation_date=obs_date,
                    value_as_number=float(row[field]),
                    value_as_string=f"{concept.get('name', field)}: {row[field]}",
                    visit_occurrence_id=row.get('visit_occurrence_id'),
                    observation_source_value=f"CONCERNS:{field}",
                    unit_source_value=concept.get('unit', 'score'),
                ))
                concern_count += 1

    # --- ADLPQ item-level responses ---
    adlpq_filtered = adlpq_df[adlpq_df['DONE'] == 'Yes'].copy() if 'DONE' in adlpq_df.columns else adlpq_df.copy()
    print(f"  ADLPQ items: {len(adlpq_df)} total -> {len(adlpq_filtered)} (DONE=Yes)")

    adlpq_merged = prepare_source_df(adlpq_filtered, person_df, date_anchor_df, visit_occurrence_df,
                                      visit_extra_cols=['visit_start_date'])

    # Binary Yes/No items get value_as_concept_id (4188539=Yes, 4188540=No)
    adlpq_binary_fields = {'ASCELL', 'ASCELLUSE', 'ASCALL', 'ASTEXT'}

    adlpq_count = 0
    for _, row in adlpq_merged.iterrows():
        for field, concept in ADLPQ_ITEM_CONCEPTS.items():
            if field in row and pd.notna(row[field]):
                obs_date = row.get('visit_start_date')
                if pd.isna(obs_date):
                    obs_date = row['synthetic_consent_date']

                val_str = str(row[field])
                val_concept_id = None
                if field in adlpq_binary_fields:
                    val_concept_id = 4188539 if val_str == 'Yes' else 4188540 if val_str == 'No' else 0

                observations.append(build_observation_record(
                    person_id=row['person_id'],
                    observation_concept_id=concept['concept_id'],
                    observation_date=obs_date,
                    value_as_string=val_str,
                    value_as_concept_id=val_concept_id,
                    visit_occurrence_id=row.get('visit_occurrence_id'),
                    observation_source_value=f"ADLPQ:{field}",
                ))
                adlpq_count += 1

    # --- GDS individual items (binary Yes/No depression screen) ---
    gds_filtered = psychwell_df[psychwell_df['DONE'] == 1].copy() if 'DONE' in psychwell_df.columns else psychwell_df.copy()
    print(f"  GDS items: {len(psychwell_df)} total -> {len(gds_filtered)} (DONE=1)")

    gds_merged = prepare_source_df(gds_filtered, person_df, date_anchor_df, visit_occurrence_df,
                                    visit_extra_cols=['visit_start_date'])

    gds_fields = [k for k in QUESTIONNAIRE_CONCEPTS if k.startswith('GD') and k != 'GDTOTAL']

    gds_count = 0
    for _, row in gds_merged.iterrows():
        for field in gds_fields:
            if field in row and pd.notna(row[field]):
                concept = QUESTIONNAIRE_CONCEPTS[field]

                obs_date = row.get('visit_start_date')
                if pd.isna(obs_date):
                    obs_date = row['synthetic_consent_date']

                val = int(row[field])
                observations.append(build_observation_record(
                    person_id=row['person_id'],
                    observation_concept_id=concept['concept_id'],
                    observation_date=obs_date,
                    value_as_number=float(val),
                    value_as_string='Yes' if val == 1 else 'No',
                    value_as_concept_id=4188539 if val == 1 else 4188540,
                    visit_occurrence_id=row.get('visit_occurrence_id'),
                    observation_source_value=f"PSYCHWELL:{field}",
                ))
                gds_count += 1

    observation_df = pd.DataFrame(observations) if observations else pd.DataFrame()
    observation_df = finalize_observation_df(observation_df)

    print(f"Created questionnaire OBSERVATION with {len(observation_df)} records (AD Concerns: {concern_count}, ADLPQ items: {adlpq_count}, GDS items: {gds_count})")
    return observation_df
