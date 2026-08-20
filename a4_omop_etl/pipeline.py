"""
Main ETL orchestration.

Reads like a table of contents: load sources → build core tables →
build measurements → build observations → build conditions →
postprocess → export → validate.
"""

import datetime

import pandas as pd

from .config import OUTPUT_DIR, load_all_sources
from .helpers import create_date_anchor, concat_and_assign_ids, drop_undated
from .person import create_person_table
from .visit import create_visit_occurrence, create_observation_period
from .death import create_death
from .drug_exposure import create_drug_exposure
from .measurement_clinical import create_measurement_clinical
from .measurement_cognitive import (
    create_measurement_cognitive,
    create_measurement_cognitive_extended,
)
from .measurement_biomarkers import create_measurement_biomarkers
from .measurement_imaging import (
    create_measurement_imaging,
    create_measurement_imaging_extended,
)
from .measurement_cogstate import (
    create_measurement_cogstate,
    create_measurement_cogstate_battery,
    create_measurement_cogstate_questionnaires,
)
from .observation import (
    create_observation,
    create_observation_milestones,
    create_observation_cssrs,
    create_observation_study_partner,
    create_observation_secondary_questionnaires,
)
from .observation_adqs import (
    create_measurement_apoe, create_observation_treatment_arm,
    create_observation_education, create_measurement_bmi,
    create_observation_retirement,
)
from .observation_questionnaires import create_observation_questionnaires
from .measurement_questionnaire_scores import create_measurement_questionnaire_scores
from .condition import (
    create_phyneuro_observations_and_measurements,
    create_siderosis_conditions,
)
from .postprocessing import (
    map_unit_concepts,
    expand_observation_periods,
)
from .procedure_occurrence import create_procedure_occurrence
from .image_occurrence import create_image_occurrence, PRIVATE_COLUMNS
from .image_feature import (
    create_image_feature,
    backfill_measurement_event_links,
    strip_mi_cdm_annotations,
)
from .image_metadata import (
    build_image_json_index,
    extend_procedures_from_json,
    create_dicom_metadata_measurements,
    IMAGE_OCCURRENCE_FIELD_CONCEPT_ID,
)
from .export import export_tables, export_mi_cdm_tables, validate_etl, validate_mi_cdm


def main():
    """Execute the full ETL pipeline."""
    print("=" * 60)
    print("A4/LEARN OMOP ETL Pipeline")
    print("=" * 60)

    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"\nOutput directory: {OUTPUT_DIR}")

    # ── Load all source files ────────────────────────────────────────
    src = load_all_sources()

    # ── Phase 1: Date Anchoring ──────────────────────────────────────
    print("\n--- Phase 1: Date Anchoring ---")
    date_anchor = create_date_anchor(src['subjinfo'])

    # ── Phase 2: PERSON ──────────────────────────────────────────────
    print("\n--- Phase 2: PERSON Table ---")
    person = create_person_table(src['subjinfo'], date_anchor, src['ptdemog'])

    # ── Phase 3: VISIT_OCCURRENCE ────────────────────────────────────
    print("\n--- Phase 3: VISIT_OCCURRENCE Table ---")
    visit_occurrence = create_visit_occurrence(src['sv'], person, date_anchor)

    # ── Phase 4: OBSERVATION_PERIOD ──────────────────────────────────
    print("\n--- Phase 4: OBSERVATION_PERIOD Table ---")
    observation_period = create_observation_period(src['subjinfo'], person, date_anchor, src['sv'])

    # ── Phase 5: DRUG_EXPOSURE ───────────────────────────────────────
    print("\n--- Phase 5: DRUG_EXPOSURE Table ---")
    drug_exposure = create_drug_exposure(src['dose'], person, visit_occurrence, date_anchor, src['subjinfo'])

    # ── Measurements ─────────────────────────────────────────────────
    print("\n--- Phase 6: MEASUREMENT Table (Clinical) ---")
    measurement_clinical = create_measurement_clinical(
        src['vitals'], src['clrm_lab'], src['clrm_ecg'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 7: MEASUREMENT Table (Cognitive) ---")
    measurement_cognitive = create_measurement_cognitive(
        src['pacc'], src['mmse'], src['cdr'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 8: MEASUREMENT Table (Biomarkers) ---")
    measurement_biomarkers = create_measurement_biomarkers(
        src['biomarker_ab'], src['biomarker_ptau'], src['biomarker_roche'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 9: MEASUREMENT Table (Imaging) ---")
    measurement_imaging = create_measurement_imaging(
        src['imaging_mri'], src['imaging_amyloid'], src['imaging_tau'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 10: MEASUREMENT Table (CogState) ---")
    measurement_cogstate = create_measurement_cogstate(
        src['cogstate'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 10b: MEASUREMENT Table (CogState Battery BPET/FNFT) ---")
    measurement_cogstate_battery = create_measurement_cogstate_battery(
        src['cogstate_battery'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 16: MEASUREMENT Table (Extended Cognitive) ---")
    measurement_cog_extended = create_measurement_cognitive_extended(
        src['cfi'], src['cfisp'], src['cogdigit'], src['cogfcsr'], src['coglogic'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 17: MEASUREMENT Table (Extended Imaging) ---")
    measurement_imaging_extended = create_measurement_imaging_extended(
        src['imaging_mri_reads'], src['imaging_flair'],
        src['imaging_retinal'], src['imaging_pet_va'],
        person, visit_occurrence, date_anchor,
        tau_petsurfer_df=src['tau_petsurfer'],
        tau_stanford_df=src['tau_stanford'],
    )

    print("\n--- Phase 19: MEASUREMENT Table (CogState Questionnaires) ---")
    measurement_cogstate_quest = create_measurement_cogstate_questionnaires(
        src['cogstate_macq'], src['cogstate_cpath'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 20: MEASUREMENT Table (Questionnaire Scores) ---")
    measurement_quest_scores = create_measurement_questionnaire_scores(
        src['psychwell'], src['adlpq'], src['adlpqsp'],
        src['ies'], src['ruib1'], src['spinfo'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 21: MEASUREMENT Table (APOE Genotype) ---")
    measurement_apoe = create_measurement_apoe(
        src['adqs'], person, date_anchor
    )

    print("\n--- Phase 21b: OBSERVATION Table (Treatment Arm) ---")
    observation_tx = create_observation_treatment_arm(
        src['adqs'], person, date_anchor
    )

    print("\n--- Phase 21c: OBSERVATION Table (Education) / MEASUREMENT (Baseline BMI) ---")
    observation_education = create_observation_education(
        src['subjinfo'], person, date_anchor
    )
    measurement_bmi = create_measurement_bmi(
        src['subjinfo'], person, date_anchor
    )
    observation_retirement = create_observation_retirement(
        src['subjinfo'], person, date_anchor
    )

    print("\n--- Phase 22: Physical & Neurological Exam (Phyneuro) ---")
    phyneuro_cond, phyneuro_meas = create_phyneuro_observations_and_measurements(
        src['phyneuro'], person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 22b: Superficial Siderosis Conditions (MRI Reads) ---")
    siderosis_cond = create_siderosis_conditions(
        src['imaging_mri_reads'], person, visit_occurrence, date_anchor
    )
    condition_occurrence = concat_and_assign_ids(
        [phyneuro_cond, siderosis_cond], 'condition_occurrence_id'
    )

    # ── Combine all measurements ─────────────────────────────────────
    measurement = concat_and_assign_ids([
        measurement_clinical, measurement_cognitive, measurement_biomarkers,
        measurement_imaging, measurement_cogstate, measurement_cogstate_battery,
        measurement_cog_extended, measurement_imaging_extended, measurement_cogstate_quest,
        measurement_quest_scores, measurement_apoe, measurement_bmi, phyneuro_meas
    ], 'measurement_id')
    print(f"\nTotal MEASUREMENT records: {len(measurement)}")

    # measurement_date is NOT NULL in OMOP CDM v5.4
    measurement = drop_undated(measurement, 'measurement_date', 'measurement_id',
                               'MEASUREMENT', source_col='measurement_source_value')

    # ── Post-processing: unit mapping ────────────────────────────────
    measurement = map_unit_concepts(measurement)

    # ── MI-CDM Extension (Park et al. 2025 / DICOM2OMOP guide) ──────
    print("\n--- Phase 30: MI-CDM DICOM Sidecar Index (A4_JSONS) ---")
    json_index = build_image_json_index(person, visit_occurrence, date_anchor, sources=src)

    print("\n--- Phase 30b: MI-CDM PROCEDURE_OCCURRENCE (Imaging) ---")
    procedure_occurrence = create_procedure_occurrence(
        src, person, visit_occurrence, date_anchor
    )
    procedure_occurrence, json_index = extend_procedures_from_json(
        json_index, procedure_occurrence
    )

    print("\n--- Phase 31: MI-CDM IMAGE_OCCURRENCE ---")
    image_occurrence = create_image_occurrence(
        src, person, visit_occurrence, procedure_occurrence, date_anchor,
        json_index=json_index
    )

    print("\n--- Phase 32: MI-CDM IMAGE_FEATURE (Bridge) ---")
    image_feature = create_image_feature(measurement, image_occurrence)
    measurement = backfill_measurement_event_links(
        measurement, image_feature, IMAGE_OCCURRENCE_FIELD_CONCEPT_ID
    )

    # Strip MI-CDM annotation columns before export
    measurement = strip_mi_cdm_annotations(measurement)

    print("\n--- Phase 33: MI-CDM DICOM Metadata -> MEASUREMENT ---")
    n_metadata_meas = 0
    if len(json_index) > 0 and len(image_occurrence) > 0:
        io_ids = image_occurrence.loc[
            image_occurrence['_rel_path'].notna(),
            ['image_occurrence_id', '_rel_path', '_elem_idx']
        ]
        index_with_io = json_index.merge(
            io_ids, on=['_rel_path', '_elem_idx'], how='inner'
        )
        metadata_meas = create_dicom_metadata_measurements(
            index_with_io, start_measurement_id=int(measurement['measurement_id'].max()) + 1
        )
        n_metadata_meas = len(metadata_meas)
        if n_metadata_meas > 0:
            measurement = pd.concat([measurement, metadata_meas], ignore_index=True)
            print(f"Total MEASUREMENT records incl. DICOM metadata: {len(measurement):,}")

    # ── Observations ─────────────────────────────────────────────────
    print("\n--- Phase 11-12: OBSERVATION Table (Lifestyle & Family History) ---")
    observation_lifestyle = create_observation(
        src['habits'], src['famhxpar'], src['famhxsib'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- Phase 15: OBSERVATION Table (Milestones) ---")
    observation_milestones = create_observation_milestones(
        src['ds'], person, date_anchor
    )

    print("\n--- Phase 15b: DEATH Table ---")
    death = create_death(src['ds'], person, date_anchor)

    print("\n--- Phase 17b: OBSERVATION Table (C-SSRS) ---")
    observation_cssrs = create_observation_cssrs(
        src['cssrs'], src['cssrslv'], person, date_anchor, visit_occurrence
    )

    print("\n--- Phase 20: OBSERVATION Table (Study Partner) ---")
    observation_study_partner = create_observation_study_partner(
        src['spinfo'], person, date_anchor, visit_occurrence
    )

    print("\n--- Phase 21: OBSERVATION Table (Secondary Questionnaires) ---")
    observation_secondary = create_observation_secondary_questionnaires(
        src['ies'], src['ftpscale'], src['rss'], src['views'],
        src['ruib'], src['ruib1'], person, date_anchor, visit_occurrence
    )

    print("\n--- Phase 25: OBSERVATION Table (Questionnaires - AD Concerns, ADLPQ Items, GDS Items) ---")
    observation_questionnaires = create_observation_questionnaires(
        src['concerns'], src['adlpq'], src['psychwell'],
        person, visit_occurrence, date_anchor,
        adlpqsp_df=src['adlpqsp'],
    )

    # ── Combine all observations ─────────────────────────────────────
    # Phyneuro abnormal findings are routed to condition_occurrence
    # (Condition-domain SNOMED concepts), not observation.
    observation = concat_and_assign_ids([
        observation_lifestyle, observation_milestones,
        observation_cssrs, observation_study_partner, observation_secondary,
        observation_questionnaires, observation_tx, observation_education,
        observation_retirement,
    ], 'observation_id')
    print(f"\nTotal OBSERVATION records: {len(observation)}")

    # observation_date is NOT NULL in OMOP CDM v5.4
    observation = drop_undated(observation, 'observation_date', 'observation_id',
                               'OBSERVATION', source_col='observation_source_value')

    # ── Post-processing ──────────────────────────────────────────────
    observation_period = expand_observation_periods(observation_period, [
        (measurement, 'measurement_date'),
        (observation, 'observation_date'),
        (drug_exposure, 'drug_exposure_start_date'),
        (drug_exposure, 'drug_exposure_end_date'),
        (visit_occurrence, 'visit_start_date'),
        (visit_occurrence, 'visit_end_date'),
        (procedure_occurrence, 'procedure_date'),
        (condition_occurrence, 'condition_start_date'),
        (death, 'death_date'),
    ])

    # ── CDM_SOURCE metadata ──────────────────────────────────────────
    cdm_source = pd.DataFrame([{
        'cdm_source_name': 'A4_LEARN_OMOP_ETL',
        'cdm_source_abbreviation': 'A4LEARN',
        'cdm_holder': 'A4/LEARN OMOP ETL',
        'source_description': 'A4 (Anti-Amyloid Treatment in Asymptomatic Alzheimers) and LEARN clinical trial data',
        'source_documentation_reference': 'https://www.actcinfo.org/',
        'cdm_etl_reference': 'https://github.com/hlee110123/A4_OMOP',
        'source_release_date': '2026-01-11',
        'cdm_release_date': datetime.date.today().isoformat(),
        'cdm_version': 'v5.4',
        'cdm_version_concept_id': 756265,
        'vocabulary_version': 'v5.0 27-FEB-25',
    }])

    # ── Export ────────────────────────────────────────────────────────
    # condition_occurrence holds phyneuro abnormal exam findings plus
    # superficial siderosis from MRI reads (SNOMED Clinical Finding concepts
    # belong in this table per OMOP CDM v5.4).
    # procedure_occurrence is a standard OMOP CDM v5.4 table populated with
    # imaging procedures; per Park & Jeon et al. 2024 the MI-CDM extension
    # itself only adds image_occurrence and image_feature.
    export_tables({
        'cdm_source': cdm_source,
        'date_anchor': date_anchor,
        'person': person,
        'visit_occurrence': visit_occurrence,
        'observation_period': observation_period,
        'drug_exposure': drug_exposure,
        'death': death,
        'measurement': measurement,
        'observation': observation,
        'condition_occurrence': condition_occurrence,
        'procedure_occurrence': procedure_occurrence,
    })

    # Export MI-CDM extension tables (the two new tables from Park & Jeon et al. 2024)
    # Private working columns (_sequence etc.) are for in-pipeline linkage only
    image_occurrence_export = image_occurrence.drop(
        columns=PRIVATE_COLUMNS + ['_date_str'], errors='ignore')
    export_mi_cdm_tables({
        'image_occurrence': image_occurrence_export,
        'image_feature': image_feature,
    })

    # ── Validation ───────────────────────────────────────────────────
    validation_results = validate_etl(
        person, visit_occurrence, observation_period,
        src['subjinfo'], src['sv'],
        drug_exposure, src['dose']
    )
    validation_results.update(validate_mi_cdm(
        image_occurrence_export, image_feature, measurement,
        procedure_occurrence, n_json_series=len(json_index),
        n_metadata_meas=n_metadata_meas,
    ))

    all_passed = all(validation_results.values())
    print(f"\n{'=' * 60}")
    print(f"ETL Complete - {'ALL VALIDATIONS PASSED' if all_passed else 'SOME VALIDATIONS FAILED'}")
    print(f"Output files in: {OUTPUT_DIR}")
    print(f"{'=' * 60}")

    return {
        'date_anchor': date_anchor,
        'person': person,
        'visit_occurrence': visit_occurrence,
        'observation_period': observation_period,
        'drug_exposure': drug_exposure,
        'death': death,
        'measurement': measurement,
        'observation': observation,
        'condition_occurrence': condition_occurrence,
        'procedure_occurrence': procedure_occurrence,
        'image_occurrence': image_occurrence,
        'image_feature': image_feature,
        'validation': validation_results,
    }
