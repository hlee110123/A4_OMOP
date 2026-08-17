"""
Derived subject-level measurements and observations (ADQS + SUBJINFO).

APOE genotype and carrier status belong in MEASUREMENT domain (genetic lab result).
Treatment assignment (TX) stored as OBSERVATION — not derivable from DRUG_EXPOSURE
because the trial was blinded (both arms have identical dose records).
Population flags (ITT, mITT, PP, Safety) removed — analysis metadata, not clinical data.
Treatment dates removed — derivable from drug_exposure table.

Baseline demographics sourced from SUBJINFO (one row per subject):
  EDCCNTU (years of education) -> OBSERVATION, value_as_number
  BMIBL   (baseline BMI)       -> MEASUREMENT, value_as_number
See concept_maps/adqs.csv for the concept mappings.
"""

import pandas as pd

from . import concepts
from .helpers import (
    prepare_source_df, finalize_measurement_df,
    build_observation_record, finalize_observation_df, safe_float,
)


def create_measurement_apoe(
    adqs_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records for APOE genotype and carrier status.

    Source: adqs.csv (subject-level) | Date: synthetic_consent_date

    Field Mappings (concept_maps/adqs.csv):
        APOEGN        -> APOE gene alleles e2 and e3 and e4 [Identifier] (3029139, LOINC 42315-2)
                         value_as_concept_id: E2/E2..E4/E4 (2100000420-425)
        APOEGNPRSNFLG -> Apolipoprotein E4 [Presence] in Blood (3006041, LOINC 15353-6)
                         value_as_concept_id: positive=4188539, negative=4188540
    """
    # Get subject-level data including APOE fields
    subject_cols = ['BID', 'APOEGN', 'APOEGNPRSNFLG']
    available = [c for c in subject_cols if c in adqs_df.columns]
    subject_df = adqs_df.groupby('BID').first()[
        [c for c in available if c != 'BID']
    ].reset_index()

    subject_df = prepare_source_df(subject_df, person_df, date_anchor_df)

    # APOE genotype value concepts (LOINC Answer codes, Athena-verified)
    # Standard LOINC answer concepts from LA21353-LA21361 series; retired customs 2100000420-425.
    apoe_value_concepts = {
        'E2/E2': 36307526,  # LOINC LA21356-3 APOE e2/e2
        'E2/E3': 36310377,  # LOINC LA21357-1 APOE e2/e3
        'E2/E4': 36308156,  # LOINC LA21361-3 APOE e2/e4
        'E3/E3': 36309003,  # LOINC LA21358-9 APOE e3/e3 (wild type)
        'E3/E4': 36311054,  # LOINC LA21359-7 APOE e3/e4
        'E4/E4': 36303222,  # LOINC LA21360-5 APOE e4/e4
    }

    measurements = []

    for _, row in subject_df.iterrows():
        meas_date = row.get('synthetic_consent_date')

        # APOE Genotype
        if pd.notna(row.get('APOEGN')):
            apoe_genotype = str(row['APOEGN'])
            value_concept = apoe_value_concepts.get(apoe_genotype, 0)
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': 3029139,  # LOINC 42315-2 APOE gene alleles e2/e3/e4 [Identifier]
                'measurement_date': meas_date,
                'value_as_number': None,
                'value_as_concept_id': value_concept,
                'unit_source_value': None,
                'visit_occurrence_id': None,
                'measurement_source_value': f'ADQS:APOEGN={apoe_genotype}',
            })

        # APOE4 Carrier Status
        if pd.notna(row.get('APOEGNPRSNFLG')):
            is_carrier = int(row['APOEGNPRSNFLG']) == 1
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': 3006041,  # LOINC 15353-6 Apolipoprotein E4 [Presence] in Blood
                'measurement_date': meas_date,
                'value_as_number': float(row['APOEGNPRSNFLG']),
                'value_as_concept_id': 4188539 if is_carrier else 4188540,
                'unit_source_value': None,
                'visit_occurrence_id': None,
                'measurement_source_value': f'ADQS:APOEGNPRSNFLG={int(row["APOEGNPRSNFLG"])}',
            })

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    # Override value_source_value with the specific APOE value (after finalize sets the default)
    if len(measurement_df) > 0:
        measurement_df['value_source_value'] = measurement_df['measurement_source_value'].str.split('=').str[-1]

    apoe_count = len([m for m in measurements if 'APOEGN=' in m.get('measurement_source_value', '')])
    carrier_count = len([m for m in measurements if 'APOEGNPRSNFLG=' in m.get('measurement_source_value', '')])
    print(f"  Created {len(measurement_df)} APOE measurements (genotype: {apoe_count}, carrier: {carrier_count})")

    return measurement_df


def create_observation_treatment_arm(
    adqs_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION records for treatment arm assignment (TX).

    Source: adqs.csv (subject-level) | Date: synthetic_consent_date

    Field Mappings (concept_maps/adqs.csv):
        TX -> Treatment assignment (2100000400)
             Placebo=2100000401, Solanezumab=2100000402

    TX is not derivable from DRUG_EXPOSURE because the trial was blinded —
    both solanezumab and placebo arms have identical dose records.
    """
    TX_VALUE_CONCEPTS = {
        'Placebo': 2100000401,
        'Solanezumab': 2100000402,
    }
    TX_CONCEPT_ID = 2100000400

    # Get one row per subject with TX
    tx_df = adqs_df[['BID', 'TX']].dropna(subset=['TX']).drop_duplicates()
    tx_df = prepare_source_df(tx_df, person_df, date_anchor_df)

    observations = []
    for _, row in tx_df.iterrows():
        tx_value = str(row['TX'])
        observations.append(build_observation_record(
            person_id=row['person_id'],
            observation_concept_id=TX_CONCEPT_ID,
            observation_date=row['synthetic_consent_date'],
            value_as_string=tx_value,
            value_as_concept_id=TX_VALUE_CONCEPTS.get(tx_value, 0),
            observation_source_value=f'ADQS:TX={tx_value}',
        ))

    observation_df = pd.DataFrame(observations) if observations else pd.DataFrame()
    observation_df = finalize_observation_df(observation_df)

    placebo_n = len([o for o in observations if 'Placebo' in o.get('observation_source_value', '')])
    solan_n = len([o for o in observations if 'Solanezumab' in o.get('observation_source_value', '')])
    print(f"  Created {len(observation_df)} TX observations (Placebo: {placebo_n}, Solanezumab: {solan_n})")

    return observation_df


def create_observation_education(
    subjinfo_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION records for years of education (EDCCNTU).

    Source: SUBJINFO.csv (one row per subject) | Date: synthetic_consent_date

    Field Mapping (concept_maps/adqs.csv):
        EDCCNTU -> Years of education (1015298, LOINC)
                   value_as_number = total years (range 0-36; reviewer-confirmed)
    """
    EDUCATION_CONCEPT_ID = 1015298  # LOINC "Years of education" (reviewer-confirmed)

    if 'EDCCNTU' not in subjinfo_df.columns:
        return pd.DataFrame()

    edu_df = subjinfo_df[['BID', 'EDCCNTU']].drop_duplicates(subset='BID')
    edu_df = prepare_source_df(edu_df, person_df, date_anchor_df)

    observations = []
    for _, row in edu_df.iterrows():
        years = safe_float(row.get('EDCCNTU'))
        if years is None:
            continue
        observations.append(build_observation_record(
            person_id=row['person_id'],
            observation_concept_id=EDUCATION_CONCEPT_ID,
            observation_date=row['synthetic_consent_date'],
            value_as_number=years,
            observation_source_value=f'SUBJINFO:EDCCNTU={row["EDCCNTU"]}',
        ))

    observation_df = pd.DataFrame(observations) if observations else pd.DataFrame()
    observation_df = finalize_observation_df(observation_df)
    print(f"  Created {len(observation_df)} education (EDCCNTU) observations")

    return observation_df


def create_measurement_bmi(
    subjinfo_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records for baseline body mass index (BMIBL).

    Source: SUBJINFO.csv (one row per subject) | Date: synthetic_consent_date

    Field Mapping (concept_maps/adqs.csv):
        BMIBL -> Body mass index (4245997, SNOMED)
                 value_as_number = baseline BMI (kg/m2; range 13.8-78.9; reviewer-confirmed)
    """
    BMI_CONCEPT_ID = 4245997  # SNOMED "Body mass index" (reviewer-confirmed)

    if 'BMIBL' not in subjinfo_df.columns:
        return pd.DataFrame()

    bmi_df = subjinfo_df[['BID', 'BMIBL']].drop_duplicates(subset='BID')
    bmi_df = prepare_source_df(bmi_df, person_df, date_anchor_df)

    measurements = []
    for _, row in bmi_df.iterrows():
        bmi = safe_float(row.get('BMIBL'))
        if bmi is None:
            continue
        measurements.append({
            'person_id': row['person_id'],
            'measurement_concept_id': BMI_CONCEPT_ID,
            'measurement_date': row['synthetic_consent_date'],
            'value_as_number': bmi,
            'unit_source_value': 'kg/m2',
            'visit_occurrence_id': None,
            'measurement_source_value': f'SUBJINFO:BMIBL={row["BMIBL"]}',
        })

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)
    print(f"  Created {len(measurement_df)} baseline BMI (BMIBL) measurements")

    return measurement_df


def create_observation_retirement(
    subjinfo_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION records for retirement status (WRKRET).

    Source: SUBJINFO.csv (one row per subject) | Date: synthetic_consent_date

    Field Mapping (concept_maps/adqs.csv):
        WRKRET -> Retirement (44803812, SNOMED)
                  value_as_concept_id: 1=Yes (4188539), 0=No (4188540), 96=Unknown (0)
    """
    RETIREMENT_CONCEPT_ID = 44803812  # SNOMED "Retirement" (reviewer-confirmed)
    VALUE_CONCEPTS = {'1': 4188539, '0': 4188540}  # SNOMED Yes / No; 96 (Unknown) -> 0

    if 'WRKRET' not in subjinfo_df.columns:
        return pd.DataFrame()

    ret_df = subjinfo_df[['BID', 'WRKRET']].dropna(subset=['WRKRET']).drop_duplicates(subset='BID')
    ret_df = prepare_source_df(ret_df, person_df, date_anchor_df)

    observations = []
    for _, row in ret_df.iterrows():
        raw = str(row['WRKRET']).strip()
        # Normalize numeric-string forms ('1', '1.0') to bare codes
        code = raw.replace('.0', '')
        if code not in ('1', '0', '96'):
            continue
        observations.append(build_observation_record(
            person_id=row['person_id'],
            observation_concept_id=RETIREMENT_CONCEPT_ID,
            observation_date=row['synthetic_consent_date'],
            value_as_string=code,
            value_as_concept_id=VALUE_CONCEPTS.get(code, 0),
            observation_source_value=f'SUBJINFO:WRKRET={code}',
        ))

    observation_df = pd.DataFrame(observations) if observations else pd.DataFrame()
    observation_df = finalize_observation_df(observation_df)
    yes_n = len([o for o in observations if o['observation_source_value'].endswith('=1')])
    no_n = len([o for o in observations if o['observation_source_value'].endswith('=0')])
    print(f"  Created {len(observation_df)} retirement (WRKRET) observations (Yes: {yes_n}, No: {no_n})")

    return observation_df
