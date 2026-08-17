"""
OMOP PROCEDURE_OCCURRENCE for imaging procedures.

Creates one procedure record per unique imaging session, identified
by (person, modality, scan_date).  Multiple source CSVs may reference
the same physical scan (e.g. imaging_SUVR_tau and Tau_PET_PetSurfer);
deduplication ensures one procedure per session.

MI-CDM reference: Both Kalokyri et al. (2023) and Park et al. (2025)
link Imaging_Study → Procedure_Occurrence for provenance.
"""

import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date

PROCEDURE_CONCEPTS = concepts.load_procedure_concepts()

# Maps each imaging source file key to its procedure type and date column
_SOURCE_CONFIG = {
    # Core imaging
    'imaging_mri':       ('MRI_BRAIN',      'Date_DAYS_CONSENT'),
    'imaging_amyloid':   ('PET_AMYLOID',    'scan_date_DAYS_CONSENT'),
    'imaging_tau':       ('PET_TAU',        'scan_date_DAYS_CONSENT'),
    # Extended imaging
    'imaging_mri_reads': ('MRI_BRAIN',      'STUDYDATE_DAYS_CONSENT'),
    'imaging_flair':     ('MRI_BRAIN',      None),  # Uses VISCODE/visit_start_date
    'imaging_retinal':   ('RETINAL_IMAGING','ExamDate_DAYS_CONSENT'),
    'imaging_pet_va':    ('PET_AMYLOID',    'scan_date_DAYS_CONSENT'),
    'tau_petsurfer':     ('PET_TAU',        None),  # Uses VISCODE/visit_start_date
    'tau_stanford':      ('PET_TAU',        None),  # Uses VISCODE/visit_start_date
}


def create_procedure_occurrence(
    sources: dict,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP PROCEDURE_OCCURRENCE records for imaging sessions.

    Deduplicates across all 9 imaging source files by
    (person_id, procedure_type, scan_date) to produce one record
    per physical imaging session.
    """
    print("\n--- MI-CDM: PROCEDURE_OCCURRENCE (Imaging) ---")
    all_procedures = []

    for src_key, (proc_type, days_col) in _SOURCE_CONFIG.items():
        df = sources.get(src_key)
        if df is None or len(df) == 0:
            continue

        src_df = df.copy()

        # Filter analyzed-only for PET sources that have scan_analyzed
        if 'scan_analyzed' in src_df.columns:
            src_df = src_df[src_df['scan_analyzed'] == 'Yes'].copy()

        if len(src_df) == 0:
            continue

        # Merge with person and date anchor
        if days_col is None:
            # Sources that use VISCODE linkage for dates
            merged = prepare_source_df(
                src_df, person_df, date_anchor_df,
                visit_occurrence_df, visit_extra_cols=['visit_start_date']
            )
            merged['_scan_date'] = merged.apply(
                lambda row: row.get('visit_start_date')
                if pd.notna(row.get('visit_start_date'))
                else row.get('synthetic_consent_date'),
                axis=1
            )
        else:
            merged = prepare_source_df(src_df, person_df, date_anchor_df)
            merged['_scan_date'] = merged.apply(
                calc_days_to_date, args=(days_col,), axis=1
            )
            # Fallback to synthetic consent date
            mask = merged['_scan_date'].isna()
            if mask.any():
                merged.loc[mask, '_scan_date'] = merged.loc[mask, 'synthetic_consent_date']

        concept = PROCEDURE_CONCEPTS[proc_type]

        for _, row in merged.iterrows():
            if pd.isna(row.get('_scan_date')):
                continue
            all_procedures.append({
                'person_id': row['person_id'],
                'procedure_concept_id': concept['concept_id'],
                'procedure_date': row['_scan_date'],
                'procedure_type_concept_id': 32809,  # Case Report Form
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'procedure_source_value': proc_type,
                '_proc_type': proc_type,
            })

    if not all_procedures:
        print("  No imaging procedures found")
        return pd.DataFrame()

    proc_df = pd.DataFrame(all_procedures)

    # Deduplicate: one procedure per (person_id, procedure_concept_id, procedure_date)
    proc_df['_date_str'] = proc_df['procedure_date'].astype(str)
    dedup_df = proc_df.drop_duplicates(
        subset=['person_id', 'procedure_concept_id', '_date_str'],
        keep='first'
    ).copy()

    # Assign sequential IDs
    dedup_df = dedup_df.reset_index(drop=True)
    dedup_df['procedure_occurrence_id'] = range(1, len(dedup_df) + 1)

    # Clean up temp columns
    dedup_df = dedup_df.drop(columns=['_date_str', '_proc_type', '_scan_date'], errors='ignore')

    # Standard OMOP columns
    for col, default in [
        ('procedure_datetime', None),
        ('procedure_end_date', None),
        ('procedure_end_datetime', None),
        ('modifier_concept_id', 0),
        ('quantity', None),
        ('provider_id', None),
        ('visit_detail_id', None),
        ('procedure_source_concept_id', 0),
        ('modifier_source_value', None),
    ]:
        if col not in dedup_df.columns:
            dedup_df[col] = default

    print(f"  Created {len(dedup_df)} procedure_occurrence records "
          f"(from {len(proc_df)} raw, deduplicated)")
    return dedup_df
