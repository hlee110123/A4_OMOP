"""
Concept mapping loaders.

Reads concept_maps/*.csv and returns Python dicts matching
the original dictionary structures used throughout the ETL.
"""

import csv
from .config import CONCEPT_DIR


def _load_csv(filename: str) -> list[dict]:
    """Load a concept CSV and return list of row dicts."""
    path = CONCEPT_DIR / filename
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


# ─── Demographics ─────────────────────────────────────────────────────

def load_gender_concepts() -> dict:
    """source_code (int) → concept_id (int)"""
    rows = _load_csv('demographics.csv')
    return {int(r['source_code']): int(r['concept_id'])
            for r in rows if r['category'] == 'gender'}


def load_race_concepts() -> dict:
    rows = _load_csv('demographics.csv')
    return {int(r['source_code']): int(r['concept_id'])
            for r in rows if r['category'] == 'race'}


def load_ethnicity_concepts() -> dict:
    rows = _load_csv('demographics.csv')
    return {int(r['source_code']): int(r['concept_id'])
            for r in rows if r['category'] == 'ethnicity'}


# ─── Visits / Drugs ───────────────────────────────────────────────────

def load_visit_concepts() -> dict:
    """source_code (str) → concept_id (int)"""
    rows = _load_csv('visits.csv')
    return {r['source_code']: int(r['concept_id']) for r in rows}


def load_drug_concepts() -> dict:
    """dose_mg (int) → concept_id (int)"""
    rows = _load_csv('drugs.csv')
    return {int(r['source_code']): int(r['concept_id']) for r in rows}


# ─── Units ────────────────────────────────────────────────────────────

def load_unit_concept_map() -> dict:
    """unit_source_value (str) → unit_concept_id (int)"""
    rows = _load_csv('units.csv')
    return {r['unit_source_value']: int(r['unit_concept_id']) for r in rows}


# ─── Dict-of-dicts loaders (concept_id + name + unit) ────────────────

def _load_dict_of_dicts(filename: str, group_filter: str = None, group_filters: list = None) -> dict:
    """Load CSV into {source_code: {concept_id, name, unit, ...}} format.

    Args:
        filename: CSV file in concept_maps/
        group_filter: Single group to include (exact match)
        group_filters: List of groups to include (any match)
    """
    rows = _load_csv(filename)
    result = {}
    for r in rows:
        group = r.get('group', '')
        if group_filter and group != group_filter:
            continue
        if group_filters and group not in group_filters:
            continue
        entry = {'concept_id': int(r['concept_id']), 'name': r['concept_name']}
        if 'unit' in r and r['unit']:
            entry['unit'] = r['unit']
        if 'unit_concept_id' in r and r['unit_concept_id']:
            entry['unit_concept_id'] = int(r['unit_concept_id'])
        result[r['source_code']] = entry
    return result


def load_vitals_concepts() -> dict:
    return _load_dict_of_dicts('vitals.csv')


def load_ecg_concepts() -> dict:
    return _load_dict_of_dicts('ecg.csv')


def load_cognitive_concepts() -> dict:
    return _load_dict_of_dicts('cognitive.csv', group_filter='core')


def load_cognitive_extended() -> dict:
    return _load_dict_of_dicts('cognitive.csv', group_filter='extended')


def load_cognitive_mmse_items() -> dict:
    """Load individual MMSE item concepts."""
    return _load_dict_of_dicts('cognitive.csv', group_filter='mmse_item')


def load_cognitive_mmse_letters() -> dict:
    """Load MMSE WORLD backwards letter position concepts."""
    return _load_dict_of_dicts('cognitive.csv', group_filter='mmse_letter')


def load_cognitive_cdr_domains() -> dict:
    """Load CDR domain score concepts."""
    return _load_dict_of_dicts('cognitive.csv', group_filter='cdr_domain')


def load_cogstate_concepts() -> dict:
    """Load CogState test + composite concepts (excludes battery and questionnaire)."""
    rows = _load_csv('cogstate.csv')
    result = {}
    for r in rows:
        if r.get('group', '') in ('test', 'composite'):
            entry = {'concept_id': int(r['concept_id']), 'name': r['concept_name']}
            if r.get('unit'):
                entry['unit'] = r['unit']
            result[r['source_code']] = entry
    return result


def load_cogstate_battery_concepts() -> dict:
    """Load CogState battery concepts (BPET, FNFT)."""
    return _load_dict_of_dicts('cogstate.csv', group_filter='battery')


def load_cogstate_battery_metric_concepts() -> dict:
    """Load CogState battery expanded metric concepts (lmn, cor, err, percor)."""
    return _load_dict_of_dicts('cogstate.csv', group_filter='battery_metric')


def load_cogstate_questionnaire_concepts() -> dict:
    return _load_dict_of_dicts('cogstate.csv', group_filter='questionnaire')


def load_cogstate_macq_item_concepts() -> dict:
    """Load individual MACQ item concepts."""
    return _load_dict_of_dicts('cogstate.csv', group_filter='macq_item')


def load_cogstate_cpath_item_concepts() -> dict:
    """Load individual C-PATH item concepts."""
    return _load_dict_of_dicts('cogstate.csv', group_filter='cpath_item')


def load_cogstate_cpath_domain_concepts() -> dict:
    """Load C-PATH domain score concepts."""
    return _load_dict_of_dicts('cogstate.csv', group_filter='cpath_domain')


def load_biomarker_concepts() -> dict:
    return _load_dict_of_dicts('biomarkers.csv')


def load_imaging_concepts() -> dict:
    return _load_dict_of_dicts('imaging.csv', group_filter='core')


def load_imaging_extended() -> dict:
    return _load_dict_of_dicts('imaging.csv', group_filter='extended')


def load_observation_concepts() -> dict:
    """Load lifestyle + family history observation concepts."""
    rows = _load_csv('observations.csv')
    result = {}
    for r in rows:
        if r.get('group', '') in ('lifestyle', 'family_history'):
            result[r['source_code']] = {
                'concept_id': int(r['concept_id']),
                'name': r['concept_name'],
                # Units are per-field and live in the map, not in Python: the CRF asks
                # SLEEP in hours but SLEEPDAY and WALKING in minutes.
                'unit': r.get('unit') or None,
                'unit_concept_id': int(r['unit_concept_id']) if r.get('unit_concept_id') else 0,
            }
    return result


def load_study_partner_concepts() -> dict:
    rows = _load_csv('observations.csv')
    result = {}
    for r in rows:
        if r.get('group', '') == 'study_partner':
            result[r['source_code']] = {
                'concept_id': int(r['concept_id']),
                'name': r['concept_name'],
            }
    return result


def load_measurement_from_observations() -> dict:
    """Load concepts that moved from observations to measurement domain."""
    rows = _load_csv('observations.csv')
    result = {}
    for r in rows:
        if r.get('group', '') == 'measurement':
            result[r['source_code']] = {
                'concept_id': int(r['concept_id']),
                'name': r['concept_name'],
            }
    return result


def load_condition_concepts() -> dict:
    return _load_dict_of_dicts('conditions.csv')


def load_milestone_concepts() -> dict:
    return _load_dict_of_dicts('milestones.csv')


def load_questionnaire_concepts() -> dict:
    return _load_dict_of_dicts('questionnaires.csv', group_filter='primary')


def load_questionnaire_measurement_concepts() -> dict:
    """Load questionnaire scores that belong in MEASUREMENT domain."""
    return _load_dict_of_dicts('questionnaires.csv', group_filter='measurement')


def load_secondary_questionnaire_concepts() -> dict:
    return _load_dict_of_dicts('questionnaires.csv', group_filter='secondary')


def load_adlpq_item_concepts() -> dict:
    """Load ADLPQ individual question item concepts."""
    return _load_dict_of_dicts('questionnaires.csv', group_filter='adlpq_item')


# ─── Simple key→key maps ─────────────────────────────────────────────

def load_cssrs_concepts() -> dict:
    return _load_dict_of_dicts('cssrs.csv')


def load_cssrslv_column_map() -> dict:
    """lifetime_column → standard_key mapping."""
    rows = _load_csv('cssrslv_columns.csv')
    return {r['lifetime_column']: r['standard_key'] for r in rows}


# ─── Labs (simple source_code → concept_id) ──────────────────────────

def load_lab_concepts() -> dict:
    """source_code (str) → concept_id (int)"""
    rows = _load_csv('labs.csv')
    return {r['source_code']: int(r['concept_id']) for r in rows}


# ─── MI-CDM Extension Concepts (Park et al. 2025) ───────────────────

def load_procedure_concepts() -> dict:
    """source_code (str) → {concept_id, name}"""
    rows = _load_csv('procedures.csv')
    return {r['source_code']: {
        'concept_id': int(r['concept_id']),
        'name': r['concept_name'],
    } for r in rows}


def load_modality_concepts() -> dict:
    """source_code (str) → concept_id (int).  DICOM modality codes."""
    rows = _load_csv('modalities.csv')
    return {r['source_code']: int(r['concept_id']) for r in rows}


def load_image_feature_type_concepts() -> dict:
    """source_code (str) → concept_id (int).  Provenance type concepts."""
    rows = _load_csv('image_feature_types.csv')
    return {r['source_code']: int(r['concept_id']) for r in rows}


def load_image_finding_concepts() -> dict:
    """source_code (str) → concept_id (int).  Finding grouping concepts."""
    rows = _load_csv('image_findings.csv')
    return {r['source_code']: int(r['concept_id']) for r in rows}
