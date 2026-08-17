import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date, finalize_measurement_df, safe_float

IMAGING_CONCEPTS = concepts.load_imaging_concepts()
IMAGING_EXTENDED = concepts.load_imaging_extended()


def create_measurement_imaging(
    mri_df: pd.DataFrame,
    amyloid_df: pd.DataFrame,
    tau_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from imaging files.

    Sources & Field Mappings (concept_maps/imaging.csv, group=core):
        imaging_mri.csv     -> dynamic ROI columns (2100000030, Brain Region Volume, mL)
                               | Date: EXAMD_DAYS_CONSENT
        imaging_amyloid.csv -> SUVR composite (2100000031, Amyloid PET SUVR, ratio)
                               | Date: EXAMD_DAYS_CONSENT
        imaging_tau.csv     -> SUVR per region (2100000032, Tau PET SUVR, ratio)
                               | Date: EXAMD_DAYS_CONSENT
    """
    measurements = []

    # ---- Volumetric MRI ----
    mri_filtered = prepare_source_df(mri_df.copy(), person_df, date_anchor_df)
    mri_filtered['measurement_date'] = mri_filtered.apply(
        calc_days_to_date, args=('Date_DAYS_CONSENT',), axis=1
    )

    # ROI columns, excluding metadata and date columns. The prefix match is anchored:
    # LeftCaudate and RightCaudate contain the letters 'date' but are ROIs.
    meta_cols = ['SUBSTUDY', 'BID', 'VISCODE', 'Date_DAYS_CONSENT',
                 'person_id', 'person_source_value', 'synthetic_consent_date', 'measurement_date']
    roi_cols = [c for c in mri_filtered.columns
                if c not in meta_cols and not c.startswith('Date_')]

    concept = IMAGING_CONCEPTS['MRI_VOLUME']
    for _, row in mri_filtered.iterrows():
        for roi in roi_cols:
            value = safe_float(row.get(roi))
            if value is not None:
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': concept['concept_id'],
                    'measurement_date': row.get('measurement_date'),
                    'value_as_number': value,
                    'unit_source_value': concept['unit'],
                    'visit_occurrence_id': None,
                    'measurement_source_value': f'MRI:{roi}',
                    '_mi_cdm_modality': 'MR',
                    '_mi_cdm_series_type': 'T1_VOLUMETRIC',
                    '_mi_cdm_pipeline': 'VOLUMETRIC_MRI',
                })

    mri_count = len(measurements)
    print(f"  Volumetric MRI: {len(mri_df)} rows -> {mri_count} measurements")

    # ---- Amyloid PET SUVR ----
    # scan_date_DAYS_CONSENT is not populated for every scan; the visit join supplies
    # a fallback date and populates visit_occurrence_id.
    amyloid_filtered = prepare_source_df(
        amyloid_df[amyloid_df['scan_analyzed'] == 'Yes'].copy(), person_df, date_anchor_df,
        visit_occurrence_df, visit_extra_cols=['visit_start_date']
    )
    amyloid_filtered['measurement_date'] = amyloid_filtered.apply(
        calc_days_to_date, args=('scan_date_DAYS_CONSENT',), axis=1
    )
    _no_scan_date = amyloid_filtered['measurement_date'].isna()
    amyloid_filtered.loc[_no_scan_date, 'measurement_date'] = \
        amyloid_filtered.loc[_no_scan_date, 'visit_start_date']

    concept = IMAGING_CONCEPTS['SUVR_AMYLOID']
    for _, row in amyloid_filtered.iterrows():
        value = safe_float(row.get('suvr_cer'))
        if value is not None:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept['concept_id'],
                'measurement_date': row.get('measurement_date'),
                'value_as_number': value,
                'unit_source_value': concept['unit'],
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"AMYLOID|{row.get('ligand', 'florbetapir')}|{row.get('brain_region', 'unknown')}|scan{row.get('scan_number', 'NA')}",
                '_mi_cdm_modality': 'PT',
                '_mi_cdm_series_type': 'AMYLOID_PET',
                '_mi_cdm_pipeline': 'SUVR_AMYLOID',
            })

    amyloid_count = len(measurements) - mri_count
    print(f"  Amyloid PET: {len(amyloid_df)} rows -> {amyloid_count} measurements")

    # ---- Tau PET SUVR ----
    # Same treatment as amyloid: visit date as fallback, and visit linkage.
    tau_filtered = prepare_source_df(
        tau_df[tau_df['scan_analyzed'] == 'Yes'].copy(), person_df, date_anchor_df,
        visit_occurrence_df, visit_extra_cols=['visit_start_date']
    )
    tau_filtered['measurement_date'] = tau_filtered.apply(
        calc_days_to_date, args=('scan_date_DAYS_CONSENT',), axis=1
    )
    _no_scan_date = tau_filtered['measurement_date'].isna()
    tau_filtered.loc[_no_scan_date, 'measurement_date'] = \
        tau_filtered.loc[_no_scan_date, 'visit_start_date']

    concept = IMAGING_CONCEPTS['SUVR_TAU']
    for _, row in tau_filtered.iterrows():
        # Tau uses suvr_persi or suvr_crus (suvr_cer is often NA)
        suvr_val = row.get('suvr_persi') if pd.notna(row.get('suvr_persi')) else row.get('suvr_cer')
        value = safe_float(suvr_val)
        if value is not None:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept['concept_id'],
                'measurement_date': row.get('measurement_date'),
                'value_as_number': value,
                'unit_source_value': concept['unit'],
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"TAU|{row.get('ligand', 'MK6240')}|{row.get('brain_region', 'unknown')}|scan{row.get('scan_number', 'NA')}",
                '_mi_cdm_modality': 'PT',
                '_mi_cdm_series_type': 'TAU_PET',
                '_mi_cdm_pipeline': 'SUVR_TAU',
            })

    tau_count = len(measurements) - mri_count - amyloid_count
    print(f"  Tau PET: {len(tau_df)} rows -> {tau_count} measurements")

    # Build DataFrame
    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"Created imaging MEASUREMENT with {len(measurement_df)} total records")
    return measurement_df


def create_measurement_imaging_extended(
    mri_reads_df: pd.DataFrame,
    flair_df: pd.DataFrame,
    retinal_df: pd.DataFrame,
    pet_va_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    tau_petsurfer_df: pd.DataFrame = None,
    tau_stanford_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from additional imaging files.

    Sources & Field Mappings (concept_maps/imaging.csv, group=extended):
        mri_reads    -> MCH (2100000070), LOBAR (2100000075), DEEP (2100000076)
        flair        -> WMH_VOL (2100000071), WMH_CORRECTED (2100000072), ICV (2100000077)
        retinal      -> RETINAL_AI (2100000073)
        pet_va       -> PET_VA_SUVR (2100000074)
        tau_petsurfer -> per-region SUVR (2100000078)
        tau_stanford  -> per-region SUVR (2100000079)
    """
    measurements = []

    # --- MRI Reads (microhemorrhage) ---
    mri_merged = prepare_source_df(mri_reads_df, person_df, date_anchor_df)
    print(f"  MRI Reads: {len(mri_reads_df)} total -> {len(mri_merged)} matched")

    mri_count = 0
    for _, row in mri_merged.iterrows():
        obs_date = calc_days_to_date(row, 'STUDYDATE_DAYS_CONSENT') or row['synthetic_consent_date']

        for field, col in [('MCH', 'Definite.MCH'), ('LOBAR', 'Lobar'), ('DEEP', 'Deep')]:
            if col in row and pd.notna(row[col]):
                concept = IMAGING_EXTENDED[field]
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': concept['concept_id'],
                    'measurement_date': obs_date,
                    'value_as_number': float(row[col]),
                    'unit_source_value': concept['unit'],
                    'visit_occurrence_id': None,
                    'measurement_source_value': f"MRI_READS:{field}",
                    '_mi_cdm_modality': 'MR',
                    '_mi_cdm_series_type': 'SWI_READS',
                    '_mi_cdm_pipeline': 'MRI_READS',
                })
                mri_count += 1

    # --- FLAIR WMH ---
    flair_merged = prepare_source_df(flair_df, person_df, date_anchor_df, visit_occurrence_df,
                                     visit_extra_cols=['visit_start_date'])
    print(f"  FLAIR WMH: {len(flair_df)} total -> {len(flair_merged)} matched")

    flair_count = 0
    for _, row in flair_merged.iterrows():
        for field, col in [('WMH_VOL', 'WMHvol_masked'), ('WMH_CORRECTED', 'WMH_corrected'), ('ICV', 'ICV')]:
            val = safe_float(row.get(col)) if col in row else None
            # WMHvol_masked and ICV are supplied in cubic mm; convert to mL to match the
            # volumetric MRI pipeline. WMH_corrected is not scaled: it is (WMHvol/ICV)*1300,
            # a volume normalized to a standard 1300 head.
            if field in ('WMH_VOL', 'ICV') and val is not None:
                val = val / 1000.0
            if val is not None:
                concept = IMAGING_EXTENDED[field]
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': concept['concept_id'],
                    'measurement_date': row.get('visit_start_date') if pd.notna(row.get('visit_start_date')) else row['synthetic_consent_date'],
                    'value_as_number': val,
                    'unit_source_value': concept['unit'],
                    'visit_occurrence_id': row.get('visit_occurrence_id'),
                    'measurement_source_value': f"FLAIR:{field}",
                    '_mi_cdm_modality': 'MR',
                    '_mi_cdm_series_type': 'FLAIR',
                    '_mi_cdm_pipeline': 'FLAIR_WMH',
                })
                flair_count += 1

    # --- Retinal (no VISCODE - use date) ---
    retinal_merged = prepare_source_df(retinal_df, person_df, date_anchor_df)
    print(f"  Retinal: {len(retinal_df)} total -> {len(retinal_merged)} matched")

    retinal_count = 0
    for _, row in retinal_merged.iterrows():
        if pd.notna(row.get('RAIModelScore')):
            obs_date = calc_days_to_date(row, 'ExamDate_DAYS_CONSENT') or row['synthetic_consent_date']

            concept = IMAGING_EXTENDED['RETINAL_AI']
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept['concept_id'],
                'measurement_date': obs_date,
                'value_as_number': float(row['RAIModelScore']),
                'unit_source_value': concept['unit'],
                'visit_occurrence_id': None,
                'measurement_source_value': f"RETINAL:Eye={row.get('Eye', 'NA')},Field={row.get('Field', 'NA')}",
                '_mi_cdm_modality': 'OP',
                '_mi_cdm_series_type': 'RETINAL',
                '_mi_cdm_pipeline': 'RETINAL_AI',
            })
            retinal_count += 1

    # --- PET VA ---
    pet_merged = prepare_source_df(pet_va_df, person_df, date_anchor_df)
    print(f"  PET VA: {len(pet_va_df)} total -> {len(pet_merged)} matched")

    pet_count = 0
    for _, row in pet_merged.iterrows():
        if pd.notna(row.get('pmod_suvr')):
            obs_date = calc_days_to_date(row, 'scan_date_DAYS_CONSENT') or row['synthetic_consent_date']

            concept = IMAGING_EXTENDED['PET_VA_SUVR']
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept['concept_id'],
                'measurement_date': obs_date,
                'value_as_number': float(row['pmod_suvr']),
                'unit_source_value': concept['unit'],
                'visit_occurrence_id': None,
                'measurement_source_value': f"PET_VA:ligand={row.get('ligand', 'NA')}",
                '_mi_cdm_modality': 'PT',
                '_mi_cdm_series_type': 'AMYLOID_PET',
                '_mi_cdm_pipeline': 'PET_VA',
            })
            pet_count += 1

    # --- Tau PET PetSurfer (alternative pipeline) ---
    petsurfer_count = 0
    if tau_petsurfer_df is not None:
        # Compute region_cols from the original df, before merging adds extra columns.
        # bi_* is bilateral PVC SUVR and PVC_* is regional PVC SUVR. NumVoxels_* holds
        # voxel counts for volume-weighting when combining regions, not measurements.
        region_cols = [c for c in tau_petsurfer_df.columns if c.startswith(('bi_', 'PVC_'))]
        ps_merged = prepare_source_df(tau_petsurfer_df, person_df, date_anchor_df, visit_occurrence_df,
                                      visit_extra_cols=['visit_start_date'])
        print(f"  Tau PetSurfer: {len(tau_petsurfer_df)} total -> {len(ps_merged)} matched")

        concept = IMAGING_EXTENDED['TAU_PETSURFER']
        for _, row in ps_merged.iterrows():
            for region in region_cols:
                val = safe_float(row.get(region))
                if val is not None:
                    measurements.append({
                        'person_id': row['person_id'],
                        'measurement_concept_id': concept['concept_id'],
                        'measurement_date': row.get('visit_start_date') if pd.notna(row.get('visit_start_date')) else row['synthetic_consent_date'],
                        'value_as_number': val,
                        'unit_source_value': concept['unit'],
                        'visit_occurrence_id': row.get('visit_occurrence_id'),
                        'measurement_source_value': f"TAU_PETSURFER:{region}",
                        '_mi_cdm_modality': 'PT',
                        '_mi_cdm_series_type': 'TAU_PET',
                        '_mi_cdm_pipeline': 'TAU_PETSURFER',
                    })
                    petsurfer_count += 1

    # --- Tau PET Stanford (alternative pipeline) ---
    stanford_count = 0
    if tau_stanford_df is not None:
        # Only include SUVR columns, NOT Volume_mm3 columns (those are brain volumes, not SUVR ratios)
        region_cols = [c for c in tau_stanford_df.columns
                       if c not in ['SUBSTUDY', 'BID', 'VISCODE'] and not c.startswith('Volume_mm3')]
        sf_merged = prepare_source_df(tau_stanford_df, person_df, date_anchor_df, visit_occurrence_df,
                                      visit_extra_cols=['visit_start_date'])
        print(f"  Tau Stanford: {len(tau_stanford_df)} total -> {len(sf_merged)} matched")

        concept = IMAGING_EXTENDED['TAU_STANFORD']
        for _, row in sf_merged.iterrows():
            for region in region_cols:
                val = safe_float(row.get(region))
                if val is not None:
                    measurements.append({
                        'person_id': row['person_id'],
                        'measurement_concept_id': concept['concept_id'],
                        'measurement_date': row.get('visit_start_date') if pd.notna(row.get('visit_start_date')) else row['synthetic_consent_date'],
                        'value_as_number': val,
                        'unit_source_value': concept['unit'],
                        'visit_occurrence_id': row.get('visit_occurrence_id'),
                        'measurement_source_value': f"TAU_STANFORD:{region}",
                        '_mi_cdm_modality': 'PT',
                        '_mi_cdm_series_type': 'TAU_PET',
                        '_mi_cdm_pipeline': 'TAU_STANFORD',
                    })
                    stanford_count += 1

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"Created extended imaging MEASUREMENT with {len(measurement_df)} records")
    print(f"  MRI: {mri_count}, FLAIR: {flair_count}, Retinal: {retinal_count}, PET_VA: {pet_count}, PetSurfer: {petsurfer_count}, Stanford: {stanford_count}")
    return measurement_df
