"""
DICOM sidecar metadata ingestion (A4_JSONS) for the MI-CDM extension.

A4_JSONS holds one dcm2niix BIDS-sidecar JSON per acquired imaging series
(a few PET files are JSON arrays holding multiple reconstruction series).
Filenames encode {A4|LEARN|SF}_{MR|PET}_{sequence}_{BID}_{VISCODE}.json.

This module:
  1. Scans the directory into a series-level index linked to person,
     visit, and date anchor (build_image_json_index).
  2. Extends PROCEDURE_OCCURRENCE with imaging sessions that have no
     results-file procedure (extend_procedures_from_json) - notably
     screen-fail screening PETs and MR-only sessions.
  3. Emits DICOM acquisition metadata as MEASUREMENT rows linked to
     their IMAGE_OCCURRENCE via measurement_event_id per the DICOM2OMOP
     "ETL Guide for Loading DICOM Data into OMOP Using MI-CDM" section 5
     (create_dicom_metadata_measurements).

Sidecars are fully de-identified: no dates, no DICOM UIDs, no Patient ID.
Dates come from the linked visit; series whose visit code has no SV row
(early termination, code 999) are dated from the scan dates in the tabular
results files, and series with no resolvable date at all are dropped and
reported rather than stamped with a fabricated date. UIDs are synthetic,
and person/visit resolve from the filename BID/VISCODE.
"""

import json
import re

import pandas as pd

from . import concepts
from .config import IMAGE_JSON_DIR, BASE_DIR

# Custom A4_LEARN field concept for image_occurrence.image_occurrence_id.
# No standard concept exists for extension-table fields; used as
# meas_event_field_concept_id on every DICOM-derived measurement row.
IMAGE_OCCURRENCE_FIELD_CONCEPT_ID = 2100000532

DICOM_ATTRIBUTES = concepts.load_dicom_attribute_map()
DICOM_VALUE_MAP = concepts.load_dicom_value_map()
RADIOPHARM_CONCEPTS = concepts.load_radiopharmaceutical_concepts()

_FNAME_RE = re.compile(r'^(A4|LEARN|SF)_(MR|PET)_(.+)_(B\d+)_(\d+)\.json$')

# Filename sequence -> procedure type key in concept_maps/procedures.csv
SEQUENCE_TO_PROC = {
    'T1': 'MRI_BRAIN', 'FLAIR': 'MRI_BRAIN', 'T2_SE': 'MRI_BRAIN',
    'T2_star': 'MRI_BRAIN', 'b0CD': 'MRI_BRAIN', 'DWI': 'MRI_BRAIN',
    'FBP': 'PET_AMYLOID', 'FTP': 'PET_TAU',
}

# Filename modality -> DICOM modality code (concept_maps/modalities.csv)
_FILENAME_MODALITY = {'MR': 'MR', 'PET': 'PT'}


def _tabular_scan_dates(sources) -> dict:
    """
    (BID, zero-padded VISCODE, modality) -> earliest scan-day offset,
    from the dated tabular results files.

    Used to date sidecar series whose visit code has no SV row (early
    termination, code 999): the SUVR/volumetric files record scan dates
    for those same scans on the shared days-from-consent scale.
    """
    if not sources:
        return {}
    specs = [
        ('imaging_tau',       'scan_date_DAYS_CONSENT',  'PT'),
        ('imaging_amyloid',   'scan_date_DAYS_CONSENT',  'PT'),
        ('imaging_mri',       'Date_DAYS_CONSENT',       'MR'),
        ('imaging_mri_reads', 'STUDYDATE_DAYS_CONSENT',  'MR'),
    ]
    lookup = {}
    for name, col, modality in specs:
        df = sources.get(name)
        if df is None or col not in df.columns:
            continue
        sub = df[['BID', 'VISCODE', col]].dropna()
        for bid, viscode, days in sub.itertuples(index=False):
            try:
                key = (bid, str(int(float(viscode))).zfill(3), modality)
                days = int(days)
            except (TypeError, ValueError):
                continue
            if key not in lookup or days < lookup[key]:
                lookup[key] = days
    return lookup


def build_image_json_index(
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    sources: dict = None,
) -> pd.DataFrame:
    """
    Scan A4_JSONS into a series-level index DataFrame.

    One row per series (per array element for multi-reconstruction PET
    files), with whitelisted DICOM attributes as columns plus person,
    visit, and scan-date linkage.
    """
    print("\n--- MI-CDM: Scanning A4_JSONS sidecar metadata ---")
    if not IMAGE_JSON_DIR.exists():
        print(f"  {IMAGE_JSON_DIR} not found - skipping JSON metadata")
        return pd.DataFrame()

    whitelist = list(DICOM_ATTRIBUTES.keys())
    rows = []
    n_files = 0
    n_unparsed = 0
    for path in IMAGE_JSON_DIR.rglob('*.json'):
        m = _FNAME_RE.match(path.name)
        if not m:
            n_unparsed += 1
            continue
        study, fmod, sequence, bid, viscode = m.groups()
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            n_unparsed += 1
            continue
        n_files += 1
        elems = data if isinstance(data, list) else [data]
        rel_path = str(path.relative_to(BASE_DIR))
        for i, elem in enumerate(elems):
            if not isinstance(elem, dict):
                continue
            row = {
                '_study': study,
                '_sequence': sequence,
                '_modality_code': elem.get('Modality') or _FILENAME_MODALITY[fmod],
                'BID': bid,
                'VISCODE': viscode.zfill(3),
                '_rel_path': rel_path,
                '_elem_idx': i,
                '_n_elems': len(elems),
                '_series_number': elem.get('SeriesNumber'),
            }
            for key in whitelist:
                if key in elem:
                    row[key] = elem[key]
            rows.append(row)

    index = pd.DataFrame(rows)
    print(f"  {n_files} files scanned -> {len(index)} series "
          f"({n_unparsed} unparseable)")
    if len(index) == 0:
        return index

    # Person, visit, and date linkage (mirrors helpers.prepare_source_df,
    # done directly here because VISCODE is already normalized).
    person_lookup = person_df[['person_id', 'person_source_value']]
    index = index.merge(person_lookup, left_on='BID',
                        right_on='person_source_value', how='inner')
    index = index.merge(date_anchor_df[['BID', 'synthetic_consent_date']],
                        on='BID', how='left')
    index['visit_source_value'] = index['BID'] + '_' + index['VISCODE']
    visit_lookup = visit_occurrence_df[
        ['visit_occurrence_id', 'visit_source_value', 'visit_start_date', 'person_id']
    ]
    index = index.merge(visit_lookup, on=['visit_source_value', 'person_id'], how='left')

    # Scan date: visit date when linked; otherwise the tabular results
    # files' scan date for the same (BID, VISCODE, modality) — this dates
    # the early-termination series (VISCODE 999 has no SV row). Sidecars
    # carry no dates themselves, and a consent date is never substituted:
    # a series with no resolvable date is dropped and reported, because a
    # fabricated date poisons downstream feature links and procedures.
    scan_days = _tabular_scan_dates(sources)
    index['_scan_date'] = index['visit_start_date']
    unlinked = index['_scan_date'].isna()
    if unlinked.any() and scan_days:
        def _from_tabular(r):
            modality = 'PT' if r['_modality_code'] == 'PT' else 'MR'
            days = scan_days.get((r['BID'], r['VISCODE'], modality))
            if days is None:
                return pd.NaT
            return r['synthetic_consent_date'] + pd.Timedelta(days=days)
        index.loc[unlinked, '_scan_date'] = index[unlinked].apply(_from_tabular, axis=1)
    n_tabular = int((index['_scan_date'].notna() & unlinked).sum())

    undated = index['_scan_date'].isna()
    if undated.any():
        by_seq = index.loc[undated, '_sequence'].value_counts()
        detail = ", ".join(f"{k} x{v}" for k, v in by_seq.head(5).items())
        print(f"  dropped {int(undated.sum())} series with no visit link and "
              f"no tabular scan date ({detail})")
        index = index[~undated].copy()
    index['_date_str'] = pd.to_datetime(index['_scan_date']).dt.strftime('%Y-%m-%d')

    n_visit = int(index['visit_occurrence_id'].notna().sum())
    print(f"  Linked: {len(index)} series to persons; {n_visit} to visits, "
          f"{n_tabular} dated from tabular scan dates")
    return index


def relink_tau_pipeline_measurements(
    measurement_df: pd.DataFrame,
    json_index: pd.DataFrame,
) -> pd.DataFrame:
    """Re-date PetSurfer/Stanford tau measurements to the baseline FTP scan.

    The imaging_Tau_PET_{PetSurfer,Stanford}.csv exports stamp every row
    VISCODE=2 ("Visit 2 (Screening PET)" - the florbetapir screening visit),
    which is not the tau acquisition visit; dating rows by that visit lands
    a median 28 days before the scan and orphans them from the FTP sidecar
    series. The files' methods PDF documents one scan per participant, and
    both pipelines processed the same realigned+summed PET volume, so each
    row belongs to the person's earliest FTP session. Persons with no FTP
    sidecar keep their visit-dated fallback. See
    docs/Concept_Mapping_Decisions.md ("Tau pipeline relink").
    """
    if ('_mi_cdm_pipeline' not in measurement_df.columns
            or json_index is None or len(json_index) == 0):
        return measurement_df
    ftp = json_index[json_index['_sequence'] == 'FTP']
    if len(ftp) == 0:
        return measurement_df

    baseline = (ftp.dropna(subset=['_scan_date'])
                .sort_values('_scan_date')
                .drop_duplicates('person_id')
                .set_index('person_id')[['_scan_date', 'VISCODE',
                                         'visit_occurrence_id']])

    mask = measurement_df['_mi_cdm_pipeline'].isin(
        ['TAU_PETSURFER', 'TAU_STANFORD'])
    # Guardrail: the one-scan-per-participant interpretation only holds
    # while the exports stay cross-sectional. Any person with multiple
    # dated row groups per pipeline is left visit-dated and reported.
    per_person = measurement_df[mask].groupby(
        ['person_id', '_mi_cdm_pipeline'])['measurement_date'].nunique()
    multi = per_person[per_person > 1]
    if len(multi) > 0:
        print(f"  WARNING: {len(multi)} tau person-pipeline groups have "
              f"multiple dates; relink assumes one scan/person - skipped them")
        mask &= ~measurement_df['person_id'].isin(
            multi.index.get_level_values('person_id'))

    pids = measurement_df.loc[mask, 'person_id']
    new_date = pids.map(baseline['_scan_date'])
    has = new_date.notna()
    rows = new_date.index[has]
    measurement_df.loc[rows, 'measurement_date'] = new_date[has]
    measurement_df.loc[rows, 'visit_occurrence_id'] = pids.map(
        baseline['visit_occurrence_id'])[has]
    measurement_df.loc[rows, '_mi_cdm_viscode'] = pids.map(
        baseline['VISCODE'])[has]
    print(f"  Relinked {int(has.sum()):,} PetSurfer/Stanford tau measurements "
          f"({pids[has].nunique()} persons) to their baseline FTP session; "
          f"{pids[~has].nunique()} persons have no FTP sidecar (kept fallback)")
    return measurement_df


def extend_procedures_from_json(
    index: pd.DataFrame,
    procedure_df: pd.DataFrame,
) -> tuple:
    """
    Ensure every JSON imaging session has a PROCEDURE_OCCURRENCE row.

    Sessions are (person, procedure concept, visit). An existing
    results-file procedure is reused when it matches on visit or exact
    date; otherwise a new procedure row is created (image_occurrence.
    procedure_occurrence_id is NOT NULL per the MI-CDM guide DDL).

    Returns (extended procedure_df, index with _procedure_occurrence_id).
    """
    print("\n--- MI-CDM: Extending PROCEDURE_OCCURRENCE from JSON index ---")
    if len(index) == 0:
        return procedure_df, index

    proc_concepts = concepts.load_procedure_concepts()
    index = index.copy()
    index['_proc_type'] = index['_sequence'].map(SEQUENCE_TO_PROC)
    index['_proc_concept_id'] = index['_proc_type'].map(
        lambda t: proc_concepts[t]['concept_id'])

    # Existing procedures indexed by visit and by exact date
    by_visit = {}
    by_date = {}
    if len(procedure_df) > 0:
        pdf = procedure_df.copy()
        pdf['_date_str'] = pd.to_datetime(pdf['procedure_date']).dt.strftime('%Y-%m-%d')
        for _, r in pdf.iterrows():
            key_d = (r['person_id'], r['procedure_concept_id'], r['_date_str'])
            by_date.setdefault(key_d, r['procedure_occurrence_id'])
            if pd.notna(r.get('visit_occurrence_id')):
                key_v = (r['person_id'], r['procedure_concept_id'], r['visit_occurrence_id'])
                by_visit.setdefault(key_v, r['procedure_occurrence_id'])

    next_id = (int(procedure_df['procedure_occurrence_id'].max()) + 1
               if len(procedure_df) > 0 else 1)
    new_procs = []
    session_ids = {}  # (person_id, concept, viscode) -> procedure_occurrence_id
    proc_ids = []
    n_reused = 0
    for _, r in index.iterrows():
        skey = (r['person_id'], r['_proc_concept_id'], r['VISCODE'])
        if skey in session_ids:
            proc_ids.append(session_ids[skey])
            continue
        pid = None
        if pd.notna(r['visit_occurrence_id']):
            pid = by_visit.get((r['person_id'], r['_proc_concept_id'],
                                r['visit_occurrence_id']))
        if pid is None:
            pid = by_date.get((r['person_id'], r['_proc_concept_id'], r['_date_str']))
        if pid is not None:
            n_reused += 1
        else:
            pid = next_id
            next_id += 1
            new_procs.append({
                'person_id': r['person_id'],
                'procedure_concept_id': r['_proc_concept_id'],
                'procedure_date': r['_scan_date'],
                'procedure_type_concept_id': 32817,  # EHR: from DICOM headers
                'visit_occurrence_id': r['visit_occurrence_id'],
                'procedure_source_value': r['_proc_type'],
                'procedure_occurrence_id': pid,
                'procedure_datetime': None,
                'procedure_end_date': None,
                'procedure_end_datetime': None,
                'modifier_concept_id': 0,
                'quantity': None,
                'provider_id': None,
                'visit_detail_id': None,
                'procedure_source_concept_id': 0,
                'modifier_source_value': None,
            })
        session_ids[skey] = pid
        proc_ids.append(pid)

    index['_procedure_occurrence_id'] = proc_ids
    if new_procs:
        procedure_df = pd.concat(
            [procedure_df, pd.DataFrame(new_procs)], ignore_index=True)
    print(f"  Sessions: {len(session_ids)} "
          f"({n_reused} matched existing procedures, {len(new_procs)} created)")
    return procedure_df, index


def _lookup_value_concept(key: str, token: str):
    return DICOM_VALUE_MAP.get((key, token))


def create_dicom_metadata_measurements(
    index_with_io: pd.DataFrame,
    start_measurement_id: int,
) -> pd.DataFrame:
    """
    Build MEASUREMENT rows for whitelisted DICOM attributes.

    Per the MI-CDM guide section 5: one row per attribute per series
    (backslash-multi coded strings become one row per value), with
      measurement_concept_id / measurement_source_concept_id
                                = DICOM attribute concept
      value_as_number           = numeric value in DICOM-standard units
      value_as_concept_id       = DICOM value concept for coded strings
      measurement_source_value  = raw JSON value (always preserved)
      measurement_event_id      = image_occurrence_id
      meas_event_field_concept_id = 2100000532
    """
    print("\n--- MI-CDM: DICOM metadata -> MEASUREMENT ---")
    if len(index_with_io) == 0:
        return pd.DataFrame()

    records = []
    id_cols = index_with_io[['person_id', '_scan_date', 'visit_occurrence_id',
                             'image_occurrence_id', '_sequence']]
    for key, spec in DICOM_ATTRIBUTES.items():
        if key not in index_with_io.columns:
            continue
        present = index_with_io[key].notna()
        if not present.any():
            continue
        sub = id_cols[present].copy()
        sub['_raw'] = index_with_io.loc[present, key]
        dtype = spec['datatype']
        scale = spec['scale_factor']
        multivalue = spec['multivalue']

        for _, r in sub.iterrows():
            raw = r['_raw']
            # Free text is machine-generated (protocol/vendor strings) after the
            # whitelist dropped operator-typed attributes; newlines are stripped
            # so no value can span CSV lines.
            raw_str = ' '.join(str(raw).split())[:50]
            base = {
                'person_id': r['person_id'],
                'measurement_concept_id': spec['concept_id'],
                'measurement_source_concept_id': spec['concept_id'],
                'measurement_date': r['_scan_date'],
                'visit_occurrence_id': r['visit_occurrence_id'],
                'measurement_type_concept_id': 32817,  # EHR (header metadata)
                'measurement_source_value': raw_str,
                'unit_source_value': spec['unit'] or None,
                'unit_concept_id': spec['unit_concept_id'],
                'measurement_event_id': r['image_occurrence_id'],
                'meas_event_field_concept_id': IMAGE_OCCURRENCE_FIELD_CONCEPT_ID,
                'value_as_number': None,
                'value_as_concept_id': None,
                'value_source_value': raw_str,
            }

            if dtype == 'numeric':
                if isinstance(raw, list):
                    # multivalue='uniform' (FrameDuration): single row when
                    # all frames are equal, else source value only
                    vals = [v for v in raw if isinstance(v, (int, float))]
                    if multivalue == 'uniform' and vals and len(set(vals)) == 1:
                        base['value_as_number'] = vals[0] * scale
                    base['measurement_source_value'] = ' '.join(json.dumps(raw).split())[:50]
                    base['value_source_value'] = ' '.join(json.dumps(raw).split())[:50]
                    records.append(base)
                elif isinstance(raw, (int, float)):
                    base['value_as_number'] = raw * scale
                    records.append(base)
            elif dtype == 'bool':
                base['value_as_number'] = 1 if raw else 0
                records.append(base)
            elif dtype == 'coded':
                tokens = ([t.strip() for t in str(raw).split('\\') if t.strip()]
                          if multivalue == 'split' else [str(raw).strip()])
                for tok in tokens:
                    rec = dict(base)
                    rec['value_as_concept_id'] = _lookup_value_concept(key, tok)
                    rec['value_source_value'] = tok[:50]
                    records.append(rec)
            else:  # text
                if raw_str == '' or raw_str == 'None':
                    continue
                if key == 'Radiopharmaceutical':
                    base['value_as_concept_id'] = RADIOPHARM_CONCEPTS.get(
                        r['_sequence'])
                records.append(base)

    if not records:
        print("  No metadata measurements created")
        return pd.DataFrame()

    meas = pd.DataFrame(records)
    meas['measurement_id'] = range(start_measurement_id,
                                   start_measurement_id + len(meas))
    # OMOP boilerplate to align with the main measurement DataFrame
    for col, default in [
        ('measurement_datetime', None), ('measurement_time', None),
        ('operator_concept_id', None), ('range_low', None), ('range_high', None),
        ('provider_id', None), ('visit_detail_id', None),
    ]:
        meas[col] = default

    n_coded = meas['value_as_concept_id'].notna().sum()
    print(f"  Created {len(meas):,} metadata measurement rows "
          f"({meas['value_as_number'].notna().sum():,} numeric, "
          f"{n_coded:,} with value concepts) across "
          f"{meas['measurement_event_id'].nunique():,} series")
    return meas
