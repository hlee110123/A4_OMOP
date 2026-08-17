"""OMOP PERSON table creation."""

import pandas as pd

from . import concepts


def create_person_table(
    subjinfo_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    ptdemog_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Create OMOP PERSON table from SUBJINFO.

    Maps demographics including gender, race, ethnicity with OMOP concept IDs.
    Preserves multi-racial source values from ptdemog.
    """
    GENDER_CONCEPTS = concepts.load_gender_concepts()
    RACE_CONCEPTS = concepts.load_race_concepts()
    ETHNICITY_CONCEPTS = concepts.load_ethnicity_concepts()

    # Merge with date anchor
    person_df = subjinfo_df.merge(date_anchor_df, on='BID', how='left')

    # Merge with ptdemog for multi-racial source value
    person_df = person_df.merge(
        ptdemog_df[['BID', 'PTRACE']],
        on='BID',
        how='left'
    )

    # Calculate year of birth from age at consent
    def calc_birth_year(row):
        try:
            consent_year = row['synthetic_consent_date'].year
            age = int(row['AGEYR'])
            return consent_year - age
        except:
            return None

    # Create PERSON table
    person = pd.DataFrame({
        'person_id': range(1, len(person_df) + 1),
        'gender_concept_id': person_df['SEX'].map(GENDER_CONCEPTS).fillna(0).astype(int),
        'year_of_birth': person_df.apply(calc_birth_year, axis=1),
        'month_of_birth': 6,  # Mid-year estimate
        'day_of_birth': 15,
        'birth_datetime': None,
        'race_concept_id': person_df['RACE'].map(RACE_CONCEPTS).fillna(0).astype(int),
        'ethnicity_concept_id': person_df['ETHNIC'].map(ETHNICITY_CONCEPTS).fillna(0).astype(int),
        'location_id': None,
        'provider_id': None,
        'care_site_id': None,
        'person_source_value': person_df['BID'],
        'gender_source_value': person_df['SEX'].astype(str),
        'gender_source_concept_id': 0,
        'race_source_value': person_df['PTRACE'],  # Multi-racial detail from ptdemog
        'race_source_concept_id': 0,
        'ethnicity_source_value': person_df['ETHNIC'].astype(str),
        'ethnicity_source_concept_id': 0,
    })

    print(f"Created PERSON table with {len(person)} records")
    print(f"  - Gender distribution: {person['gender_concept_id'].value_counts().to_dict()}")

    return person
