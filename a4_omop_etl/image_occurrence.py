"""
IMAGE_OCCURRENCE table (Park et al. 2025 MI-CDM extension).

One row per DICOM series equivalent, identified by
(person, modality, series_type, date).  Links to
procedure_occurrence for provenance and visit_occurrence
for clinical context.

Each row receives synthetic DICOM UIDs (study and series)
since real DICOM metadata is not available in A4/LEARN.
"""

import hashlib

import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date

PROCEDURE_CONCEPTS = concepts.load_procedure_concepts()
MODALITY_CONCEPTS = concepts.load_modality_concepts()

# Maps _mi_cdm_modality annotation values to DICOM modality codes
_MODALITY_MAP = {
    'MR': 'MR',
    'PT': 'PT',
    'OP': 'OP',
}

# Maps _mi_cdm_series_type to (DICOM modality, anatomic_site_concept_id).
# anatomic_site_concept_id values are SNOMED standard concepts in the
# Spec Anatomic Site domain (per Park & Jeon et al. 2024 Table 2):
#   4133034 = Brain structure (SNOMED 12738006)
#   4305329 = Eye structure (SNOMED 81745001)
_SERIES_CONFIG = {
    'T1_VOLUMETRIC':  ('MR', 4133034),
    'SWI_READS':      ('MR', 4133034),
    'FLAIR':          ('MR', 4133034),
    'AMYLOID_PET':    ('PT', 4133034),
    'TAU_PET':        ('PT', 4133034),
    'RETINAL':        ('OP', 4305329),
}

# Maps each imaging source file key to procedure type and date column
_SOURCE_CONFIG = {
    'imaging_mri':       ('MRI_BRAIN',       'Date_DAYS_CONSENT',       'T1_VOLUMETRIC'),
    'imaging_amyloid':   ('PET_AMYLOID',     'scan_date_DAYS_CONSENT',  'AMYLOID_PET'),
    'imaging_tau':       ('PET_TAU',         'scan_date_DAYS_CONSENT',  'TAU_PET'),
    'imaging_mri_reads': ('MRI_BRAIN',       'STUDYDATE_DAYS_CONSENT',  'SWI_READS'),
    'imaging_flair':     ('MRI_BRAIN',       None,                      'FLAIR'),
    'imaging_retinal':   ('RETINAL_IMAGING', 'ExamDate_DAYS_CONSENT',   'RETINAL'),
    'imaging_pet_va':    ('PET_AMYLOID',     'scan_date_DAYS_CONSENT',  'AMYLOID_PET'),
    'tau_petsurfer':     ('PET_TAU',         None,                      'TAU_PET'),
    'tau_stanford':      ('PET_TAU',         None,                      'TAU_PET'),
}


def _synthetic_uid(seed: str) -> str:
    """Generate a deterministic DICOM-format UID from a seed string.

    Uses the 2.25.{integer} format per DICOM standard for UUID-derived UIDs.
    """
    h = hashlib.md5(seed.encode()).hexdigest()
    return f"2.25.{int(h[:24], 16)}"


def create_image_occurrence(
    sources: dict,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    procedure_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build IMAGE_OCCURRENCE table per Park et al. 2025.

    One row per unique (person_id, series_type, scan_date).
    Links to procedure_occurrence and visit_occurrence.
    Generates synthetic DICOM study/series UIDs.
    """
    print("\n--- MI-CDM: IMAGE_OCCURRENCE ---")
    all_rows = []

    for src_key, (proc_type, days_col, series_type) in _SOURCE_CONFIG.items():
        df = sources.get(src_key)
        if df is None or len(df) == 0:
            continue

        src_df = df.copy()

        # Filter analyzed-only for PET sources
        if 'scan_analyzed' in src_df.columns:
            src_df = src_df[src_df['scan_analyzed'] == 'Yes'].copy()
        if len(src_df) == 0:
            continue

        # Merge with person, date anchor, and visit (when VISCODE available)
        # Visit linkage works via VISCODE for all sources except imaging_retinal.
        has_viscode = 'VISCODE' in src_df.columns
        if days_col is None:
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
            # Pass visit_occurrence_df when VISCODE available so visit_occurrence_id
            # is populated even when image_occurrence_date comes from the date column.
            if has_viscode:
                merged = prepare_source_df(
                    src_df, person_df, date_anchor_df, visit_occurrence_df
                )
            else:
                merged = prepare_source_df(src_df, person_df, date_anchor_df)
            merged['_scan_date'] = merged.apply(
                calc_days_to_date, args=(days_col,), axis=1
            )
            mask = merged['_scan_date'].isna()
            if mask.any():
                merged.loc[mask, '_scan_date'] = merged.loc[mask, 'synthetic_consent_date']

        modality_code, anatomic_site = _SERIES_CONFIG[series_type]

        for _, row in merged.iterrows():
            if pd.isna(row.get('_scan_date')):
                continue
            bid = row.get('BID', row.get('person_source_value', ''))
            date_str = str(row['_scan_date'])
            all_rows.append({
                'person_id': row['person_id'],
                '_scan_date': row['_scan_date'],
                '_date_str': date_str,
                '_series_type': series_type,
                '_modality_code': modality_code,
                '_anatomic_site': anatomic_site,
                '_bid': bid,
                '_proc_type': proc_type,
                'visit_occurrence_id': row.get('visit_occurrence_id'),
            })

    if not all_rows:
        print("  No image occurrences found")
        return pd.DataFrame()

    io_df = pd.DataFrame(all_rows)

    # Deduplicate: one image_occurrence per (person_id, series_type, date)
    io_df = io_df.drop_duplicates(
        subset=['person_id', '_series_type', '_date_str'],
        keep='first'
    ).copy()

    # Generate synthetic DICOM UIDs
    io_df['image_study_UID'] = io_df.apply(
        lambda r: _synthetic_uid(f"{r['_bid']}|{r['_date_str']}|{r['_modality_code']}"),
        axis=1
    )
    io_df['image_series_UID'] = io_df.apply(
        lambda r: _synthetic_uid(f"{r['_bid']}|{r['_date_str']}|{r['_modality_code']}|{r['_series_type']}"),
        axis=1
    )

    # Map modality concept
    io_df['modality_concept_id'] = io_df['_modality_code'].map(MODALITY_CONCEPTS)

    # Map anatomic site
    io_df['anatomic_site_concept_id'] = io_df['_anatomic_site']

    # Normalize _date_str to YYYY-MM-DD for matching
    io_df['_date_str'] = pd.to_datetime(io_df['_scan_date']).dt.strftime('%Y-%m-%d')

    # Link to procedure_occurrence
    if len(procedure_occurrence_df) > 0:
        # Build procedure lookup: (person_id, procedure_concept_id, date_str) -> procedure_occurrence_id
        proc_lookup = procedure_occurrence_df[['procedure_occurrence_id', 'person_id',
                                                'procedure_concept_id', 'procedure_date']].copy()
        proc_lookup['_proc_date_str'] = pd.to_datetime(proc_lookup['procedure_date']).dt.strftime('%Y-%m-%d')

        # Map proc_type to procedure_concept_id
        proc_type_to_concept = {k: v['concept_id'] for k, v in PROCEDURE_CONCEPTS.items()}
        io_df['_proc_concept_id'] = io_df['_proc_type'].map(proc_type_to_concept)

        io_df = io_df.merge(
            proc_lookup[['procedure_occurrence_id', 'person_id', 'procedure_concept_id', '_proc_date_str']],
            left_on=['person_id', '_proc_concept_id', '_date_str'],
            right_on=['person_id', 'procedure_concept_id', '_proc_date_str'],
            how='left'
        )
    else:
        io_df['procedure_occurrence_id'] = None

    # Assign sequential IDs and finalize columns
    io_df = io_df.reset_index(drop=True)
    io_df['image_occurrence_id'] = range(1, len(io_df) + 1)
    io_df['image_occurrence_date'] = io_df['_scan_date']
    io_df['wadors_uri'] = None
    io_df['local_path'] = None

    # Select final columns per Park et al. 2025 Table 2
    final_cols = [
        'image_occurrence_id',
        'person_id',
        'procedure_occurrence_id',
        'visit_occurrence_id',
        'anatomic_site_concept_id',
        'wadors_uri',
        'local_path',
        'image_occurrence_date',
        'image_study_UID',
        'image_series_UID',
        'modality_concept_id',
    ]
    result = io_df[final_cols].copy()

    print(f"  Created {len(result)} image_occurrence records")
    return result
