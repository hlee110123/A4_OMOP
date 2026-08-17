"""
Create OMOP MEASUREMENT records from biomarker files.

Combines amyloid-beta, pTau-217, and Roche panel biomarkers.
"""

import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date, finalize_measurement_df, safe_float

BIOMARKER_CONCEPTS = concepts.load_biomarker_concepts()


def create_measurement_biomarkers(
    ab_test_df: pd.DataFrame,
    ptau217_df: pd.DataFrame,
    roche_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from biomarker files.

    Sources & Field Mappings (concept_maps/biomarkers.csv):
        ab_test.csv  -> LBTESTCD lookup (TP40, TP42, BP40, BP42, FP40, FP42,
                        TP42/TP40 ratio) | Date: visit_start_date
        ptau217.csv  -> PTAU217 (1092155, handles <LLOQ) | Date: COLLECTION_DATE_DAYS_CONSENT
        roche.csv    -> LBTESTCD lookup (GFAP, NF-L, TPP181, AMYLB40, AMYLB42)
                        | Date: LABD_DAYS_CONSENT
    """
    measurements = []

    # ---- Amyloid-Beta Tests ----
    ab_filtered = prepare_source_df(ab_test_df, person_df, date_anchor_df, visit_occurrence_df,
                                    visit_extra_cols=['visit_start_date'])

    for _, row in ab_filtered.iterrows():
        testcd = row.get('LBTESTCD', '')
        concept = BIOMARKER_CONCEPTS.get(testcd, {})
        value = safe_float(row['LBORRES']) if pd.notna(row.get('LBORRES')) and row.get('LBORRES') != '' else None

        if value is not None:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept.get('concept_id', 0),
                'measurement_date': row.get('visit_start_date'),
                'value_as_number': value,
                'unit_source_value': row.get('LBORRESU', concept.get('unit', '')),
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"AB:{testcd}|{row.get('LBSPEC', '')}|{row.get('LBMETHOD', '')}",
            })

    print(f"  Amyloid-beta: {len(ab_test_df)} total -> {len([m for m in measurements if 'AB:' in m.get('measurement_source_value', '')])} valid")

    # ---- pTau-217 Tests ----
    ab_count = len(measurements)
    ptau_filtered = prepare_source_df(ptau217_df, person_df, date_anchor_df, visit_occurrence_df)
    ptau_filtered['measurement_date'] = ptau_filtered.apply(calc_days_to_date, args=('COLLECTION_DATE_DAYS_CONSENT',), axis=1)

    concept = BIOMARKER_CONCEPTS.get('PTAU217', {})
    for _, row in ptau_filtered.iterrows():
        # Handle <LLOQ values - use raw value if available
        orres = row.get('ORRES', '')
        orresraw = row.get('ORRESRAW', '')
        if str(orres).startswith('<'):
            value = safe_float(orresraw)
        else:
            value = safe_float(orres) if pd.notna(orres) and orres != '' else None

        if value is not None:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept.get('concept_id', 0),
                'measurement_date': row.get('measurement_date'),
                'value_as_number': value,
                'unit_source_value': row.get('ORRESU', concept.get('unit', '')),
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"PTAU217|{row.get('SPEC', '')}|{row.get('METHOD', '')}",
            })

    ptau_count = len(measurements) - ab_count
    print(f"  pTau-217: {len(ptau217_df)} total -> {ptau_count} valid")

    # ---- Roche Panel ----
    roche_count_start = len(measurements)
    roche_filtered = prepare_source_df(roche_df, person_df, date_anchor_df, visit_occurrence_df)
    roche_filtered['measurement_date'] = roche_filtered.apply(calc_days_to_date, args=('LABD_DAYS_CONSENT',), axis=1)

    for _, row in roche_filtered.iterrows():
        testcd = str(row.get('LBTESTCD', ''))
        concept = BIOMARKER_CONCEPTS.get(testcd, {})
        value = safe_float(row.get('LABRESN'))

        if value is not None:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept.get('concept_id', 0),
                'measurement_date': row.get('measurement_date'),
                'value_as_number': value,
                'unit_source_value': row.get('LABORESU', concept.get('unit', '')),
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"ROCHE:{testcd}|{row.get('LBSPEC', '')}|{row.get('LBMETHOD', '')}",
            })

    roche_count = len(measurements) - roche_count_start
    print(f"  Roche panel: {len(roche_df)} total -> {roche_count} valid")

    # Build DataFrame
    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"Created biomarker MEASUREMENT with {len(measurement_df)} total records")
    return measurement_df
