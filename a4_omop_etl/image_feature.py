"""
IMAGE_FEATURE table (Park et al. 2025 MI-CDM extension).

Polymorphic bridge linking image_occurrence to clinical domain tables
(measurement, observation, condition) via the event pattern:
  image_feature_event_field_concept_id  = concept for the target table's PK field
  image_feature_event_id               = the actual PK value

For A4/LEARN, all image features link to measurement.measurement_id
(concept 1147330).

Pipeline provenance is captured via alg_system URN strings.
Related features from the same analysis share an image_finding_id.
"""

import pandas as pd

from . import concepts

IMAGE_FINDING_CONCEPTS = concepts.load_image_finding_concepts()
IMAGE_FEATURE_TYPE_CONCEPTS = concepts.load_image_feature_type_concepts()

# OMOP concept_id for the measurement.measurement_id FIELD (concept_class_id='Field').
# 1147330 is the *table* concept 'measurement' (concept_class_id='Table'); it does not
# identify a column, which breaks the MI-CDM polymorphic join for generic consumers.
_MEASUREMENT_FIELD_CONCEPT_ID = 1147138

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

# Maps _mi_cdm_series_type → (DICOM modality for study UID matching)
_SERIES_TO_MODALITY = {
    'T1_VOLUMETRIC':  'MR',
    'SWI_READS':      'MR',
    'FLAIR':          'MR',
    'AMYLOID_PET':    'PT',
    'TAU_PET':        'PT',
    'RETINAL':        'OP',
}


def create_image_feature(
    measurement_df: pd.DataFrame,
    image_occurrence_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build IMAGE_FEATURE table per Park et al. 2025.

    Links each imaging measurement to its image_occurrence via
    the polymorphic event pattern, with pipeline provenance
    (alg_system) and finding grouping (image_finding_id).
    """
    print("\n--- MI-CDM: IMAGE_FEATURE (Bridge) ---")

    if '_mi_cdm_modality' not in measurement_df.columns:
        print("  No MI-CDM annotations found on measurements")
        return pd.DataFrame()

    # Filter to imaging measurements only (those with MI-CDM annotations)
    imaging_mask = measurement_df['_mi_cdm_modality'].notna()
    imaging_meas = measurement_df[imaging_mask].copy()

    if len(imaging_meas) == 0:
        print("  No imaging measurements found")
        return pd.DataFrame()

    # Normalize dates to YYYY-MM-DD strings for matching
    io_lookup = image_occurrence_df.copy()
    io_lookup['_date_str'] = pd.to_datetime(io_lookup['image_occurrence_date']).dt.strftime('%Y-%m-%d')

    # Also normalize measurement dates
    imaging_meas['_date_str'] = pd.to_datetime(imaging_meas['measurement_date']).dt.strftime('%Y-%m-%d')

    features = []
    finding_id_counter = 0

    # Group imaging measurements by (person_id, date, _mi_cdm_series_type, _mi_cdm_pipeline)
    # Each group shares an image_finding_id
    group_cols = ['person_id', '_date_str', '_mi_cdm_series_type', '_mi_cdm_pipeline']
    for group_key, group_df in imaging_meas.groupby(group_cols, dropna=False):
        person_id, date_str, series_type, pipeline = group_key

        if pd.isna(person_id) or pd.isna(date_str):
            continue

        finding_id_counter += 1

        # Find matching image_occurrence
        match = io_lookup[
            (io_lookup['person_id'] == person_id) &
            (io_lookup['_date_str'] == date_str)
        ]

        if len(match) == 0:
            continue

        # If multiple matches, pick the one with matching modality
        if len(match) > 1:
            expected_modality = _SERIES_TO_MODALITY.get(series_type)
            if expected_modality:
                from . import concepts as _c
                modality_concepts = _c.load_modality_concepts()
                expected_concept_id = modality_concepts.get(expected_modality)
                modality_match = match[match['modality_concept_id'] == expected_concept_id]
                if len(modality_match) > 0:
                    match = modality_match

        io_id = match.iloc[0]['image_occurrence_id']

        # Determine alg_system and finding concept
        pipeline_str = str(pipeline) if pd.notna(pipeline) else ''
        alg_system = _PIPELINE_TO_ALG_SYSTEM.get(pipeline_str, f'urn:a4:pipeline:{pipeline_str.lower()}')
        finding_key = _PIPELINE_TO_FINDING.get(pipeline_str, 'brain_volume')
        finding_concept_id = IMAGE_FINDING_CONCEPTS.get(finding_key, 0)

        # Get anatomic_site from the matched image_occurrence
        anatomic_site = match.iloc[0].get('anatomic_site_concept_id', 0)

        for _, mrow in group_df.iterrows():
            features.append({
                'person_id': person_id,
                'image_occurrence_id': io_id,
                'image_feature_event_field_concept_id': _MEASUREMENT_FIELD_CONCEPT_ID,
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

    # Reorder columns per Park et al. 2025 Table 3
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
    print(f"  Unique findings: {finding_id_counter}")
    print(f"  Pipelines: {result['alg_system'].nunique()}")
    return result


def strip_mi_cdm_annotations(measurement_df: pd.DataFrame) -> pd.DataFrame:
    """Remove temporary _mi_cdm_* columns before final measurement export."""
    mi_cdm_cols = [c for c in measurement_df.columns if c.startswith('_mi_cdm_')]
    if mi_cdm_cols:
        measurement_df = measurement_df.drop(columns=mi_cdm_cols)
    return measurement_df
