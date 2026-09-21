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
        raw = row.get('LBORRES')
        value = safe_float(raw) if pd.notna(raw) and raw != '' else None

        # BLQ (below limit of quantification) has no numeric result and no
        # recorded quantification limit; the row is kept with a NULL value,
        # '<' operator, and 'BLQ' in value_source_value so the performed
        # test stays visible. 'NOR' (no valid result) rows are dropped.
        is_blq = str(raw).strip().upper() == 'BLQ'
        if value is not None or is_blq:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept.get('concept_id', 0),
                'measurement_date': row.get('visit_start_date'),
                'value_as_number': value,
                'operator_concept_id': 4171756 if is_blq else None,  # '<'
                'value_source_value': 'BLQ' if is_blq else None,
                'unit_source_value': row.get('LBORRESU', concept.get('unit', '')),
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"AB:{testcd}|{row.get('LBSPEC', '')}|{row.get('LBMETHOD', '')}",
            })

    print(f"  Amyloid-beta: {len(ab_test_df)} total -> {len([m for m in measurements if 'AB:' in m.get('measurement_source_value', '')])} valid")

    # ---- pTau-217 Tests ----
    ab_count = len(measurements)
    ptau_filtered = prepare_source_df(ptau217_df, person_df, date_anchor_df, visit_occurrence_df,
                                      visit_extra_cols=['visit_start_date'])
    ptau_filtered['measurement_date'] = ptau_filtered.apply(calc_days_to_date, args=('COLLECTION_DATE_DAYS_CONSENT',), axis=1)
    # Collection date first, visit date when the offset is missing; truly
    # undated rows drop-and-report downstream.
    _no_dt = ptau_filtered['measurement_date'].isna()
    ptau_filtered.loc[_no_dt, 'measurement_date'] = ptau_filtered.loc[_no_dt, 'visit_start_date']

    concept = BIOMARKER_CONCEPTS.get('PTAU217', {})
    for _, row in ptau_filtered.iterrows():
        # <LLOQ results carry the raw instrument value in ORRESRAW; keep it
        # with the '<' operator and the censoring flag in value_source_value.
        # >ULOQ rows also have ORRESRAW but are deliberately excluded:
        # COMMENT2 states ">2x ULOQ data not reported per medical director".
        orres = row.get('ORRES', '')
        orresraw = row.get('ORRESRAW', '')
        is_lloq = str(orres).startswith('<')
        if is_lloq:
            value = safe_float(orresraw)
        else:
            value = safe_float(orres) if pd.notna(orres) and orres != '' else None

        if value is not None:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept.get('concept_id', 0),
                'measurement_date': row.get('measurement_date'),
                'value_as_number': value,
                'operator_concept_id': 4171756 if is_lloq else None,  # '<'
                'value_source_value': str(orres) if is_lloq else None,
                'unit_source_value': row.get('ORRESU', concept.get('unit', '')),
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"PTAU217|{row.get('SPEC', '')}|{row.get('METHOD', '')}",
            })

    ptau_count = len(measurements) - ab_count
    print(f"  pTau-217: {len(ptau217_df)} total -> {ptau_count} valid")

    # ---- Roche Panel ----
    roche_count_start = len(measurements)
    roche_filtered = prepare_source_df(roche_df, person_df, date_anchor_df, visit_occurrence_df,
                                       visit_extra_cols=['visit_start_date'])
    roche_filtered['measurement_date'] = roche_filtered.apply(calc_days_to_date, args=('LABD_DAYS_CONSENT',), axis=1)
    _no_dt = roche_filtered['measurement_date'].isna()
    roche_filtered.loc[_no_dt, 'measurement_date'] = roche_filtered.loc[_no_dt, 'visit_start_date']

    for _, row in roche_filtered.iterrows():
        testcd = str(row.get('LBTESTCD', ''))
        concept = BIOMARKER_CONCEPTS.get(testcd, {})
        value = safe_float(row.get('LABRESN'))
        unit = row.get('LABORESU', concept.get('unit', ''))
        value_source = None

        # The Abeta analytes share standard LOINC plasma concepts with the
        # immunoassay path (pg/mL), so ng/mL Roche values are converted
        # x1000. Unit-driven: AMYLB40 arrives in NG/ML, AMYLB42 already in
        # PG/ML — converting by test code alone corrupted Abeta-42 by 1000x.
        # Pure unit conversion; original value and unit in value_source_value.
        if testcd in ('AMYLB40', 'AMYLB42'):
            source_unit = str(unit).strip().upper()
            if value is not None and source_unit == 'NG/ML':
                value_source = f"{row.get('LABRESN')} {unit}"
                value = value * 1000.0
            unit = 'pg/mL'

        # BLQ rows have no numeric result and the source records no
        # quantification limit (LBMTDL is the test name, not a limit), so
        # the row is kept with a NULL value, '<' operator, and 'BLQ' flag.
        is_blq = str(row.get('LABRESC', '')).strip().upper() == 'BLQ' and value is None
        if value is not None or is_blq:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept.get('concept_id', 0),
                'measurement_date': row.get('measurement_date'),
                'value_as_number': value,
                'operator_concept_id': 4171756 if is_blq else None,  # '<'
                'value_source_value': 'BLQ' if is_blq else value_source,
                'unit_source_value': unit,
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
