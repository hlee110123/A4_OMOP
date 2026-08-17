"""CSV export and ETL validation."""

import pandas as pd

from .config import OUTPUT_DIR, MI_CDM_OUTPUT_DIR


def export_tables(tables: dict) -> None:
    """Export all OMOP tables to CSV files."""
    print("\n--- Exporting CSV Files ---")
    for name, df in tables.items():
        path = OUTPUT_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"Exported: {name}.csv")


def export_mi_cdm_tables(tables: dict) -> None:
    """Export MI-CDM extension tables to mi_cdm/ subdirectory."""
    MI_CDM_OUTPUT_DIR.mkdir(exist_ok=True)
    print("\n--- Exporting MI-CDM Extension Tables ---")
    for name, df in tables.items():
        path = MI_CDM_OUTPUT_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"Exported: mi_cdm/{name}.csv ({len(df)} rows)")


def validate_etl(
    person: pd.DataFrame,
    visit_occurrence: pd.DataFrame,
    observation_period: pd.DataFrame,
    subjinfo: pd.DataFrame,
    sv: pd.DataFrame,
    drug_exposure: pd.DataFrame,
    dose: pd.DataFrame
) -> dict:
    """
    Validate ETL output quality.

    Performs 5 checks:
    1. Person count matches SUBJINFO
    2. Visit count within tolerance
    3. No orphan visits (referential integrity)
    4. All persons have observation periods
    5. Drug exposure count matches source
    """
    print("\n--- Validation ---")
    results = {}

    # Check 1: Person count matches SUBJINFO
    expected_persons = len(subjinfo)
    actual_persons = len(person)
    results['person_count'] = actual_persons == expected_persons
    print(f"Person count: {actual_persons} (expected {expected_persons}) - {'PASS' if results['person_count'] else 'FAIL'}")

    # Check 2: Visit count within tolerance
    sv_filtered = sv[sv['SVTYPE'] != 'Not Done']
    expected_visits = len(sv_filtered)
    actual_visits = len(visit_occurrence)
    tolerance = 0.05
    results['visit_count'] = abs(actual_visits - expected_visits) / expected_visits < tolerance
    print(f"Visit count: {actual_visits} (expected ~{expected_visits}, tolerance {tolerance*100}%) - {'PASS' if results['visit_count'] else 'FAIL'}")

    # Check 3: No orphan visits
    person_ids = set(person['person_id'])
    visit_person_ids = set(visit_occurrence['person_id'])
    orphan_visits = visit_person_ids - person_ids
    results['no_orphan_visits'] = len(orphan_visits) == 0
    print(f"Orphan visits: {len(orphan_visits)} - {'PASS' if results['no_orphan_visits'] else 'FAIL'}")

    # Check 4: All persons have observation periods
    obs_person_ids = set(observation_period['person_id'])
    missing_obs = person_ids - obs_person_ids
    results['all_persons_have_obs_period'] = len(missing_obs) == 0
    print(f"Persons without observation period: {len(missing_obs)} - {'PASS' if results['all_persons_have_obs_period'] else 'FAIL'}")

    # Check 5: Drug exposure count
    # Dosed rows whose day-offsets are NaN cannot be dated and are deliberately dropped
    # (drug_exposure_start_date / _end_date are NOT NULL in OMOP CDM v5.4), so the
    # expectation is dosed-AND-datable rather than simply dosed.
    dosed = dose[dose['DONE'] == 'Yes']
    datable = dosed[dosed['STARTDATE_DAYS_CONSENT'].notna() & dosed['ENDDATE_DAYS_CONSENT'].notna()]
    expected_doses = len(datable)
    undatable = len(dosed) - expected_doses
    actual_doses = len(drug_exposure)
    results['drug_exposure_count'] = actual_doses == expected_doses
    suffix = f", {undatable} undatable excluded" if undatable else ""
    print(f"Drug exposure count: {actual_doses} (expected {expected_doses}{suffix}) - {'PASS' if results['drug_exposure_count'] else 'FAIL'}")

    return results
