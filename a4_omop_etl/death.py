"""
OMOP DEATH table from study disposition events.

DS.csv DSDECOD=DEATH rows become one DEATH row per person (CDM v5.4).
The death milestone also remains in OBSERVATION (concept 4306655) as a
supplement, but cohort tooling (ATLAS censoring, survival analyses)
reads the dedicated DEATH table.
"""

import pandas as pd

from .helpers import calc_days_to_date


def create_death(
    ds_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create the DEATH table from DS.csv disposition events.

    Source: DS.csv, DSDECOD='DEATH' | Date: DSSTDTC_DAYS_CONSENT
    One row per person (earliest date wins if duplicated). Cause of death
    is not recorded in the source, so cause fields stay NULL/0.
    """
    deaths = ds_df[ds_df['DSDECOD'] == 'DEATH'].copy()
    print(f"  DS: {len(deaths)} DEATH disposition rows")

    person_lookup = person_df[['person_id', 'person_source_value']]
    deaths = deaths.merge(person_lookup, left_on='BID', right_on='person_source_value', how='inner')
    deaths = deaths.merge(date_anchor_df[['BID', 'synthetic_consent_date']], on='BID', how='left')
    deaths['death_date'] = deaths.apply(calc_days_to_date, args=('DSSTDTC_DAYS_CONSENT',), axis=1)

    # death_date is NOT NULL; drop-and-report rather than fabricate.
    undated = deaths['death_date'].isna()
    if undated.any():
        print(f"  dropped {int(undated.sum())} death record(s) with no resolvable date")
        deaths = deaths[~undated]

    # One row per person, earliest date first.
    deaths = deaths.sort_values('death_date').drop_duplicates('person_id')

    death_df = pd.DataFrame({
        'person_id': deaths['person_id'],
        'death_date': deaths['death_date'],
        'death_datetime': None,
        'death_type_concept_id': 32809,  # Case Report Form
        'cause_concept_id': 0,
        'cause_source_value': None,
        'cause_source_concept_id': 0,
    }).reset_index(drop=True)

    print(f"  Created DEATH table with {len(death_df)} records")
    return death_df
