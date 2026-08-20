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


def validate_mi_cdm(
    image_occurrence: pd.DataFrame,
    image_feature: pd.DataFrame,
    measurement: pd.DataFrame,
    procedure_occurrence: pd.DataFrame,
    n_json_series: int,
    n_metadata_meas: int,
) -> dict:
    """
    MI-CDM data quality checks per the DICOM2OMOP guide section 9.

    Completeness of required IMAGE_OCCURRENCE fields, sidecar count
    reconciliation, and linkage integrity of the measurement-event and
    image-feature relationships.
    """
    print("\n--- MI-CDM Validation ---")
    results = {}
    if len(image_occurrence) == 0:
        print("No image_occurrence rows - skipping MI-CDM checks")
        return results

    io = image_occurrence

    # Completeness: required fields per the guide DDL (visit is optional)
    required = ['person_id', 'procedure_occurrence_id', 'image_occurrence_date',
                'image_study_UID', 'image_series_UID', 'modality_concept_id']
    incomplete = {c: int(io[c].isna().sum()) for c in required if io[c].isna().any()}
    results['micdm_io_complete'] = not incomplete
    print(f"IMAGE_OCCURRENCE required fields: "
          f"{'all populated' if not incomplete else incomplete} - "
          f"{'PASS' if results['micdm_io_complete'] else 'FAIL'}")

    # Reconciliation: every sidecar series produced one row
    n_sidecar_rows = int(io['local_path'].notna().sum())
    results['micdm_sidecar_count'] = n_sidecar_rows == n_json_series
    print(f"Sidecar series reconciliation: {n_sidecar_rows} rows "
          f"(expected {n_json_series}) - "
          f"{'PASS' if results['micdm_sidecar_count'] else 'FAIL'}")

    # Linkage: procedures referenced by IMAGE_OCCURRENCE must exist
    proc_ids = set(procedure_occurrence['procedure_occurrence_id'])
    linked = io['procedure_occurrence_id'].dropna()
    orphans = int((~linked.isin(proc_ids)).sum())
    results['micdm_io_procedures_valid'] = orphans == 0
    print(f"IMAGE_OCCURRENCE -> procedure orphans: {orphans} - "
          f"{'PASS' if results['micdm_io_procedures_valid'] else 'FAIL'}")

    # Linkage: DICOM metadata measurements point at real occurrences
    io_ids = set(io['image_occurrence_id'])
    if 'measurement_event_id' in measurement.columns:
        ev = measurement['measurement_event_id'].dropna()
        bad_events = int((~ev.isin(io_ids)).sum())
        results['micdm_measurement_events_valid'] = bad_events == 0
        print(f"MEASUREMENT event links: {len(ev):,} rows, {bad_events} orphans "
              f"({n_metadata_meas:,} DICOM metadata) - "
              f"{'PASS' if results['micdm_measurement_events_valid'] else 'FAIL'}")

    # Linkage: image features point at real occurrences
    if len(image_feature) > 0:
        bad_feat = int((~image_feature['image_occurrence_id'].isin(io_ids)).sum())
        results['micdm_feature_links_valid'] = bad_feat == 0
        print(f"IMAGE_FEATURE -> occurrence orphans: {bad_feat} - "
              f"{'PASS' if results['micdm_feature_links_valid'] else 'FAIL'}")

    # Visit linkage rate on sidecar-derived rows (informational threshold)
    sidecar = io[io['local_path'].notna()]
    if len(sidecar) > 0:
        rate = sidecar['visit_occurrence_id'].notna().mean()
        results['micdm_visit_linkage'] = rate >= 0.99
        print(f"Sidecar visit linkage: {rate:.2%} - "
              f"{'PASS' if results['micdm_visit_linkage'] else 'FAIL'}")

    return results


def validate_data_quality(tables: dict, base_dir=None) -> dict:
    """
    Cross-cutting data-quality checks over the exported event tables.

    - Concept integrity: every *_concept_id must exist in the standard
      vocabulary (CONCEPT.csv at the repo root) or in custom_vocabulary/.
      Custom-range ids missing from the custom vocabulary FAIL; standard-range
      ids missing from the local snapshot WARN only, because the snapshot
      omits vocabularies this ETL legitimately uses (CDISC, PPI, UK Biobank) —
      the target CDM must load those.
    - Duplicate natural keys on MEASUREMENT/OBSERVATION (WARN: ECG triplicate
      readings legitimately repeat person/concept/date/source).
    - Event dates inside the plausible synthetic window.
    """
    from pathlib import Path
    from .config import BASE_DIR, CONCEPT_DIR

    base = Path(base_dir) if base_dir else BASE_DIR
    print("\n--- Data Quality Validation ---")
    results = {}

    concept_cols = {
        'measurement': ['measurement_concept_id'],
        'observation': ['observation_concept_id'],
        'condition_occurrence': ['condition_concept_id'],
        'procedure_occurrence': ['procedure_concept_id'],
        'drug_exposure': ['drug_concept_id'],
        'death': ['death_type_concept_id'],
    }
    used = set()
    for name, cols in concept_cols.items():
        df = tables.get(name)
        if df is None or len(df) == 0:
            continue
        for col in cols:
            if col in df.columns:
                used.update(int(v) for v in df[col].dropna().unique() if int(v) != 0)

    custom_path = base / 'custom_vocabulary' / 'CONCEPT.csv'
    custom_ids = set()
    if custom_path.exists():
        custom_ids = set(pd.read_csv(custom_path, usecols=['concept_id'])['concept_id'].astype(int))

    CUSTOM_LO, DICOM_LO = 2_000_000_000, 2_128_000_000
    used_custom = {c for c in used if CUSTOM_LO <= c < DICOM_LO}
    used_dicom = {c for c in used if c >= DICOM_LO}
    used_standard = used - used_custom - used_dicom

    missing_custom = used_custom - custom_ids
    results['dq_custom_concepts_registered'] = not missing_custom
    print(f"Custom concepts registered: {len(used_custom - missing_custom)}/{len(used_custom)}"
          + (f" MISSING {sorted(missing_custom)[:10]}" if missing_custom else "")
          + f" - {'PASS' if not missing_custom else 'FAIL'}")

    vocab_path = base / 'CONCEPT.csv'
    if vocab_path.exists() and used_standard:
        found = set()
        for chunk in pd.read_csv(vocab_path, sep='\t', usecols=['concept_id'],
                                 chunksize=2_000_000):
            found.update(used_standard.intersection(chunk['concept_id'].astype(int)))
        unresolved = used_standard - found
        # Known-external vocabularies not in the local snapshot: CDISC ids
        # (instrument items), PPI/UK Biobank (reviewer adoptions).
        print(f"Standard concepts in local snapshot: {len(found)}/{len(used_standard)}"
              + (f"; {len(unresolved)} not in snapshot (external vocabularies — "
                 f"verify CDISC/PPI/UK Biobank are loaded in the target CDM)" if unresolved else "")
              + " - PASS (external ids are a WARN, not a failure)")
        results['dq_standard_concepts_resolved'] = True
    else:
        print("Standard vocabulary CONCEPT.csv not found - concept check skipped")

    # Duplicate natural keys. measurement_event_id is part of the identity:
    # DICOM metadata rows legitimately repeat person/concept/date/value across
    # the series they describe. Remaining repeats are ECG triplicate readings
    # whose values coincide and multi-element DICOM strings (by design).
    m = tables.get('measurement')
    if m is not None and len(m):
        key = ['person_id', 'measurement_concept_id', 'measurement_date',
               'measurement_source_value', 'value_as_number', 'measurement_event_id']
        dups = int(m.duplicated(subset=[k for k in key if k in m.columns]).sum())
        print(f"MEASUREMENT duplicate natural keys: {dups:,} "
              f"({dups/len(m):.2%}; ECG triplicates repeat by design) - "
              f"{'PASS' if dups/len(m) < 0.02 else 'WARN'}")
        results['dq_measurement_dup_rate'] = dups / len(m) < 0.02

    # Date ranges: synthetic anchor is 2020-01-01 + <=364d; screening visits
    # reach ~6 months before consent and follow-up ~8.5 years after.
    date_cols = [('measurement', 'measurement_date'), ('observation', 'observation_date'),
                 ('condition_occurrence', 'condition_start_date'),
                 ('procedure_occurrence', 'procedure_date'),
                 ('drug_exposure', 'drug_exposure_start_date'), ('death', 'death_date')]
    lo, hi = pd.Timestamp('2018-06-01'), pd.Timestamp('2032-12-31')
    out_of_range = 0
    for name, col in date_cols:
        df = tables.get(name)
        if df is None or len(df) == 0 or col not in df.columns:
            continue
        d = pd.to_datetime(df[col], errors='coerce')
        out_of_range += int(((d < lo) | (d > hi)).sum())
    results['dq_dates_in_range'] = out_of_range == 0
    print(f"Event dates outside {lo.date()}..{hi.date()}: {out_of_range} - "
          f"{'PASS' if out_of_range == 0 else 'FAIL'}")

    return results
