"""
IMAGE_FEATURE table (Park et al. 2025 MI-CDM extension).

Reserved for image-derived findings (per the updated DICOM2OMOP MI-CDM
guide): SUVRs, volumes, reads, WMH, retinal measures. DICOM header
metadata does NOT get image_feature rows - it lives in MEASUREMENT with
measurement_event_id linkage (see image_metadata.py).

Each feature links its image_occurrence to the clinical measurement via
the event pattern:
  image_feature_event_field_concept_id = 1147330 (the MEASUREMENT table
      concept, per the MI-CDM guide section 7)
  image_feature_event_id               = measurement_id

Pipeline provenance is captured via alg_system URN strings.
Related features from the same analysis share an image_finding_id.
"""

import pandas as pd

from . import concepts
from .image_occurrence import _SERIES_TO_SEQUENCE

IMAGE_FINDING_CONCEPTS = concepts.load_image_finding_concepts()
IMAGE_FEATURE_TYPE_CONCEPTS = concepts.load_image_feature_type_concepts()
MODALITY_CONCEPTS = concepts.load_modality_concepts()

# The MEASUREMENT table concept. The MI-CDM guide (section 7) specifies
# 1147330 for image_feature_event_field_concept_id; this supersedes the
# earlier use of 1147138 (the measurement.measurement_id Field concept).
_MEASUREMENT_TABLE_CONCEPT_ID = 1147330

# Maps _mi_cdm_pipeline annotation → alg_system URN
_PIPELINE_TO_ALG_SYSTEM = {
    'VOLUMETRIC_MRI':   'urn:a4:pipeline:volumetric_mri',
    'SUVR_AMYLOID':     'urn:a4:pipeline:suvr_amyloid',
    'SUVR_TAU':         'urn:a4:pipeline:suvr_tau',
    'TAU_PETSURFER':    'urn:a4:pipeline:petsurfer',
    'TAU_STANFORD':     'urn:a4:pipeline:stanford',
    'MRI_READS':        'urn:a4:pipeline:mri_reads',
    'FLAIR_WMH':        'urn:a4:pipeline:flair_wmh',
    'RETINAL_AI':       'urn:a4:pipeline:retinal_ai',
    'PET_VA':           'urn:a4:pipeline:pet_visual_assessment',
}

# Maps _mi_cdm_pipeline → image_finding source_code (for concept lookup)
_PIPELINE_TO_FINDING = {
    'VOLUMETRIC_MRI':   'brain_volume',
    'SUVR_AMYLOID':     'amyloid_suvr',
    'SUVR_TAU':         'tau_suvr',
    'TAU_PETSURFER':    'tau_suvr',
    'TAU_STANFORD':     'tau_suvr',
    'MRI_READS':        'mri_read',
    'FLAIR_WMH':        'flair_volume',
    'RETINAL_AI':       'retinal_measure',
    'PET_VA':           'pet_visual_assessment',
}

# Maps _mi_cdm_series_type → DICOM modality (for fallback matching)
_SERIES_TO_MODALITY = {
    'T1_VOLUMETRIC':  'MR',
    'SWI_READS':      'MR',
    'FLAIR':          'MR',
    'AMYLOID_PET':    'PT',
    'TAU_PET':        'PT',
    'RETINAL':        'OP',
}


def _pick_occurrence(person_io, series_type, visit_id, date_str, viscode=None):
    """Pick the best-matching image_occurrence for a feature group.

    Preference order:
      1. same acquisition VISCODE, matching sequence/series type
      2. same visit, matching sequence/series type
      3. same date, matching sequence/series type
      4. same visit or date, matching modality
      5. same date, any

    VISCODE comes first because some sources (e.g. PET visual reads) date
    their rows by the read date - years after acquisition - while the
    VISCODE names the scan visit.
    """
    if person_io is None or len(person_io) == 0:
        return None

    seq = _SERIES_TO_SEQUENCE.get(series_type)
    modality_id = MODALITY_CONCEPTS.get(_SERIES_TO_MODALITY.get(series_type))

    type_mask = pd.Series(False, index=person_io.index)
    if seq is not None:
        type_mask |= person_io['_sequence'] == seq
    type_mask |= person_io['_series_type'] == series_type

    viscode_mask = (person_io['VISCODE'] == viscode
                    if viscode else pd.Series(False, index=person_io.index))
    visit_mask = (person_io['visit_occurrence_id'] == visit_id
                  if pd.notna(visit_id) else pd.Series(False, index=person_io.index))
    date_mask = person_io['_date_str'] == date_str
    modality_mask = (person_io['modality_concept_id'] == modality_id
                     if modality_id else pd.Series(False, index=person_io.index))

    for mask in (viscode_mask & type_mask,
                 visit_mask & type_mask, date_mask & type_mask,
                 visit_mask & modality_mask, date_mask & modality_mask,
                 date_mask):
        hit = person_io[mask]
        if len(hit) > 0:
            return hit.iloc[0]
    return None


def create_image_feature(
    measurement_df: pd.DataFrame,
    image_occurrence_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build IMAGE_FEATURE per Park et al. 2025 for derived imaging results.

    Links each imaging measurement to its image_occurrence via the
    polymorphic event pattern, with pipeline provenance (alg_system)
    and finding grouping (image_finding_id). Occurrence matching
    prefers the shared visit, then the exact date, and picks the series
    matching the measurement's series type (e.g. FreeSurfer volumes ->
    the T1 series).
    """
    print("\n--- MI-CDM: IMAGE_FEATURE (Bridge) ---")

    if '_mi_cdm_modality' not in measurement_df.columns:
        print("  No MI-CDM annotations found on measurements")
        return pd.DataFrame()

    imaging_mask = measurement_df['_mi_cdm_modality'].notna()
    imaging_meas = measurement_df[imaging_mask].copy()
    if len(imaging_meas) == 0:
        print("  No imaging measurements found")
        return pd.DataFrame()

    io_lookup = image_occurrence_df.copy()
    if '_date_str' not in io_lookup.columns:
        io_lookup['_date_str'] = pd.to_datetime(
            io_lookup['image_occurrence_date']).dt.strftime('%Y-%m-%d')
    io_by_person = dict(tuple(io_lookup.groupby('person_id')))

    imaging_meas['_date_str'] = pd.to_datetime(
        imaging_meas['measurement_date']).dt.strftime('%Y-%m-%d')

    features = []
    finding_id_counter = 0
    unmatched_groups = 0

    if '_mi_cdm_viscode' not in imaging_meas.columns:
        imaging_meas['_mi_cdm_viscode'] = None
    group_cols = ['person_id', '_date_str', '_mi_cdm_series_type',
                  '_mi_cdm_pipeline', '_mi_cdm_viscode']
    for group_key, group_df in imaging_meas.groupby(group_cols, dropna=False):
        person_id, date_str, series_type, pipeline, viscode = group_key
        if pd.isna(person_id) or pd.isna(date_str):
            continue

        finding_id_counter += 1

        visit_ids = group_df['visit_occurrence_id'].dropna()
        visit_id = visit_ids.iloc[0] if len(visit_ids) else None
        match = _pick_occurrence(io_by_person.get(person_id),
                                 series_type, visit_id, date_str,
                                 viscode=viscode if pd.notna(viscode) else None)
        if match is None:
            unmatched_groups += 1
            continue

        io_id = match['image_occurrence_id']
        anatomic_site = match.get('anatomic_site_concept_id', 0)

        pipeline_str = str(pipeline) if pd.notna(pipeline) else ''
        alg_system = _PIPELINE_TO_ALG_SYSTEM.get(
            pipeline_str, f'urn:a4:pipeline:{pipeline_str.lower()}')
        finding_key = _PIPELINE_TO_FINDING.get(pipeline_str, 'brain_volume')
        finding_concept_id = IMAGE_FINDING_CONCEPTS.get(finding_key, 0)

        for _, mrow in group_df.iterrows():
            features.append({
                'person_id': person_id,
                'image_occurrence_id': io_id,
                'image_feature_event_field_concept_id': _MEASUREMENT_TABLE_CONCEPT_ID,
                'image_feature_event_id': mrow['measurement_id'],
                'image_feature_concept_id': mrow.get('measurement_concept_id', 0),
                'image_feature_type_concept_id': IMAGE_FEATURE_TYPE_CONCEPTS.get('derived', 32880),
                'image_finding_concept_id': finding_concept_id,
                'image_finding_id': finding_id_counter,
                'anatomic_site_concept_id': anatomic_site,
                'alg_system': alg_system,
                'alg_datetime': None,
            })

    if not features:
        print("  No image features created")
        return pd.DataFrame()

    feat_df = pd.DataFrame(features)
    feat_df = feat_df.reset_index(drop=True)
    feat_df['image_feature_id'] = range(1, len(feat_df) + 1)

    final_cols = [
        'image_feature_id',
        'person_id',
        'image_occurrence_id',
        'image_feature_event_field_concept_id',
        'image_feature_event_id',
        'image_feature_concept_id',
        'image_feature_type_concept_id',
        'image_finding_concept_id',
        'image_finding_id',
        'anatomic_site_concept_id',
        'alg_system',
        'alg_datetime',
    ]
    result = feat_df[final_cols].copy()

    print(f"  Created {len(result)} image_feature records")
    print(f"  Unique findings: {finding_id_counter} "
          f"({unmatched_groups} groups had no matching image_occurrence)")
    print(f"  Pipelines: {result['alg_system'].nunique()}")
    return result


def backfill_measurement_event_links(
    measurement_df: pd.DataFrame,
    image_feature_df: pd.DataFrame,
    field_concept_id: int,
) -> pd.DataFrame:
    """
    Point derived imaging measurements back at their source series.

    Per the MI-CDM guide section 7, quantitative feature results in
    MEASUREMENT also carry measurement_event_id = image_occurrence_id
    and meas_event_field_concept_id = the image_occurrence_id field
    concept.
    """
    if len(image_feature_df) == 0 or len(measurement_df) == 0:
        return measurement_df

    m2io = dict(zip(image_feature_df['image_feature_event_id'],
                    image_feature_df['image_occurrence_id']))
    for col in ('measurement_event_id', 'meas_event_field_concept_id'):
        if col not in measurement_df.columns:
            measurement_df[col] = None

    mapped = measurement_df['measurement_id'].map(m2io)
    mask = mapped.notna()
    measurement_df.loc[mask, 'measurement_event_id'] = mapped[mask]
    measurement_df.loc[mask, 'meas_event_field_concept_id'] = field_concept_id
    print(f"  Backfilled measurement_event_id on {int(mask.sum()):,} "
          f"derived imaging measurements")
    return measurement_df


def strip_mi_cdm_annotations(measurement_df: pd.DataFrame) -> pd.DataFrame:
    """Remove temporary _mi_cdm_* columns before final measurement export."""
    mi_cdm_cols = [c for c in measurement_df.columns if c.startswith('_mi_cdm_')]
    if mi_cdm_cols:
        measurement_df = measurement_df.drop(columns=mi_cdm_cols)
    return measurement_df
