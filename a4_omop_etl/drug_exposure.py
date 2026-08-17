"""OMOP DRUG_EXPOSURE table creation."""

import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date


# RxNorm ingredient 'placebo' (standard, Drug domain). dose.csv records the blinded
# nominal dose level for BOTH arms, so BLINDDOSE alone cannot identify the ingredient.
PLACEBO_CONCEPT_ID = 19047135


def create_drug_exposure(
    dose_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    subjinfo_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Create OMOP DRUG_EXPOSURE from dose.csv.

    Solanezumab infusions map to the standard RxNorm ingredient concept with the
    dose in `quantity`. Placebo-arm infusions map to the placebo concept with a
    NULL quantity — BLINDDOSE is the blinded nominal level, not a mass of drug
    received. Arm is taken from SUBJINFO.TX (unblinded in the source release).
    """
    DRUG_CONCEPTS = concepts.load_drug_concepts()

    # Filter to completed doses only (DONE = 'Yes')
    dose_filtered = dose_df[dose_df['DONE'] == 'Yes'].copy()
    print(f"Filtered doses: {len(dose_df)} total -> {len(dose_filtered)} (DONE='Yes')")

    dose_filtered = prepare_source_df(dose_filtered, person_df, date_anchor_df, visit_occurrence_df)

    # Attach randomized treatment arm; a dosed row with no arm is a data error, not a default
    dose_filtered = dose_filtered.merge(subjinfo_df[['BID', 'TX']], on='BID', how='left')
    missing_tx = dose_filtered['TX'].isna().sum()
    if missing_tx:
        raise ValueError(
            f"{missing_tx} dosed rows have no SUBJINFO.TX treatment assignment; "
            "cannot determine whether these are active drug or placebo"
        )
    is_placebo = dose_filtered['TX'].eq('Placebo')

    # Calculate drug exposure dates
    dose_filtered['drug_exposure_start_date'] = dose_filtered.apply(
        calc_days_to_date, args=('STARTDATE_DAYS_CONSENT',), axis=1
    )
    dose_filtered['drug_exposure_end_date'] = dose_filtered.apply(
        calc_days_to_date, args=('ENDDATE_DAYS_CONSENT',), axis=1
    )

    # Map drug concepts: BLINDDOSE gives the Solanezumab dose form; placebo overrides it
    dose_filtered['drug_concept_id'] = dose_filtered['BLINDDOSE'].map(DRUG_CONCEPTS).fillna(0).astype(int)
    dose_filtered.loc[is_placebo, 'drug_concept_id'] = PLACEBO_CONCEPT_ID

    # Build DRUG_EXPOSURE table
    drug_exposure = pd.DataFrame({
        'drug_exposure_id': range(1, len(dose_filtered) + 1),
        'person_id': dose_filtered['person_id'],
        'drug_concept_id': dose_filtered['drug_concept_id'],
        'drug_exposure_start_date': dose_filtered['drug_exposure_start_date'],
        'drug_exposure_start_datetime': None,
        'drug_exposure_end_date': dose_filtered['drug_exposure_end_date'],
        'drug_exposure_end_datetime': None,
        'verbatim_end_date': None,
        'drug_type_concept_id': 32809,  # Case Report Form
        'stop_reason': dose_filtered['COMPLETE'],
        'refills': None,
        # Dose in mg — NULL for placebo, where BLINDDOSE is a blinding level, not a mass
        'quantity': dose_filtered['BLINDDOSE'].astype(float).mask(is_placebo),
        'days_supply': None,
        'sig': None,
        'route_concept_id': 4171047,  # Intravenous route
        'lot_number': None,
        'provider_id': None,
        'visit_occurrence_id': dose_filtered['visit_occurrence_id'],
        'visit_detail_id': None,
        # Blinded dose level retained so the randomization stratum stays recoverable
        'drug_source_value': dose_filtered.apply(
            lambda r: f"{'Placebo' if r['TX'] == 'Placebo' else 'Solanezumab'} {int(r['BLINDDOSE'])}mg",
            axis=1
        ),
        'drug_source_concept_id': 0,
        'route_source_value': 'IV infusion',
        'dose_unit_source_value': 'mg',
    })

    # drug_exposure_start_date / _end_date are NOT NULL in OMOP CDM v5.4. A row whose
    # source day-offsets are NaN cannot be dated; drop and report rather than emit NULL.
    undated = drug_exposure['drug_exposure_start_date'].isna() | \
        drug_exposure['drug_exposure_end_date'].isna()
    if undated.any():
        bids = dose_filtered.loc[undated.values, 'BID'].tolist()
        print(f"  Dropped {int(undated.sum())} dosing record(s) with no resolvable date "
              f"(BID {', '.join(map(str, bids[:5]))})")
        drug_exposure = drug_exposure[~undated].copy()
        drug_exposure['drug_exposure_id'] = range(1, len(drug_exposure) + 1)

    # Print summary
    print(f"Created DRUG_EXPOSURE table with {len(drug_exposure)} records")
    print(f"  - Arm distribution: {dose_filtered['TX'].value_counts().to_dict()}")
    print(f"  - Dose distribution: {dose_filtered['BLINDDOSE'].value_counts().to_dict()}")
    print(f"  - Visits linked: {drug_exposure['visit_occurrence_id'].notna().sum()} / {len(drug_exposure)}")

    return drug_exposure
