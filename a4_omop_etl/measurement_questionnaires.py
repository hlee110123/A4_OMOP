"""Questionnaire measurement records (PSYCHWELL, ADLPQ, ADLPQSP, CONCERNS)."""

import pandas as pd
from . import concepts
from .helpers import prepare_source_df

QUESTIONNAIRE_CONCEPTS = concepts.load_questionnaire_concepts()


def create_measurement_questionnaires(
    psychwell_df: pd.DataFrame,
    adlpq_df: pd.DataFrame,
    adlpqsp_df: pd.DataFrame,
    concerns_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create OMOP MEASUREMENT records from questionnaire files."""
    measurements = []

    def process_questionnaire(df, score_fields, file_name, done_val=1):
        nonlocal measurements
        if 'DONE' in df.columns:
            filtered = df[df['DONE'] == done_val].copy()
        else:
            filtered = df.copy()
        print(f"  {file_name}: {len(df)} total -> {len(filtered)} valid")

        merged = prepare_source_df(filtered, person_df, date_anchor_df, visit_occurrence_df,
                                    visit_extra_cols=['visit_start_date'])

        count = 0
        for _, row in merged.iterrows():
            for field in score_fields:
                if field in row and pd.notna(row[field]):
                    concept = QUESTIONNAIRE_CONCEPTS.get(field, {'concept_id': 0, 'name': field, 'unit': 'score'})
                    meas_date = row.get('visit_start_date') if pd.notna(row.get('visit_start_date')) else row['synthetic_consent_date']
                    measurements.append({
                        'person_id': row['person_id'],
                        'measurement_concept_id': concept['concept_id'],
                        'measurement_date': meas_date,
                        'value_as_number': float(row[field]),
                        'unit_source_value': concept['unit'],
                        'visit_occurrence_id': row.get('visit_occurrence_id'),
                        'measurement_source_value': f"{file_name}:{field}",
                    })
                    count += 1
        return count

    # Process questionnaires
    psych_count = process_questionnaire(psychwell_df, ['GDTOTAL', 'STAITOTAL'], 'PSYCHWELL')
    adlpq_count = process_questionnaire(adlpq_df, ['ASSCORE'], 'ADLPQ', done_val='Yes')
    adlpqsp_count = process_questionnaire(adlpqsp_df, ['ASSCORE'], 'ADLPQSP', done_val='Yes')
    concerns_count = process_questionnaire(concerns_df, ['CADDVLP', 'CADKNOW', 'CADBLIEV', 'CADWRST', 'CADCNCRN'], 'CONCERNS')

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()

    if len(measurement_df) > 0:
        measurement_df['measurement_id'] = range(1, 1 + len(measurement_df))
        measurement_df['measurement_datetime'] = None
        measurement_df['measurement_time'] = None
        measurement_df['measurement_type_concept_id'] = 32809  # Case Report Form
        measurement_df['operator_concept_id'] = None
        measurement_df['value_as_concept_id'] = None
        measurement_df['unit_concept_id'] = 0
        measurement_df['range_low'] = None
        measurement_df['range_high'] = None
        measurement_df['provider_id'] = None
        measurement_df['visit_detail_id'] = None
        measurement_df['measurement_source_concept_id'] = 0
        measurement_df['value_source_value'] = measurement_df['value_as_number'].astype(str)

    print(f"Created questionnaire MEASUREMENT with {len(measurement_df)} records")
    return measurement_df
