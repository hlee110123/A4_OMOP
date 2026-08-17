"""
Shared utilities used across domain modules.

- Date anchoring (privacy-preserving synthetic dates)
- Person and visit lookup construction
- Date calculation from days-from-consent
- Visit concept mapping
- OMOP record factories and table finalization
- Standard source-data preparation (merge chains)
"""

import hashlib
from datetime import datetime, timedelta

import pandas as pd

from . import concepts


# ─── Date Anchoring ───────────────────────────────────────────────────

def create_date_anchor(subjinfo_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create synthetic consent date using BID hash for privacy.

    Each person gets a unique offset (0-365 days) based on their BID hash,
    providing privacy while maintaining temporal relationships.
    """
    base_date = datetime(2020, 1, 1)

    def hash_offset(bid: str) -> int:
        hash_val = int(hashlib.md5(bid.encode()).hexdigest(), 16)
        return hash_val % 365

    date_anchor = pd.DataFrame({'BID': subjinfo_df['BID'].unique()})
    date_anchor['offset_days'] = date_anchor['BID'].apply(hash_offset)
    date_anchor['synthetic_consent_date'] = date_anchor['offset_days'].apply(
        lambda x: base_date + timedelta(days=x)
    )

    print(f"Created date anchors for {len(date_anchor)} subjects")
    return date_anchor


# ─── Visit Concept Mapping ───────────────────────────────────────────

def map_visit_concept(row: pd.Series, visit_concepts: dict) -> int:
    """Map visit to OMOP visit_concept_id based on VISITCD and VISIT name."""
    visitcd = str(row['VISITCD']).zfill(3)
    visit_name = str(row.get('VISIT', ''))

    # Screening visits (001-005)
    if visitcd in ['001', '002', '003', '004', '005']:
        return visit_concepts['screening']

    # Baseline visit (006)
    elif visitcd == '006':
        return visit_concepts['baseline']

    # Infusion visits (based on visit name)
    elif 'Infusion' in visit_name:
        return visit_concepts['infusion']

    # Unscheduled visits (701-705)
    elif visitcd in ['701', '702', '703', '704', '705']:
        return visit_concepts['unscheduled']

    # Default for all others (clinic visits, etc.)
    return visit_concepts['default']


# ─── Value Conversion ────────────────────────────────────────────────

def safe_float(value):
    """Convert value to float, returning None on failure or NaN input."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ─── DataFrame Utilities ─────────────────────────────────────────────

def concat_and_assign_ids(dfs, id_column: str) -> pd.DataFrame:
    """Concatenate DataFrames and assign sequential IDs."""
    result = pd.concat(dfs, ignore_index=True)
    if len(result) > 0:
        result[id_column] = range(1, len(result) + 1)
    return result


def drop_undated(df, date_col: str, id_column: str, label: str,
                 source_col: str = None) -> pd.DataFrame:
    """Drop rows with no resolvable date and report what was lost, by source.

    The date columns of MEASUREMENT, OBSERVATION and DRUG_EXPOSURE are NOT NULL in
    OMOP CDM v5.4, so an undated row cannot be loaded. A substituted placeholder
    date would pass downstream checks while being wrong, so rows are dropped and
    counted instead. IDs are reassigned afterwards to keep the key contiguous.
    """
    if len(df) == 0 or date_col not in df.columns:
        return df
    undated = df[date_col].isna()
    n = int(undated.sum())
    if not n:
        return df

    if source_col and source_col in df.columns:
        by = (df.loc[undated, source_col].astype(str)
              .str.split(':').str[0].str.split('|').str[0].value_counts())
        detail = ", ".join(f"{k} x{v:,}" for k, v in by.head(6).items())
    else:
        detail = "no source breakdown"
    print(f"  {label}: dropped {n:,} of {len(df):,} rows with no resolvable {date_col} ({detail})")

    result = df[~undated].copy()
    result[id_column] = range(1, len(result) + 1)
    return result


# ─── Row-Level Date Calculation ──────────────────────────────────────

def calc_days_to_date(row, days_col: str):
    """
    Calculate date from synthetic_consent_date + days offset.

    For use with df.apply():  df['date'] = df.apply(calc_days_to_date, args=('DAYS_COL',), axis=1)
    Requires 'synthetic_consent_date' column (from prepare_source_df or date_anchor merge).
    """
    try:
        if pd.notna(row.get(days_col)) and pd.notna(row.get('synthetic_consent_date')):
            return row['synthetic_consent_date'] + timedelta(days=int(row[days_col]))
    except (ValueError, TypeError):
        pass
    return None


# ─── Source Data Preparation ─────────────────────────────────────────

def prepare_source_df(
    df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame = None,
    viscode_col: str = 'VISCODE',
    visit_extra_cols: list = None,
) -> pd.DataFrame:
    """
    Standard merge sequence: person lookup + date anchor + optional visit linking.

    Parameters
    ----------
    df : source DataFrame (must have 'BID' column)
    person_df : PERSON table (needs person_id, person_source_value)
    date_anchor_df : date anchor table (needs BID, synthetic_consent_date)
    visit_occurrence_df : if provided, normalizes VISCODE and merges visit lookup
    viscode_col : column containing the visit code (default 'VISCODE')
    visit_extra_cols : additional visit columns to include (e.g. ['visit_start_date'])

    Returns merged DataFrame with person_id, synthetic_consent_date,
    and optionally visit_occurrence_id + visit_source_value.
    """
    person_lookup = person_df[['person_id', 'person_source_value']].copy()
    result = df.merge(person_lookup, left_on='BID', right_on='person_source_value', how='inner')
    result = result.merge(date_anchor_df[['BID', 'synthetic_consent_date']], on='BID', how='left')

    if visit_occurrence_df is not None and viscode_col in result.columns:
        # Normalize VISCODE to zero-padded 3-char string. Use nullable Int64 to
        # handle source columns that are float64 (because of NaN VISCODEs).
        result[viscode_col] = (
            pd.to_numeric(result[viscode_col], errors='coerce')
            .astype('Int64')
            .astype(str)
            .replace('<NA>', '')
            .str.zfill(3)
        )
        result['visit_source_value'] = result['BID'] + '_' + result[viscode_col]

        cols = ['visit_occurrence_id', 'visit_source_value']
        if visit_extra_cols:
            cols = cols + visit_extra_cols
        # Include person_id in visit lookup if available (for disambiguating)
        if 'person_id' in visit_occurrence_df.columns:
            cols = cols + ['person_id']
        cols = list(dict.fromkeys(cols))  # deduplicate preserving order
        visit_lookup = visit_occurrence_df[cols].copy()

        merge_on = ['visit_source_value']
        if 'person_id' in visit_lookup.columns:
            merge_on.append('person_id')
        result = result.merge(visit_lookup, on=merge_on, how='left')

    return result


# ─── OMOP Record Factories ──────────────────────────────────────────

def build_measurement_record(
    person_id, measurement_concept_id, measurement_date,
    value_as_number=None, unit_source_value='',
    visit_occurrence_id=None, measurement_source_value='',
    **overrides
) -> dict:
    """
    Build a measurement dict with standard fields.

    Only the 7 core fields are set here; OMOP boilerplate columns
    (measurement_datetime, type_concept_id, etc.) are filled later
    by finalize_measurement_df().
    """
    record = {
        'person_id': person_id,
        'measurement_concept_id': measurement_concept_id,
        'measurement_date': measurement_date,
        'value_as_number': value_as_number,
        'unit_source_value': unit_source_value,
        'visit_occurrence_id': visit_occurrence_id,
        'measurement_source_value': measurement_source_value,
    }
    record.update(overrides)
    return record


def build_observation_record(
    person_id, observation_concept_id, observation_date,
    value_as_number=None, value_as_string=None,
    value_as_concept_id=None, visit_occurrence_id=None,
    observation_source_value='', unit_source_value=None,
    qualifier_source_value=None, qualifier_concept_id=None,
    **overrides
) -> dict:
    """
    Build an observation dict with all 15 OMOP OBSERVATION fields defaulted.

    Callers pass only the fields that differ from defaults.
    """
    record = {
        'person_id': person_id,
        'observation_concept_id': observation_concept_id,
        'observation_date': observation_date,
        'observation_datetime': None,
        'observation_type_concept_id': 32809,  # Case Report Form
        'value_as_number': value_as_number,
        'value_as_string': value_as_string,
        'value_as_concept_id': value_as_concept_id,
        'qualifier_concept_id': qualifier_concept_id,
        'unit_concept_id': 0,
        'provider_id': None,
        'visit_occurrence_id': visit_occurrence_id,
        'visit_detail_id': None,
        'observation_source_value': observation_source_value,
        'observation_source_concept_id': 0,
        'unit_source_value': unit_source_value,
        'qualifier_source_value': qualifier_source_value,
    }
    record.update(overrides)
    return record


# ─── Table Finalization ──────────────────────────────────────────────

def finalize_measurement_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill OMOP boilerplate columns and assign sequential measurement IDs.

    Call after pd.DataFrame(measurements) to add the standard columns
    that are identical across all measurement modules.
    """
    if len(df) == 0:
        return df

    df['measurement_id'] = range(1, 1 + len(df))

    defaults = {
        'measurement_datetime': None,
        'measurement_time': None,
        'measurement_type_concept_id': 32809,  # Case Report Form
        'operator_concept_id': None,
        'value_as_concept_id': None,
        'unit_concept_id': 0,
        'range_low': None,
        'range_high': None,
        'provider_id': None,
        'visit_detail_id': None,
        'measurement_source_concept_id': 0,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    if 'value_source_value' not in df.columns:
        df['value_source_value'] = df['value_as_number'].astype(str)
    else:
        mask = df['value_source_value'].isna()
        if mask.any():
            df.loc[mask, 'value_source_value'] = df.loc[mask, 'value_as_number'].astype(str)

    return df


def finalize_observation_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign sequential observation IDs.

    Observation dicts from build_observation_record() already contain
    all required fields, so this just handles the ID assignment.
    """
    if len(df) == 0:
        return df
    df['observation_id'] = range(1, 1 + len(df))
    return df
