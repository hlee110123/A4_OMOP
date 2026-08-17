"""OMOP VISIT_OCCURRENCE and OBSERVATION_PERIOD table creation."""

import pandas as pd
from datetime import timedelta

from . import concepts
from .helpers import map_visit_concept


def create_visit_occurrence(
    sv_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Create OMOP VISIT_OCCURRENCE from SV.csv.

    Filters out 'Not Done' visits and calculates actual dates from
    consent date offsets.
    """
    VISIT_CONCEPTS = concepts.load_visit_concepts()

    # Filter out "Not Done" visits
    sv_filtered = sv_df[sv_df['SVTYPE'] != 'Not Done'].copy()
    print(f"Filtered visits: {len(sv_df)} total -> {len(sv_filtered)} (excluding 'Not Done')")

    # Ensure VISITCD is string for concatenation
    sv_filtered['VISITCD'] = sv_filtered['VISITCD'].astype(str).str.zfill(3)

    # Create visit source value (BID + VISITCD for traceability)
    sv_filtered['visit_source_value'] = (
        sv_filtered['BID'] + '_' + sv_filtered['VISITCD']
    )

    # Create person lookup
    person_lookup = person_df[['person_id', 'person_source_value']].copy()

    # Merge with person
    sv_filtered = sv_filtered.merge(
        person_lookup,
        left_on='BID',
        right_on='person_source_value',
        how='inner'
    )

    # Merge with date anchor
    sv_filtered = sv_filtered.merge(date_anchor_df[['BID', 'synthetic_consent_date']], on='BID')

    # Calculate visit dates
    def calc_visit_date(row):
        try:
            days = int(row['SVSTDTC_DAYS_CONSENT'])
            return row['synthetic_consent_date'] + timedelta(days=days)
        except:
            return None

    sv_filtered['visit_start_date'] = sv_filtered.apply(calc_visit_date, axis=1)

    # Map visit concepts
    sv_filtered['visit_concept_id'] = sv_filtered.apply(
        lambda row: map_visit_concept(row, VISIT_CONCEPTS), axis=1
    )

    # Build VISIT_OCCURRENCE table
    visit_occurrence = pd.DataFrame({
        'visit_occurrence_id': range(1, len(sv_filtered) + 1),
        'person_id': sv_filtered['person_id'],
        'visit_concept_id': sv_filtered['visit_concept_id'],
        'visit_start_date': sv_filtered['visit_start_date'],
        'visit_start_datetime': None,
        'visit_end_date': sv_filtered['visit_start_date'],  # Same day visits
        'visit_end_datetime': None,
        'visit_type_concept_id': 32809,  # Case Report Form
        'provider_id': None,
        'care_site_id': None,
        'visit_source_value': sv_filtered['visit_source_value'],
        'visit_source_concept_id': 0,
        'admitted_from_concept_id': 0,
        'admitted_from_source_value': None,
        'discharged_to_concept_id': 0,
        'discharged_to_source_value': None,
        'preceding_visit_occurrence_id': None,
    })

    print(f"Created VISIT_OCCURRENCE table with {len(visit_occurrence)} records")
    print(f"  - Visit concept distribution: {visit_occurrence['visit_concept_id'].value_counts().to_dict()}")

    return visit_occurrence


def create_observation_period(
    subjinfo_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    sv_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION_PERIOD from SUBJINFO and SV.

    Start date = consent date (day 0)
    End date = discontinuation date or last visit date
    """
    # Merge with date anchor
    obs_df = subjinfo_df.merge(date_anchor_df, on='BID', how='left')

    # Calculate max visit date per person for fallback
    sv_filtered = sv_df[sv_df['SVTYPE'] != 'Not Done'].copy()
    max_visits = sv_filtered.groupby('BID')['SVSTDTC_DAYS_CONSENT'].max().reset_index()
    max_visits.columns = ['BID', 'max_visit_days']

    obs_df = obs_df.merge(max_visits, on='BID', how='left')

    # Merge with person_df to get correct person_id values
    person_lookup = person_df[['person_id', 'person_source_value']].copy()
    obs_df = obs_df.merge(person_lookup, left_on='BID', right_on='person_source_value', how='inner')

    # Calculate dates
    def calc_start_date(row):
        return row['synthetic_consent_date']  # Day 0 = consent

    def calc_end_date(row):
        # Take the LATEST of discontinuation and last completed visit. Preferring
        # DISCDTC outright made the max-visit branch unreachable (DISCDTC is populated
        # for all 6,945 subjects) and truncated follow-up for the 1,333 subjects whose
        # discontinuation date precedes their last completed visit.
        candidates = [0]
        for col in ('DISCDTC_DAYS_CONSENT', 'max_visit_days'):
            value = pd.to_numeric(row.get(col), errors='coerce')
            if pd.notna(value):
                candidates.append(int(value))
        return row['synthetic_consent_date'] + timedelta(days=max(candidates))

    # Build OBSERVATION_PERIOD table with actual person_id from PERSON table
    observation_period = pd.DataFrame({
        'observation_period_id': range(1, len(obs_df) + 1),
        'person_id': obs_df['person_id'].values,
        'observation_period_start_date': obs_df.apply(calc_start_date, axis=1),
        'observation_period_end_date': obs_df.apply(calc_end_date, axis=1),
        'period_type_concept_id': 32809,  # Case Report Form
    })

    print(f"Created OBSERVATION_PERIOD table with {len(observation_period)} records")

    return observation_period
