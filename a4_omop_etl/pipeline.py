"""
Main ETL orchestration.

Reads like a table of contents: load sources → core tables →
measurements → conditions → MI-CDM imaging extension → observations →
postprocess → export → validate.

ORDERING: measurement IDs must be final (concat + drop_undated + unit
mapping) before the MI-CDM bridge stores them as image_feature event ids,
and the DICOM metadata measurements append after that with fresh ids.
The observation block is independent of MI-CDM; it simply runs late.
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
    relink_tau_pipeline_measurements,
    IMAGE_OCCURRENCE_FIELD_CONCEPT_ID,
)
from .export import (
    export_tables, export_mi_cdm_tables,
    validate_etl, validate_mi_cdm, validate_data_quality,
)


def main():
    """Execute the full ETL pipeline."""
    print("=" * 60)
    print("A4/LEARN OMOP ETL Pipeline")
    print("=" * 60)

    OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"\nOutput directory: {OUTPUT_DIR}")

    # ── Load all source files ────────────────────────────────────────
    src = load_all_sources()

    # ── Date Anchoring ──────────────────────────────────────
    print("\n--- Date Anchoring ---")
    date_anchor = create_date_anchor(src['subjinfo'])

    # ── PERSON ──────────────────────────────────────────────
    print("\n--- PERSON ---")
    person = create_person_table(src['subjinfo'], date_anchor, src['ptdemog'])

    # ── VISIT_OCCURRENCE ────────────────────────────────────
    print("\n--- VISIT_OCCURRENCE ---")
    visit_occurrence = create_visit_occurrence(src['sv'], person, date_anchor)

    # ── OBSERVATION_PERIOD ──────────────────────────────────
    print("\n--- OBSERVATION_PERIOD ---")
    observation_period = create_observation_period(src['subjinfo'], person, date_anchor, src['sv'])

    # ── DRUG_EXPOSURE ───────────────────────────────────────
    print("\n--- DRUG_EXPOSURE ---")
    drug_exposure = create_drug_exposure(src['dose'], person, visit_occurrence, date_anchor, src['subjinfo'])

    # ── Measurements ─────────────────────────────────────────────────
    print("\n--- MEASUREMENT: Clinical (vitals, labs, ECG) ---")
    measurement_clinical = create_measurement_clinical(
        src['vitals'], src['clrm_lab'], src['clrm_ecg'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- MEASUREMENT: Cognitive (PACC, MMSE, CDR) ---")
    measurement_cognitive, observation_mmse = create_measurement_cognitive(
        src['pacc'], src['mmse'], src['cdr'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- MEASUREMENT: Biomarkers ---")
    measurement_biomarkers = create_measurement_biomarkers(
        src['biomarker_ab'], src['biomarker_ptau'], src['biomarker_roche'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- MEASUREMENT: Imaging (MRI volumes, PET SUVR) ---")
    measurement_imaging = create_measurement_imaging(
        src['imaging_mri'], src['imaging_amyloid'], src['imaging_tau'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- MEASUREMENT: CogState computerized ---")
    measurement_cogstate = create_measurement_cogstate(
        src['cogstate'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- MEASUREMENT: CogState battery (BPET/FNFT) ---")
    measurement_cogstate_battery = create_measurement_cogstate_battery(
        src['cogstate_battery'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- MEASUREMENT: Extended cognitive (CFI, digit, FCSR, logic) ---")
    measurement_cog_extended = create_measurement_cognitive_extended(
        src['cfi'], src['cfisp'], src['cogdigit'], src['cogfcsr'], src['coglogic'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- MEASUREMENT: Extended imaging (reads, FLAIR, retinal, tau pipelines) ---")
    measurement_imaging_extended = create_measurement_imaging_extended(
        src['imaging_mri_reads'], src['imaging_flair'],
        src['imaging_retinal'], src['imaging_pet_va'],
        person, visit_occurrence, date_anchor,
        tau_petsurfer_df=src['tau_petsurfer'],
        tau_stanford_df=src['tau_stanford'],
    )

    print("\n--- MEASUREMENT: CogState questionnaires (MACQ, C-PATH) ---")
    measurement_cogstate_quest = create_measurement_cogstate_questionnaires(
        src['cogstate_macq'], src['cogstate_cpath'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- MEASUREMENT: Questionnaire scores (STAI, ADL-PQ, RUIB) ---")
    measurement_quest_scores = create_measurement_questionnaire_scores(
        src['psychwell'], src['adlpq'], src['adlpqsp'],
        src['ies'], src['ruib1'], src['spinfo'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- MEASUREMENT: APOE genotype ---")
    measurement_apoe = create_measurement_apoe(
        src['adqs'], person, date_anchor,
        clrm_lab_df=src['clrm_lab'], subjinfo_df=src['subjinfo'],
    )

    print("\n--- OBSERVATION: Treatment arm ---")
    observation_tx = create_observation_treatment_arm(
        src['adqs'], person, date_anchor
    )

    print("\n--- OBSERVATION: Education, retirement / MEASUREMENT: Baseline BMI ---")
    observation_education = create_observation_education(
        src['subjinfo'], person, date_anchor
    )
    measurement_bmi = create_measurement_bmi(
        src['subjinfo'], person, date_anchor
    )
    observation_retirement = create_observation_retirement(
        src['subjinfo'], person, date_anchor
    )

    print("\n--- CONDITION: Physical & neurological exam (phyneuro) ---")
    phyneuro_cond, phyneuro_meas = create_phyneuro_observations_and_measurements(
        src['phyneuro'], person, visit_occurrence, date_anchor
    )

    print("\n--- CONDITION: Superficial siderosis (MRI reads) ---")
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
    print("\n--- MI-CDM: DICOM sidecar index (A4_JSONS) ---")
    json_index = build_image_json_index(person, visit_occurrence, date_anchor, sources=src)

    print("\n--- MI-CDM: PROCEDURE_OCCURRENCE (imaging) ---")
    procedure_occurrence = create_procedure_occurrence(
        src, person, visit_occurrence, date_anchor
    )
    procedure_occurrence, json_index = extend_procedures_from_json(
        json_index, procedure_occurrence
    )

    # PetSurfer/Stanford tau rows are visit-2 stamped in their sources;
    # re-date them to the person's baseline FTP sidecar session so
    # image_feature links them to the real series (with metadata).
    measurement = relink_tau_pipeline_measurements(measurement, json_index)

    print("\n--- MI-CDM: IMAGE_OCCURRENCE ---")
    image_occurrence = create_image_occurrence(
        src, person, visit_occurrence, procedure_occurrence, date_anchor,
        json_index=json_index
    )

    print("\n--- MI-CDM: IMAGE_FEATURE (bridge) ---")
    image_feature = create_image_feature(measurement, image_occurrence)
    measurement = backfill_measurement_event_links(
        measurement, image_feature, IMAGE_OCCURRENCE_FIELD_CONCEPT_ID
    )

    # Strip MI-CDM annotation columns before export
    measurement = strip_mi_cdm_annotations(measurement)

    print("\n--- MI-CDM: DICOM metadata -> MEASUREMENT ---")
    # (_rel_path, _elem_idx) is the natural key of a sidecar series. It was
    # carried from the JSON index onto image_occurrence rows precisely so we
    # can join back here — after image_occurrence_ids were assigned post-
    # concat — and stamp each metadata measurement with its series id
    # (measurement_event_id + field concept 2100000532).
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
    print("\n--- OBSERVATION: Lifestyle & family history ---")
    observation_lifestyle = create_observation(
        src['habits'], src['famhxpar'], src['famhxsib'],
        person, visit_occurrence, date_anchor
    )

    print("\n--- OBSERVATION: Milestones ---")
    observation_milestones = create_observation_milestones(
        src['ds'], person, date_anchor
    )

    print("\n--- DEATH ---")
    death = create_death(src['ds'], person, date_anchor)

    print("\n--- OBSERVATION: C-SSRS ---")
    observation_cssrs = create_observation_cssrs(
        src['cssrs'], src['cssrslv'], person, date_anchor, visit_occurrence
    )

    print("\n--- OBSERVATION: Study partner ---")
    observation_study_partner = create_observation_study_partner(
        src['spinfo'], person, date_anchor, visit_occurrence
    )

    print("\n--- OBSERVATION: Secondary questionnaires (IES, FTP, RSS, VIEWS, RUIB) ---")
    observation_secondary = create_observation_secondary_questionnaires(
        src['ies'], src['ftpscale'], src['rss'], src['views'],
        src['ruib'], src['ruib1'], person, date_anchor, visit_occurrence
    )

    print("\n--- OBSERVATION: Questionnaires (AD Concerns, ADL-PQ items, GDS) ---")
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
        observation_retirement, observation_mmse,
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
    validation_results.update(validate_data_quality({
        'measurement': measurement,
        'observation': observation,
        'condition_occurrence': condition_occurrence,
        'procedure_occurrence': procedure_occurrence,
        'drug_exposure': drug_exposure,
        'death': death,
    }))

    all_passed = all(validation_results.values())
    print(f"\n{'=' * 60}")
    print(f"ETL Complete - {'ALL VALIDATIONS PASSED' if all_passed else 'SOME VALIDATIONS FAILED'}")
    if not all_passed:
        failed = [k for k, v in validation_results.items() if not v]
        print(f"FAILED CHECKS: {', '.join(failed)}")
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
