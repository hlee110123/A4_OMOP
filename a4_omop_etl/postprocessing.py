"""
Post-processing steps applied after all domain tables are built.

- Unit concept mapping for measurements
- Observation period expansion to cover all clinical data
"""

import pandas as pd

from . import concepts


def map_unit_concepts(measurement: pd.DataFrame) -> pd.DataFrame:
    """Map unit_source_value to unit_concept_id (case-insensitive lookup).

    Source data uses inconsistent casing for the same unit (e.g., ROCHE
    biomarker reports 'PG/ML' while AB biomarker uses 'pg/mL'). The lookup
    keys in concept_maps/units.csv are therefore folded to lowercase here
    so a single canonical entry per unit suffices regardless of source casing.
    """
    UNIT_CONCEPT_MAP = concepts.load_unit_concept_map()
    lower_map = {k.lower(): v for k, v in UNIT_CONCEPT_MAP.items()}

    unmapped_mask = (measurement['unit_concept_id'] == 0) & measurement['unit_source_value'].notna()
    unmapped_before = unmapped_mask.sum()
    mapped_units = measurement.loc[unmapped_mask, 'unit_source_value'].str.lower().map(lower_map)
    measurement.loc[unmapped_mask & mapped_units.notna() & (mapped_units > 0), 'unit_concept_id'] = \
        mapped_units[mapped_units.notna() & (mapped_units > 0)].astype(int)
    unmapped_after = (measurement['unit_concept_id'] == 0).sum()
    print(f"\nUnit concept mapping: {unmapped_before - unmapped_after:,} newly mapped, {unmapped_after:,} remaining unmapped")

    return measurement


def expand_observation_periods(
    observation_period: pd.DataFrame,
    event_tables: list,
) -> pd.DataFrame:
    """Widen observation_period to cover every clinical event.

    event_tables is a list of (dataframe, date_column) pairs and must include ALL
    event tables. Previously only measurement/observation/drug_exposure were
    considered, so visits, procedures and conditions could fall outside; and only
    the END was expanded, so screening events (which run to 174 days BEFORE consent)
    fell before the start.

    Dates are compared as datetimes. The previous implementation coerced everything
    with str() and compared lexicographically, then assigned the winning *string*
    back into a datetime column — correct only because every producer happened to
    emit a Timestamp, whose str() form sorts correctly.
    """
    print("\n--- Expanding Observation Periods ---")
    op = observation_period.copy()
    for col in ('observation_period_start_date', 'observation_period_end_date'):
        op[col] = pd.to_datetime(op[col], errors='coerce')

    mins, maxs = [], []
    for df, date_col in event_tables:
        if df is None or len(df) == 0 or date_col not in df.columns:
            continue
        d = pd.to_datetime(df[date_col], errors='coerce')
        valid = d.notna()
        if not valid.any():
            continue
        g = d[valid].groupby(df.loc[valid, 'person_id'])
        mins.append(g.min())
        maxs.append(g.max())

    if mins:
        earliest = pd.concat(mins, axis=1).min(axis=1)
        latest = pd.concat(maxs, axis=1).max(axis=1)
        new_start = op['person_id'].map(earliest)
        new_end = op['person_id'].map(latest)

        starts_moved = (new_start.notna() & (new_start < op['observation_period_start_date'])).sum()
        ends_moved = (new_end.notna() & (new_end > op['observation_period_end_date'])).sum()

        op['observation_period_start_date'] = op['observation_period_start_date'].where(
            new_start.isna() | (new_start >= op['observation_period_start_date']), new_start)
        op['observation_period_end_date'] = op['observation_period_end_date'].where(
            new_end.isna() | (new_end <= op['observation_period_end_date']), new_end)

        print(f"Expanded start for {starts_moved:,} and end for {ends_moved:,} "
              f"of {len(op):,} persons (across {len(event_tables)} event tables)")

    return op


