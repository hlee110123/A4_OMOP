"""
A4/LEARN OMOP ETL Package

Transforms A4/LEARN Alzheimer's clinical trial data to OMOP CDM v5.4
with MI-CDM (Medical Imaging Common Data Model) extension.

Core Modules:
    config      - Paths and file manifest
    concepts    - Concept mapping loaders (from concept_maps/ CSVs)
    helpers     - Shared utilities (date anchoring, person/visit linkage)
    person      - PERSON table
    visit       - VISIT_OCCURRENCE and OBSERVATION_PERIOD tables
    drug_exposure       - DRUG_EXPOSURE table
    measurement_clinical    - Vitals, labs, ECG
    measurement_cognitive   - PACC, MMSE, CDR + extended
    measurement_biomarkers  - AD biomarkers (amyloid-beta, tau, GFAP, NFL)
    measurement_imaging     - MRI, amyloid PET, tau PET + extended
    measurement_cogstate    - CogState tests + battery + questionnaires (individual items)
    measurement_questionnaire_scores - GDS, STAI, ADL-PQ, IES, BR1NIGHT, INFHRS (MEASUREMENT domain)
    observation     - Lifestyle, family history, CSSRS, milestones, study partner, secondary
    observation_adqs        - Treatment assignment (OBSERVATION) + APOE (MEASUREMENT)
    observation_questionnaires - AD Concern items (OBSERVATION domain only)
    condition       - CONDITION_OCCURRENCE (physical/neuro exam)
    postprocessing  - Unit mapping, observation period expansion
    export          - CSV export + validation
    pipeline        - Main orchestration

MI-CDM Extension Modules (Park et al. 2025):
    procedure_occurrence    - PROCEDURE_OCCURRENCE for imaging procedures
    image_occurrence        - IMAGE_OCCURRENCE (one row per DICOM series)
    image_feature           - IMAGE_FEATURE (polymorphic bridge: measurement ↔ imaging context)
"""

__version__ = "3.0.0"
