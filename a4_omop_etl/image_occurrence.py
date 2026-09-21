"""
IMAGE_OCCURRENCE table (Park et al. 2025 MI-CDM extension).

One row per imaging series.  Two builders feed the table:

  1. JSON-derived rows (authoritative for MR/PT): one row per series in
     the A4_JSONS dcm2niix sidecar index, at true DICOM-series grain,
     with local_path pointing at the sidecar file.
  2. Tabular-derived rows (fallback): the original synthesis from
     imaging results files, kept only for series with no sidecar -
     retinal (OP) imaging and results whose scans have no JSON.

Sidecars are de-identified (no DICOM UIDs), so UIDs are synthetic but
deterministic: all sequences of one modality at one visit share a study
UID; each series gets its own series UID.

Links to procedure_occurrence for provenance (NOT NULL per the MI-CDM
guide DDL) and visit_occurrence for clinical context.
"""

import hashlib

import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date

PROCEDURE_CONCEPTS = concepts.load_procedure_concepts()
MODALITY_CONCEPTS = concepts.load_modality_concepts()

# SNOMED standard concepts, Spec Anatomic Site domain (Park & Jeon et al.
# 2024 Table 2): 4133034 = Brain structure, 4305329 = Eye structure
_BRAIN = 4133034
_EYE = 4305329

# Maps _mi_cdm_series_type to (DICOM modality, anatomic_site_concept_id)
_SERIES_CONFIG = {
    'T1_VOLUMETRIC':  ('MR', _BRAIN),
    'SWI_READS':      ('MR', _BRAIN),
    'FLAIR':          ('MR', _BRAIN),
    'AMYLOID_PET':    ('PT', _BRAIN),
    'TAU_PET':        ('PT', _BRAIN),
    'RETINAL':        ('OP', _EYE),
}

# Tabular series type -> JSON filename sequence, for deduplication:
# a tabular row is dropped when a sidecar covers the same scan.
_SERIES_TO_SEQUENCE = {
    'T1_VOLUMETRIC': 'T1',
    'SWI_READS':     'T2_star',
    'FLAIR':         'FLAIR',
    'AMYLOID_PET':   'FBP',
    'TAU_PET':       'FTP',
    # RETINAL has no sidecars and is never dropped
}

# Maps each imaging source file key to procedure type and date column
_SOURCE_CONFIG = {
    'imaging_mri':       ('MRI_BRAIN',       'Date_DAYS_CONSENT',       'T1_VOLUMETRIC'),
    'imaging_amyloid':   ('PET_AMYLOID',     'scan_date_DAYS_CONSENT',  'AMYLOID_PET'),
    'imaging_tau':       ('PET_TAU',         'scan_date_DAYS_CONSENT',  'TAU_PET'),
    'imaging_mri_reads': ('MRI_BRAIN',       'STUDYDATE_DAYS_CONSENT',  'SWI_READS'),
    'imaging_flair':     ('MRI_BRAIN',       None,                      'FLAIR'),
    'imaging_retinal':   ('RETINAL_IMAGING', 'ExamDate_DAYS_CONSENT',   'RETINAL'),
    # imaging_pet_va, tau_petsurfer and tau_stanford are deliberately absent:
    # re-reads/re-analyses of scans already represented (screening PET via
    # imaging_amyloid + FBP sidecars; tau via imaging_tau + FTP sidecars).
    # Their tabular rows carried wrong dates (year-shifted read date;
    # VISCODE=2 stamp) and duplicated real series. Analysis provenance lives
    # in image_feature.alg_system, matching procedure_occurrence's config.
}

# Private working columns kept on the returned DataFrame for downstream
# linkage (image_feature, metadata measurements); dropped before export.
PRIVATE_COLUMNS = ['_sequence', '_series_type', '_rel_path', '_elem_idx', 'VISCODE']


def _synthetic_uid(seed: str) -> str:
    """Deterministic DICOM-format UID (2.25.{integer}) from a seed string."""
    h = hashlib.md5(seed.encode()).hexdigest()
    return f"2.25.{int(h[:24], 16)}"


def _build_json_rows(json_index: pd.DataFrame) -> pd.DataFrame:
    """One IMAGE_OCCURRENCE row per sidecar series (authoritative)."""
    if json_index is None or len(json_index) == 0:
        return pd.DataFrame()

    io = json_index[[
        'person_id', 'BID', 'VISCODE', '_sequence', '_modality_code',
        '_scan_date', '_date_str', 'visit_occurrence_id',
        '_procedure_occurrence_id', '_rel_path', '_elem_idx',
        '_n_elems', '_series_number',
    ]].copy()

    io['anatomic_site_concept_id'] = _BRAIN
    io['modality_concept_id'] = io['_modality_code'].map(MODALITY_CONCEPTS)
    io['procedure_occurrence_id'] = io['_procedure_occurrence_id']

    # Study UID: shared by all series of one modality at one visit.
    # Series UID: unique per sidecar file (and per array element).
    io['image_study_UID'] = io.apply(
        lambda r: _synthetic_uid(f"{r['BID']}|{r['VISCODE']}|{r['_modality_code']}"),
        axis=1)
    io['image_series_UID'] = io.apply(
        lambda r: _synthetic_uid(f"{r['_rel_path']}|{r['_elem_idx']}"), axis=1)

    io['local_path'] = io.apply(
        lambda r: r['_rel_path'] if r['_n_elems'] == 1
        else f"{r['_rel_path']}#series={r['_series_number']}", axis=1)
    io['wadors_uri'] = None
    io['image_occurrence_date'] = io['_scan_date']
    io['_series_type'] = None
    return io


def _build_tabular_rows(
    sources: dict,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """Original synthesis from imaging results files (fallback rows)."""
    all_rows = []
    for src_key, (proc_type, days_col, series_type) in _SOURCE_CONFIG.items():
        df = sources.get(src_key)
        if df is None or len(df) == 0:
            continue

        src_df = df.copy()
        if 'scan_analyzed' in src_df.columns:
            src_df = src_df[src_df['scan_analyzed'] == 'Yes'].copy()
        if len(src_df) == 0:
            continue

        has_viscode = 'VISCODE' in src_df.columns
        if days_col is None:
            merged = prepare_source_df(
                src_df, person_df, date_anchor_df,
                visit_occurrence_df, visit_extra_cols=['visit_start_date']
            )
            merged['_scan_date'] = merged['visit_start_date']
        else:
            if has_viscode:
                merged = prepare_source_df(
                    src_df, person_df, date_anchor_df, visit_occurrence_df,
                    visit_extra_cols=['visit_start_date']
                )
            else:
                merged = prepare_source_df(src_df, person_df, date_anchor_df)
            merged['_scan_date'] = merged.apply(
                calc_days_to_date, args=(days_col,), axis=1
            )
            # Fallback chain mirrors the measurement side exactly (scan date,
            # then visit date, never a consent date): a fabricated consent
            # date collapsed distinct visits in the dedup and mislinked 192
            # tau features to an amyloid series. Rows with no resolvable date
            # are skipped and counted below.
            mask = merged['_scan_date'].isna()
            if mask.any() and 'visit_start_date' in merged.columns:
                merged.loc[mask, '_scan_date'] = merged.loc[mask, 'visit_start_date']

        modality_code, anatomic_site = _SERIES_CONFIG[series_type]

        n_undated = int(merged['_scan_date'].isna().sum())
        if n_undated:
            print(f"  {src_key}: skipped {n_undated} tabular rows with no "
                  f"resolvable scan or visit date")
        for _, row in merged.iterrows():
            if pd.isna(row.get('_scan_date')):
                continue
            bid = row.get('BID', row.get('person_source_value', ''))
            all_rows.append({
                'person_id': row['person_id'],
                '_scan_date': row['_scan_date'],
                '_date_str': str(row['_scan_date']),
                '_series_type': series_type,
                '_modality_code': modality_code,
                'anatomic_site_concept_id': anatomic_site,
                'BID': bid,
                'VISCODE': row.get('VISCODE'),
                '_proc_type': proc_type,
                'visit_occurrence_id': row.get('visit_occurrence_id'),
            })

    if not all_rows:
        return pd.DataFrame()

    io = pd.DataFrame(all_rows)

    # Deduplicate within tabular sources: one row per (person, type, date)
    io = io.drop_duplicates(
        subset=['person_id', '_series_type', '_date_str'], keep='first').copy()

    io['_date_str'] = pd.to_datetime(io['_scan_date']).dt.strftime('%Y-%m-%d')
    io['image_study_UID'] = io.apply(
        lambda r: _synthetic_uid(f"{r['BID']}|{r['_date_str']}|{r['_modality_code']}"),
        axis=1)
    io['image_series_UID'] = io.apply(
        lambda r: _synthetic_uid(
            f"{r['BID']}|{r['_date_str']}|{r['_modality_code']}|{r['_series_type']}"),
        axis=1)
    io['modality_concept_id'] = io['_modality_code'].map(MODALITY_CONCEPTS)
    io['image_occurrence_date'] = io['_scan_date']
    io['wadors_uri'] = None
    io['local_path'] = None
    io['_sequence'] = io['_series_type'].map(_SERIES_TO_SEQUENCE)
    io['_rel_path'] = None
    io['_elem_idx'] = None
    return io


def create_image_occurrence(
    sources: dict,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    procedure_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    json_index: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Build IMAGE_OCCURRENCE per Park et al. 2025 / DICOM2OMOP MI-CDM guide.

    JSON sidecar series are authoritative; tabular results rows are kept
    only where no sidecar covers the same (person, sequence, visit) or
    (person, sequence, date). Returns the final columns plus
    PRIVATE_COLUMNS for downstream linkage (drop before export).
    """
    print("\n--- MI-CDM: IMAGE_OCCURRENCE ---")

    json_io = _build_json_rows(json_index)
    tab_io = _build_tabular_rows(
        sources, person_df, visit_occurrence_df, date_anchor_df)

    # Drop tabular rows covered by a sidecar series
    n_dropped = 0
    if len(json_io) > 0 and len(tab_io) > 0:
        by_visit = set(zip(json_io['person_id'], json_io['_sequence'],
                           json_io['VISCODE']))
        by_date = set(zip(json_io['person_id'], json_io['_sequence'],
                          json_io['_date_str']))
        covered = tab_io.apply(
            lambda r: pd.notna(r['_sequence']) and (
                (r['person_id'], r['_sequence'], r['VISCODE']) in by_visit or
                (r['person_id'], r['_sequence'], r['_date_str']) in by_date),
            axis=1)
        n_dropped = int(covered.sum())
        tab_io = tab_io[~covered].copy()

    # Link tabular rows to procedures by (person, concept, exact date)
    if len(tab_io) > 0:
        proc_type_to_concept = {k: v['concept_id']
                                for k, v in PROCEDURE_CONCEPTS.items()}
        tab_io['_proc_concept_id'] = tab_io['_proc_type'].map(proc_type_to_concept)
        if len(procedure_occurrence_df) > 0:
            proc_lookup = procedure_occurrence_df[
                ['procedure_occurrence_id', 'person_id',
                 'procedure_concept_id', 'procedure_date']].copy()
            proc_lookup['_proc_date_str'] = pd.to_datetime(
                proc_lookup['procedure_date']).dt.strftime('%Y-%m-%d')
            proc_lookup = proc_lookup.drop_duplicates(
                subset=['person_id', 'procedure_concept_id', '_proc_date_str'])
            tab_io = tab_io.merge(
                proc_lookup[['procedure_occurrence_id', 'person_id',
                             'procedure_concept_id', '_proc_date_str']],
                left_on=['person_id', '_proc_concept_id', '_date_str'],
                right_on=['person_id', 'procedure_concept_id', '_proc_date_str'],
                how='left')
        else:
            tab_io['procedure_occurrence_id'] = None

    parts = [df for df in (json_io, tab_io) if len(df) > 0]
    if not parts:
        print("  No image occurrences found")
        return pd.DataFrame()

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
    keep = final_cols[1:] + PRIVATE_COLUMNS + ['_date_str']
    io_df = pd.concat([p[[c for c in keep if c in p.columns]] for p in parts],
                      ignore_index=True)
    io_df['image_occurrence_id'] = range(1, len(io_df) + 1)
    io_df = io_df[final_cols + PRIVATE_COLUMNS + ['_date_str']]

    print(f"  Created {len(io_df)} image_occurrence records "
          f"({len(json_io)} from sidecars, "
          f"{len(io_df) - len(json_io)} tabular fallback; "
          f"{n_dropped} tabular rows superseded by sidecars)")
    return io_df
