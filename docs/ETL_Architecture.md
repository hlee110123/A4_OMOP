# A4/LEARN OMOP ETL Architecture

Version 3.0.0 | Target: OMOP CDM v5.4

---

## Table of Contents

1. [Study Background](#1-study-background)
2. [Pipeline Overview](#2-pipeline-overview)
3. [Package Structure](#3-package-structure)
4. [Source File Inventory](#4-source-file-inventory)
5. [Output File Inventory](#5-output-file-inventory)
6. [Pipeline Phases](#6-pipeline-phases)
7. [Date Anchoring Strategy](#7-date-anchoring-strategy)
8. [Concept Mapping Architecture](#8-concept-mapping-architecture)
9. [Module Dependency Diagram](#9-module-dependency-diagram)
10. [Post-Processing](#10-post-processing)
11. [Validation](#11-validation)
12. [Running the Pipeline](#12-running-the-pipeline)
13. [Key Design Decisions](#13-key-design-decisions)

---

## 1. Study Background

### A4 Study (Anti-Amyloid Treatment in Asymptomatic Alzheimer's Disease)

A randomized, double-blind, placebo-controlled Phase III trial evaluating
intravenous Solanezumab (an anti-amyloid monoclonal antibody) in cognitively
normal elderly adults who have elevated brain amyloid on PET imaging. The trial
enrolled participants aged 65-85 who met amyloid positivity criteria at
screening.

### LEARN Study (Longitudinal Evaluation of Amyloid Risk and Neurodegeneration)

A parallel longitudinal observational cohort composed of amyloid-negative screen
failures from the A4 eligibility process. LEARN participants underwent the same
cognitive and clinical assessments as the A4 treatment arms, providing a natural
history comparison group.

### Population

- **6,945** cognitively normal adults aged 65-85
- Screened for preclinical Alzheimer's disease biomarkers
- Followed with comprehensive cognitive, biomarker, and imaging assessments

### Purpose of This ETL

This pipeline transforms the combined A4/LEARN clinical trial dataset from its
native de-identified format into the OMOP Common Data Model version 5.4. The
OMOP CDM is a standardized data model maintained by the OHDSI community that
enables observational health data to be analyzed with shared analytic tools
and compared across studies.

---

## 2. Pipeline Overview

```
                         A4/LEARN OMOP ETL Pipeline
 ============================================================================

  SOURCE FILES (48 CSVs)          PIPELINE (17 modules)          OUTPUT (8+3 CSVs)
 ========================      ========================      ==================

  Derived Data/                                               OMOP_Output/
  +-- SUBJINFO.csv ------+                                    +----------------+
  +-- SV.csv ------------|---> config.load_all_sources() ---> | date_anchor    |
  +-- PACC.csv ----------|          |                         |   6,945 rows   |
  +-- COGSTATE_COMP.csv -|          |                         +----------------+
  +-- DS.csv ------------|          v
  +-- cogfcsr16.csv -----|     helpers.create_date_anchor()
                         |          |
  Raw Data/              |          v
  +-- ptdemog.csv -------|---> person.create_person_table() ---------> person.csv
  +-- dose.csv ----------|          |                                  6,945 rows
  +-- vitals.csv --------|          v
  +-- mmse.csv ----------|     visit.create_visit_occurrence() ------> visit_
  +-- cdr.csv -----------|          |                                  occurrence.csv
  +-- habits.csv --------|          v                                  99,795 rows
  +-- famhxpar.csv ------|     visit.create_observation_period() ----> observation_
  +-- famhxsib.csv ------|          |                                  period.csv
  +-- phyneuro.csv ------|          v                                  6,945 rows
  +-- cfi.csv -----------|     drug_exposure.create_drug_exposure() -> drug_
  +-- cfisp.csv ---------|          |                                  exposure.csv
  +-- cogdigit.csv ------|          v                                  74,777 rows
  +-- coglogic.csv ------|     measurement_clinical ----+
  +-- psychwell.csv -----|     measurement_cognitive ----|
  +-- adlpq.csv ---------|     measurement_biomarkers ---|
  +-- adlpqsp.csv -------|     measurement_imaging ------|---> pd.concat() ----+
  +-- concerns.csv ------|     measurement_cogstate -----|     + ID reassign   |
  +-- cssrs.csv ---------|     measurement_questionnaires+          |          |
  +-- cssrslv.csv -------|                                         v          |
  +-- spinfo.csv --------|                                  postprocessing    |
  +-- ies.csv -----------|                                  .map_unit_        |
  +-- ftpscale.csv ------|                                   concepts()       |
  +-- rss.csv -----------|          |                              |          |
  +-- views.csv ---------|          v                              v          |
  +-- ruib.csv ----------|     observation ---+                              |
  +-- ruib1.csv ---------|       (lifestyle)  |                              |
                         |       (milestones) |---> pd.concat() --+          |
  External Data/         |       (C-SSRS)     |     + ID reassign |          |
  +-- clrm_lab.csv ------|       (partner)    |          |        |          |
  +-- clrm_ecg.csv ------|       (secondary)  +          v        v          v
  +-- biomarker_AB.csv --|                                                   |
  +-- biomarker_pTau.csv-|     condition.create_condition_   measurement.csv |
  +-- biomarker_Roche.csv|       occurrence() ---------->    2,547,815 rows  |
  +-- imaging_mri.csv ---|                                                   |
  +-- imaging_amyloid.csv|     postprocessing                observation.csv |
  +-- imaging_tau.csv ---|       .expand_observation_         412,587 rows   |
  +-- cogstate_battery---|        periods()                                  |
  +-- cogstate_macq.csv -|                              condition_       |
  +-- cogstate_cpath.csv-|                                   occurrence.csv  |
  +-- imaging_MRI_reads -|                                   (empty post-R3) |
  +-- imaging_FLAIR.csv -|                                                   |
  +-- imaging_retinal.csv|     export.export_tables() ---> 8 CSV files       |
  +-- imaging_PET_VA.csv-|     export.validate_etl()       written to        |
  +-- Tau_PetSurfer.csv -|                                 OMOP_Output/      |
  +-- Tau_Stanford.csv --+
                                                                  MI-CDM Output:
                        MI-CDM Extension                          mi_cdm/
                        procedure_occurrence.py ---------> procedure_occurrence.csv
                        image_occurrence.py -------------> image_occurrence.csv
                        image_feature.py ----------------> image_feature.csv
```

---

## 3. Package Structure

The ETL is organized as a standard Python package at `a4_omop_etl/`.

```
a4_omop_etl/
|-- __init__.py                    # Package metadata, version 3.0.0
|-- __main__.py                    # Entry point for python -m a4_omop_etl
|-- config.py                      # Paths, constants, SOURCE_FILES manifest
|-- concepts.py                    # CSV-based concept mapping loaders
|-- helpers.py                     # Date anchoring, person/visit linkage
|-- person.py                      # PERSON table
|-- visit.py                       # VISIT_OCCURRENCE + OBSERVATION_PERIOD
|-- drug_exposure.py               # DRUG_EXPOSURE table
|-- measurement_clinical.py        # Vitals, labs, ECG
|-- measurement_cognitive.py       # PACC, MMSE, CDR + extended (CFI, Digit, etc.)
|-- measurement_biomarkers.py      # Amyloid-beta, pTau-217, Roche panel
|-- measurement_imaging.py         # MRI, amyloid PET, tau PET + extended reads
|-- measurement_cogstate.py        # CogState computerized + battery + questionnaires
|-- observation_questionnaires.py  # GDS/STAI, ADL-PQ, AD Concern
|-- observation.py                 # Lifestyle, family, milestones, C-SSRS, partner
|-- condition.py                   # Physical/neurological exam abnormalities
|-- procedure_occurrence.py        # MI-CDM: PROCEDURE_OCCURRENCE (imaging)
|-- image_occurrence.py            # MI-CDM: IMAGE_OCCURRENCE (Park et al. 2025)
|-- image_feature.py               # MI-CDM: IMAGE_FEATURE (Park et al. 2025)
|-- postprocessing.py              # Unit mapping, obs period expansion
|-- export.py                      # CSV export and ETL validation
|-- pipeline.py                    # Main orchestration (calls everything above)
```

Supporting directories at the project root:

```
Clinical/
|-- run_etl.py                     # Top-level script entry point
|-- concept_maps/                  # 17 CSVs defining OMOP concept mappings
|-- Raw Data/                      # 27 source CSVs from the clinical database
|-- Derived Data/                  # 6 pre-processed CSVs (SUBJINFO, SV, PACC, etc.)
|-- External Data/                 # 15 lab, imaging, and biomarker CSVs
|-- OMOP_Output/                   # Pipeline output (8 CSVs)
|-- Documents/
|   |-- Data Dictionaries/         # Field definitions for each data domain
|   +-- Methods/                   # Assay and imaging methodology PDFs
+-- docs/                          # Project documentation
```

### Module Responsibilities

| Module | Public Functions | Output Table(s) |
|--------|-----------------|-----------------|
| `config.py` | `load_all_sources()` | -- (returns dict of 48 DataFrames) |
| `concepts.py` | 21 loader functions | -- (returns concept dicts from CSVs) |
| `helpers.py` | `create_date_anchor()`, `build_person_lookup()`, `build_visit_lookup()`, `link_to_person()`, `link_to_visit()`, `calc_date()`, `map_visit_concept()` | date_anchor DataFrame |
| `person.py` | `create_person_table()` | PERSON |
| `visit.py` | `create_visit_occurrence()`, `create_observation_period()` | VISIT_OCCURRENCE, OBSERVATION_PERIOD |
| `drug_exposure.py` | `create_drug_exposure()` | DRUG_EXPOSURE |
| `measurement_clinical.py` | `create_measurement_clinical()` | MEASUREMENT (partial) |
| `measurement_cognitive.py` | `create_measurement_cognitive()`, `create_measurement_cognitive_extended()` | MEASUREMENT (partial) |
| `measurement_biomarkers.py` | `create_measurement_biomarkers()` | MEASUREMENT (partial) |
| `measurement_imaging.py` | `create_measurement_imaging()`, `create_measurement_imaging_extended()` | MEASUREMENT (partial) |
| `measurement_cogstate.py` | `create_measurement_cogstate()`, `create_measurement_cogstate_battery()`, `create_measurement_cogstate_questionnaires()` | MEASUREMENT (partial) |
| `observation_questionnaires.py` | `create_measurement_questionnaires()` | MEASUREMENT (partial) |
| `observation.py` | `create_observation()`, `create_observation_milestones()`, `create_observation_cssrs()`, `create_observation_study_partner()`, `create_observation_secondary_questionnaires()` | OBSERVATION (partial) |
| `condition.py` | `create_condition_occurrence()` | CONDITION_OCCURRENCE |
| `procedure_occurrence.py` | `create_procedure_occurrence()` | MI-CDM PROCEDURE_OCCURRENCE |
| `image_occurrence.py` | `create_image_occurrence()` | MI-CDM IMAGE_OCCURRENCE |
| `image_feature.py` | `create_image_feature()`, `strip_mi_cdm_annotations()` | MI-CDM IMAGE_FEATURE |
| `postprocessing.py` | `map_unit_concepts()`, `expand_observation_periods()` | -- (modifies existing tables) |
| `export.py` | `export_tables()`, `validate_etl()` | 8 CSV files on disk |
| `pipeline.py` | `main()` | -- (orchestrates all of the above) |

---

## 4. Source File Inventory

All 48 source files are declared in `config.py` as the `SOURCE_FILES` manifest.
Each tuple contains `(variable_name, subdirectory, filename)`.

### Derived Data (6 files)

Pre-processed files produced upstream from the raw clinical database.

| File | Variable | Description | Consumed By |
|------|----------|-------------|-------------|
| `SUBJINFO.csv` | `subjinfo` | Subject-level demographics, enrollment, and discontinuation dates; baseline education (EDCCNTU) + BMI (BMIBL) | `helpers.py`, `person.py`, `visit.py`, `export.py`, `observation_adqs.py` |
| `SV.csv` | `sv` | Schedule of visits with visit codes, types, and dates as days-from-consent | `visit.py`, `export.py` |
| `PACC.csv` | `pacc` | Preclinical Alzheimer Cognitive Composite scores and components | `measurement_cognitive.py` |
| `COGSTATE_COMPUTERIZED.csv` | `cogstate` | CogState computerized cognitive battery results | `measurement_cogstate.py` |
| `DS.csv` | `ds` | Study disposition milestones (randomization, completion, discontinuation) | `observation.py` |
| `cogfcsr16.csv` | `cogfcsr` | Free and Cued Selective Reminding Test (16-item) | `measurement_cognitive.py` |
| `ADQS.csv` | `adqs` | Analysis Data Questionnaire Scores with APOE genotype, treatment assignment, and population flags | `observation_adqs.py` |

### Raw Data (27 files)

Direct exports from the clinical trial database, one file per case report form.

| File | Variable | Description | Consumed By |
|------|----------|-------------|-------------|
| `ptdemog.csv` | `ptdemog` | Participant demographics with multi-racial detail (PTRACE field) | `person.py` |
| `dose.csv` | `dose` | Infusion dosing records (Solanezumab 400/800/1600 mg) | `drug_exposure.py`, `export.py` |
| `vitals.csv` | `vitals` | Vital signs (weight, height, BP, pulse, temperature) | `measurement_clinical.py` |
| `mmse.csv` | `mmse` | Mini-Mental State Examination scores | `measurement_cognitive.py` |
| `cdr.csv` | `cdr` | Clinical Dementia Rating scale | `measurement_cognitive.py` |
| `habits.csv` | `habits` | Lifestyle factors (smoking, alcohol, caffeine, exercise, sleep) | `observation.py` |
| `famhxpar.csv` | `famhxpar` | Family history -- parental dementia (mother, father) | `observation.py` |
| `famhxsib.csv` | `famhxsib` | Family history -- sibling dementia | `observation.py` |
| `phyneuro.csv` | `phyneuro` | Physical and neurological examination findings | `condition.py` |
| `cfi.csv` | `cfi` | Cognitive Function Instrument -- participant version | `measurement_cognitive.py` |
| `cfisp.csv` | `cfisp` | Cognitive Function Instrument -- study partner version | `measurement_cognitive.py` |
| `cogdigit.csv` | `cogdigit` | Digit Symbol Substitution Test | `measurement_cognitive.py` |
| `coglogic.csv` | `coglogic` | Logical Memory (Wechsler Memory Scale) | `measurement_cognitive.py` |
| `psychwell.csv` | `psychwell` | Psychological Well-Being (GDS depression, STAI anxiety) | `observation_questionnaires.py` |
| `adlpq.csv` | `adlpq` | Activities of Daily Living Prevention Questionnaire -- participant | `observation_questionnaires.py` |
| `adlpqsp.csv` | `adlpqsp` | Activities of Daily Living Prevention Questionnaire -- study partner | `observation_questionnaires.py` |
| `concerns.csv` | `concerns` | AD Concerns questionnaire | `observation_questionnaires.py` |
| `cssrs.csv` | `cssrs` | Columbia-Suicide Severity Rating Scale -- current assessment | `observation.py` |
| `cssrslv.csv` | `cssrslv` | Columbia-Suicide Severity Rating Scale -- lifetime assessment | `observation.py` |
| `spinfo.csv` | `spinfo` | Study partner information (relationship, contact hours, cohabitation) | `observation.py` |
| `ies.csv` | `ies` | Impact of Events Scale | `observation.py` |
| `ftpscale.csv` | `ftpscale` | Future Time Perspective Scale | `observation.py` |
| `rss.csv` | `rss` | Research Satisfaction Scale | `observation.py` |
| `views.csv` | `views` | Views on Research Participation | `observation.py` |
| `ruib.csv` | `ruib` | Resource Utilization Interview -- baseline | `observation.py` |
| `ruib1.csv` | `ruib1` | Resource Utilization Interview -- hospital overnight stays | `observation.py` |

### External Data (15 files)

Data produced by external laboratories, imaging core labs, or CogState.

| File | Variable | Description | Consumed By |
|------|----------|-------------|-------------|
| `clrm_lab.csv` | `clrm_lab` | Central laboratory results (chemistry, hematology) | `measurement_clinical.py` |
| `clrm_ecg.csv` | `clrm_ecg` | Central ECG interpretation results | `measurement_clinical.py` |
| `biomarker_AB_Test.csv` | `biomarker_ab` | Plasma amyloid-beta 42/40 ratio | `measurement_biomarkers.py` |
| `biomarker_pTau217.csv` | `biomarker_ptau` | Plasma phosphorylated tau-217 | `measurement_biomarkers.py` |
| `biomarker_Plasma_Roche_Results.csv` | `biomarker_roche` | Roche Elecsys panel (GFAP, NFL, pTau-181, AB42/40) | `measurement_biomarkers.py` |
| `imaging_volumetric_mri.csv` | `imaging_mri` | Volumetric MRI (hippocampal, ventricular, whole brain) | `measurement_imaging.py` |
| `imaging_SUVR_amyloid.csv` | `imaging_amyloid` | Florbetapir amyloid PET SUVR values | `measurement_imaging.py` |
| `imaging_SUVR_tau.csv` | `imaging_tau` | Flortaucipir tau PET SUVR values | `measurement_imaging.py` |
| `cogstate_battery.csv` | `cogstate_battery` | CogState battery composites (BPET, FNFT) | `measurement_cogstate.py` |
| `cogstate_macq.csv` | `cogstate_macq` | Memory Awareness of Cognitive Questionnaire | `measurement_cogstate.py` |
| `cogstate_cpath.csv` | `cogstate_cpath` | C-Path Online Data Repository questionnaire | `measurement_cogstate.py` |
| `imaging_MRI_reads.csv` | `imaging_mri_reads` | Central MRI reader assessments | `measurement_imaging.py` |
| `imaging_FLAIR_WMH_QC.csv` | `imaging_flair` | FLAIR white matter hyperintensity quantification | `measurement_imaging.py` |
| `imaging_retinal.csv` | `imaging_retinal` | Retinal imaging measurements | `measurement_imaging.py` |
| `imaging_PET_VA.csv` | `imaging_pet_va` | PET visual assessment reads | `measurement_imaging.py` |
| `imaging_Tau_PET_PetSurfer.csv` | `tau_petsurfer` | Tau PET regional analysis (FreeSurfer pipeline) | `measurement_imaging.py` |
| `imaging_Tau_PET_Stanford.csv` | `tau_stanford` | Tau PET regional analysis (Stanford pipeline) | `measurement_imaging.py` |

---

## 5. Output File Inventory

All output files are written to `OMOP_Output/` as CSV.

| File | OMOP Table | Records | Description |
|------|-----------|---------|-------------|
| `person.csv` | PERSON | 6,945 | One row per enrolled subject with demographics |
| `visit_occurrence.csv` | VISIT_OCCURRENCE | 99,795 | Clinical visits excluding "Not Done" entries |
| `observation_period.csv` | OBSERVATION_PERIOD | 6,945 | One continuous period per person (consent to last event) |
| `drug_exposure.csv` | DRUG_EXPOSURE | 74,777 | Completed Solanezumab infusions |
| `measurement.csv` | MEASUREMENT | 4,494,112 | All quantitative clinical data (combined from 9 measurement phases; includes item-level cognitive/CogState/biomarker data added in Rounds 1-5) |
| `observation.csv` | OBSERVATION | 1,511,872 | Qualitative observations including questionnaires (combined from 8 observation phases; includes item-level ADLPQ, GDS, IES, FTP, RSS, VIEWS added in Rounds 1-5) |
| `condition_occurrence.csv` | CONDITION_OCCURRENCE | 7,391 | Abnormal physical & neurological exam findings from phyneuro |
| `procedure_occurrence.csv` | PROCEDURE_OCCURRENCE | 20,783 | Imaging procedures (MRI brain, PET amyloid, PET tau, retinal) — standard OMOP CDM v5.4 table |
| `mi_cdm/image_occurrence.csv` | IMAGE_OCCURRENCE | 23,898 | DICOM series equivalents (MI-CDM extension table per Park & Jeon et al. 2024) |
| `mi_cdm/image_feature.csv` | IMAGE_FEATURE | 675,690 | Polymorphic bridge to measurement (MI-CDM extension table per Park & Jeon et al. 2024) |
| `date_anchor.csv` | -- (utility) | 6,945 | BID-to-synthetic-date mapping (not an OMOP table) |

**Total records across output tables: 7,003,365** (counts grew across Rounds 1-5 with item-level mapping expansions)

> **Note:** Questionnaire records (GDS, STAI, ADL-PQ, AD Concerns) were moved from MEASUREMENT to OBSERVATION in v2.1 per OMOP CDM specification that survey/questionnaire responses belong in OBSERVATION domain.

---

## 6. Pipeline Phases

The `main()` function in `pipeline.py` orchestrates the following phases in
strict sequential order. Each phase depends on outputs from earlier phases
(primarily the person, visit, and date_anchor DataFrames).

### Phase 1 -- Load Sources

```python
src = load_all_sources()  # returns dict of 48 DataFrames
```

Reads all 48 CSVs declared in the `SOURCE_FILES` manifest into memory as a
single dictionary keyed by variable name.

### Phase 2 -- Date Anchoring

```python
date_anchor = create_date_anchor(src['subjinfo'])
```

Generates a privacy-preserving synthetic consent date for every subject. See
[Section 7](#7-date-anchoring-strategy) for the algorithm.

### Phase 3 -- PERSON

```python
person = create_person_table(src['subjinfo'], date_anchor, src['ptdemog'])
```

Builds the PERSON table from SUBJINFO demographics merged with multi-racial
detail from ptdemog. Maps gender, race, and ethnicity to standard OMOP concept
IDs. Calculates year of birth from age at consent.

### Phase 4 -- VISIT_OCCURRENCE

```python
visit_occurrence = create_visit_occurrence(src['sv'], person, date_anchor)
```

Converts schedule-of-visits records into OMOP visits. Filters out "Not Done"
entries. Classifies visits into screening (001-005), baseline (006), infusion,
unscheduled (701-705), and default clinic categories.

### Phase 5 -- OBSERVATION_PERIOD

```python
observation_period = create_observation_period(src['subjinfo'], person, date_anchor, src['sv'])
```

Creates one continuous observation period per person spanning from consent date
(day 0) to either the discontinuation date or the last recorded visit date.
The `person` parameter ensures referential integrity between person_id values
in OBSERVATION_PERIOD and PERSON tables.

### Phase 6 -- DRUG_EXPOSURE

```python
drug_exposure = create_drug_exposure(src['dose'], person, visit_occurrence, date_anchor)
```

Transforms Solanezumab infusion records into DRUG_EXPOSURE rows. Filters to
completed doses only (DONE='Yes'). Records route as intravenous (concept
4171047) and maps dose levels (400, 800, 1600 mg) to custom concept IDs.

### Phases 7-11 -- MEASUREMENT (10 sub-phases)

All measurement sub-phases produce partial DataFrames that are concatenated into
a single MEASUREMENT table. After concatenation, measurement IDs are reassigned
sequentially from 1 to N.

| Sub-phase | Function | Source Files | Domain |
|-----------|----------|-------------|--------|
| 7 | `create_measurement_clinical()` | vitals, clrm_lab, clrm_ecg | Vital signs, lab results, ECG |
| 8 | `create_measurement_cognitive()` | pacc, mmse, cdr | PACC composite, MMSE, CDR |
| 9 | `create_measurement_biomarkers()` | biomarker_ab, biomarker_ptau, biomarker_roche | Plasma AD biomarkers |
| 10 | `create_measurement_imaging()` | imaging_mri, imaging_amyloid, imaging_tau | MRI volumes, PET SUVR |
| 10b | `create_measurement_cogstate()` | cogstate | Computerized cognitive tests |
| 10c | `create_measurement_cogstate_battery()` | cogstate_battery | CogState BPET/FNFT composites |
| 16 | `create_measurement_cognitive_extended()` | cfi, cfisp, cogdigit, cogfcsr, coglogic | CFI, Digit Symbol, FCSR, Logical Memory |
| 17 | `create_measurement_questionnaires()` | psychwell, adlpq, adlpqsp, concerns | GDS, STAI, ADL-PQ, AD Concern |
| 18 | `create_measurement_imaging_extended()` | imaging_mri_reads, imaging_flair, imaging_retinal, imaging_pet_va, tau_petsurfer, tau_stanford | MRI reads, FLAIR, retinal, Tau PetSurfer/Stanford |
| 19 | `create_measurement_cogstate_questionnaires()` | cogstate_macq, cogstate_cpath | MACQ, C-Path questionnaires |

After concatenation, `map_unit_concepts()` is applied to fill in
`unit_concept_id` from a 43-entry mapping table.

### Phases 12-15 -- OBSERVATION (5 sub-phases)

All observation sub-phases produce partial DataFrames that are concatenated into
a single OBSERVATION table with IDs reassigned 1 to N.

| Sub-phase | Function | Source Files | Domain |
|-----------|----------|-------------|--------|
| 12a | `create_observation()` | habits, famhxpar, famhxsib | Lifestyle factors, family dementia history |
| 12b | `create_observation_milestones()` | ds | Randomization, completion, discontinuation |
| 12c | `create_observation_cssrs()` | cssrs, cssrslv | Suicidality screening (current + lifetime) |
| 12d | `create_observation_study_partner()` | spinfo | Partner relationship, contact hours, cohabitation |
| 12e | `create_observation_secondary_questionnaires()` | ies, ftpscale, rss, views, ruib, ruib1 | IES, FTP, RSS, VIEWS, resource utilization |
| 12f | `create_observation_adqs()` | adqs | APOE genotype, APOE4 carrier status, treatment assignment (TX), study population flags (ITT, mITT, PP, Safety) |
| 12g | `create_observation_questionnaires()` | psychwell, adlpq, adlpqsp, concerns | GDS depression, STAI anxiety, ADL-PQ, AD Concerns (moved from MEASUREMENT per OMOP spec) |

### Phase 16 -- CONDITION_OCCURRENCE

```python
condition_occurrence = create_condition_occurrence(src['phyneuro'], person, visit_occurrence, date_anchor)
```

Extracts abnormal findings (value == 2) from physical exam fields (PXCARD,
PXPULM, PXABDOM, PXMUSCUL, PXEDEMA, PXSKIN) and neurological exam fields
(NXGAIT, NXMOTOR, NXSENSOR, NXTREMOR).

### Phase 17 -- Post-Processing

Two post-processing steps are applied to finalize the tables:

1. **Unit mapping** -- maps `unit_source_value` to `unit_concept_id` via
   `concept_maps/units.csv` (case-insensitive).
2. **Observation period expansion** -- extends end dates to cover the latest
   measurement, observation, or drug exposure per person.

Visit linkage is **not** a post-processing step: records are linked to visits
by exact VISCODE (or exact date for imaging) during extraction in
`prepare_source_df()`. There is no fuzzy/day-window matching; unmatched records
keep a null `visit_occurrence_id`.

### Phases 30-32 -- MI-CDM Extension (Park et al. 2025)

The Medical Imaging CDM extension adds three tables linking imaging procedures to their derived measurements via the polymorphic event pattern.

| Phase | Function | Description |
|-------|----------|-------------|
| 30 | `create_procedure_occurrence()` | Imaging procedures (MRI, PET, retinal) deduped by (person, procedure, date) |
| 31 | `create_image_occurrence()` | One row per DICOM series equivalent, with synthetic DICOM UIDs |
| 32 | `create_image_feature()` | Links each imaging measurement to its image_occurrence via `image_feature_event_field_concept_id` (1147330) and `image_feature_event_id` (measurement_id) |

After image_feature creation, `strip_mi_cdm_annotations()` removes temporary `_mi_cdm_*` columns from measurement before export.

### Phase 18 -- Export and Validation

```python
export_tables({...})        # writes 8 CSVs to OMOP_Output/
validate_etl(person, ...)   # runs 5 quality checks
```

---

## 7. Date Anchoring Strategy

All source dates in the A4/LEARN dataset are anonymized as integer offsets
(days from consent) rather than calendar dates. The ETL must reconstruct
calendar dates for OMOP compliance while preserving privacy.

### Algorithm

```
For each subject BID:
    1. hash_value  = MD5(BID)             # deterministic 128-bit hash
    2. offset_days = hash_value mod 365   # range: 0 to 364
    3. synthetic_consent_date = 2020-01-01 + offset_days
```

### Properties

- **Deterministic**: The same BID always produces the same synthetic dates,
  ensuring reproducibility across pipeline runs.
- **Privacy-preserving**: Synthetic dates bear no relationship to actual
  calendar dates. The base date (2020-01-01) is arbitrary.
- **Temporally consistent**: All events for a given subject maintain their
  correct relative ordering and interval durations because the offset is applied
  uniformly to all dates within that subject.
- **Cross-subject de-linkage**: Different subjects receive different offsets,
  preventing cross-referencing by date across subjects.

### Date Computation

Once the synthetic consent date is established, all other dates are computed by
adding the relevant `*_DAYS_CONSENT` column value:

```
event_date = synthetic_consent_date + DAYS_CONSENT_value
```

This formula is applied in `helpers.calc_date()` and in local `calc_date`
helper functions within domain modules.

---

## 8. Concept Mapping Architecture

OMOP requires every clinical fact to reference a standard concept ID from the
OMOP Vocabulary. This ETL externalizes all concept mappings into CSV files
stored in `concept_maps/`, loaded at runtime by functions in `concepts.py`.

### Concept Map Files

| CSV File | Loader Function(s) | Maps From | Maps To |
|----------|-------------------|-----------|---------|
| `demographics.csv` | `load_gender_concepts()`, `load_race_concepts()`, `load_ethnicity_concepts()` | Source demographic codes | Standard OMOP person concept IDs |
| `visits.csv` | `load_visit_concepts()` | Visit type strings | OMOP visit_concept_id values |
| `drugs.csv` | `load_drug_concepts()` | Dose in mg (int) | Custom drug concept IDs (2000000001-3) |
| `units.csv` | `load_unit_concept_map()` | Unit source strings | OMOP unit_concept_id (UCUM) |
| `vitals.csv` | `load_vitals_concepts()` | Vital sign field names | LOINC concept IDs + unit info |
| `ecg.csv` | `load_ecg_concepts()` | ECG parameter names | LOINC concept IDs |
| `labs.csv` | `load_lab_concepts()` | Lab test codes | LOINC concept IDs |
| `cognitive.csv` | `load_cognitive_concepts()`, `load_cognitive_extended()` | Cognitive test names | Custom concept IDs (2100000001+) |
| `cogstate.csv` | `load_cogstate_concepts()`, `load_cogstate_battery_concepts()`, `load_cogstate_questionnaire_concepts()` | CogState test/composite names | Custom concept IDs |
| `biomarkers.csv` | `load_biomarker_concepts()` | Biomarker analyte names | Custom concept IDs |
| `imaging.csv` | `load_imaging_concepts()`, `load_imaging_extended()` | Imaging measure names | Custom concept IDs |
| `observations.csv` | `load_observation_concepts()`, `load_study_partner_concepts()` | Observation field names | Custom concept IDs |
| `conditions.csv` | `load_condition_concepts()` | Exam field names | Custom concept IDs |
| `milestones.csv` | `load_milestone_concepts()` | Disposition event codes | Custom concept IDs |
| `questionnaires.csv` | `load_questionnaire_concepts()`, `load_secondary_questionnaire_concepts()` | Questionnaire score names | Custom concept IDs |
| `cssrs.csv` | `load_cssrs_concepts()` | C-SSRS item names | Custom concept IDs |
| `cssrslv_columns.csv` | `load_cssrslv_column_map()` | Lifetime column names | Standard C-SSRS item keys |
| `procedures.csv` | `load_procedure_concepts()` | Procedure type codes | Custom imaging procedure concept IDs |
| `modalities.csv` | `load_modality_concepts()` | DICOM modality codes (MR, PT, OP) | Custom modality concept IDs |
| `image_feature_types.csv` | `load_image_feature_type_concepts()` | Provenance types | Standard type concept IDs (32880, 32817) |
| `image_findings.csv` | `load_image_finding_concepts()` | Finding categories | Custom finding concept IDs |

### Custom Concept ID Ranges

Standard OMOP concepts (LOINC, SNOMED, etc.) are used wherever a mapping exists.
For trial-specific measurements without standard vocabulary entries, custom
concept IDs are assigned in reserved ranges:

| Range | Domain |
|-------|--------|
| 2000000001 -- 2000000003 | Solanezumab dose levels |
| 2000000004 -- 2000000020 | Study milestones and disposition events |
| 2100000001+ | Clinical measurements, cognitive tests, biomarkers, imaging |
| 2100000080 -- 2100000099 | MI-CDM: imaging procedures, DICOM modalities, image findings |

---

## 9. Module Dependency Diagram

The diagram below shows which modules call which during pipeline execution.
Arrows indicate "calls into" or "depends on output of."

```
pipeline.py
  |
  +---> config.py
  |       load_all_sources() -------> reads 48 CSVs from disk
  |
  +---> helpers.py
  |       create_date_anchor() -----> uses subjinfo
  |
  +---> person.py
  |       create_person_table() ----> uses subjinfo, date_anchor, ptdemog
  |       depends on: concepts.py (demographics.csv)
  |
  +---> visit.py
  |       create_visit_occurrence() -> uses sv, person, date_anchor
  |       create_observation_period()-> uses subjinfo, person, date_anchor, sv
  |       depends on: concepts.py (visits.csv), helpers.py (map_visit_concept)
  |
  +---> drug_exposure.py
  |       create_drug_exposure() ---> uses dose, person, visit_occurrence, date_anchor
  |       depends on: concepts.py (drugs.csv)
  |
  +---> measurement_clinical.py
  |       create_measurement_clinical() -> uses vitals, clrm_lab, clrm_ecg,
  |                                         person, visit_occurrence, date_anchor
  |       depends on: concepts.py (vitals.csv, labs.csv, ecg.csv)
  |
  +---> measurement_cognitive.py
  |       create_measurement_cognitive() --> uses pacc, mmse, cdr
  |       create_measurement_cognitive_extended() --> uses cfi, cfisp,
  |                                                    cogdigit, cogfcsr, coglogic
  |       depends on: concepts.py (cognitive.csv)
  |
  +---> measurement_biomarkers.py
  |       create_measurement_biomarkers() -> uses biomarker_ab, biomarker_ptau,
  |                                           biomarker_roche
  |       depends on: concepts.py (biomarkers.csv)
  |
  +---> measurement_imaging.py
  |       create_measurement_imaging() ---------> uses imaging_mri,
  |                                                imaging_amyloid, imaging_tau
  |       create_measurement_imaging_extended() -> uses imaging_mri_reads,
  |                                                imaging_flair, imaging_retinal,
  |                                                imaging_pet_va, tau_petsurfer,
  |                                                tau_stanford
  |       depends on: concepts.py (imaging.csv)
  |
  +---> measurement_cogstate.py
  |       create_measurement_cogstate() ---------> uses cogstate
  |       create_measurement_cogstate_battery() --> uses cogstate_battery
  |       create_measurement_cogstate_questionnaires() -> uses cogstate_macq,
  |                                                        cogstate_cpath
  |       depends on: concepts.py (cogstate.csv)
  |
  +---> observation_questionnaires.py
  |       create_observation_questionnaires() -> uses psychwell, adlpq,
  |                                               adlpqsp, concerns
  |       depends on: concepts.py (questionnaires.csv)
  |       Note: Outputs OBSERVATION records (moved from MEASUREMENT per OMOP spec)
  |
  +---> observation_adqs.py
  |       create_observation_adqs() -----------> uses adqs
  |       depends on: concepts.py (adqs.csv)
  |       Extracts: APOE genotype, APOE4 carrier status, treatment assignment,
  |                 study population flags (ITT, mITT, PP, Safety)
  |
  +---> observation.py
  |       create_observation() -----------------> uses habits, famhxpar, famhxsib
  |       create_observation_milestones() -------> uses ds
  |       create_observation_cssrs() ------------> uses cssrs, cssrslv
  |       create_observation_study_partner() ----> uses spinfo
  |       create_observation_secondary_questionnaires() -> uses ies, ftpscale,
  |                                                         rss, views, ruib, ruib1
  |       depends on: concepts.py (observations.csv, milestones.csv,
  |                                cssrs.csv, cssrslv_columns.csv,
  |                                questionnaires.csv)
  |
  +---> condition.py
  |       create_condition_occurrence() --------> uses phyneuro
  |       depends on: concepts.py (conditions.csv)
  |
  +---> procedure_occurrence.py
  |       create_procedure_occurrence() -> uses imaging sources, person, visit, date_anchor
  |       depends on: concepts.py (procedures.csv), helpers.py
  |
  +---> image_occurrence.py
  |       create_image_occurrence() -----> uses imaging sources, person, visit, procedure_occurrence, date_anchor
  |       depends on: concepts.py (procedures.csv, modalities.csv), helpers.py
  |
  +---> image_feature.py
  |       create_image_feature() --------> uses measurement (with _mi_cdm annotations), image_occurrence
  |       strip_mi_cdm_annotations() ----> removes temporary columns from measurement
  |       depends on: concepts.py (image_findings.csv, image_feature_types.csv)
  |
  +---> postprocessing.py
  |       map_unit_concepts() -------> modifies measurement (uses units.csv)
  |       expand_observation_periods() -> modifies observation_period
  |       depends on: concepts.py (units.csv)
  |
  +---> export.py
          export_tables() -----------> writes 8 CSVs
          validate_etl() ------------> checks person, visit, obs_period,
                                        drug_exposure against source counts
```

### Shared Dependency: `concepts.py`

Every domain module depends on `concepts.py` for its concept mappings. The
`concepts.py` module in turn reads from the `concept_maps/` directory. This
design centralizes all vocabulary decisions into editable CSV files, separating
mapping logic from transformation logic.

### Shared Dependency: `helpers.py`

Most domain modules use the person-lookup and visit-linkage utilities from
`helpers.py`, following a consistent pattern:

1. Merge source data with `person_lookup` on BID to obtain `person_id`.
2. Merge with `visit_lookup` on `visit_source_value` (BID + VISCODE) to obtain
   `visit_occurrence_id`.
3. Merge with `date_anchor` on BID to obtain `synthetic_consent_date`.
4. Compute event dates as `synthetic_consent_date + DAYS_CONSENT`.

---

## 10. Post-Processing

Three post-processing steps refine the output after all domain tables are built.

### 10.1 Unit Concept Mapping

**Module**: `postprocessing.map_unit_concepts()`
**Input**: Combined measurement DataFrame
**Mapping source**: `concept_maps/units.csv` (43 unit entries)

Scans all measurement rows where `unit_concept_id` is 0 but
`unit_source_value` is not null, and attempts to map the source string to a
standard UCUM concept ID.

Observed result: approximately 30-55% of rows have mapped UCUM unit concepts; the
remainder are either unitless (scores, ratios, z-scores) or have non-UCUM
source units that don't have a standard equivalent. Exact counts vary across
Rounds 1-5 as item-level data has been added.

### 10.2 Observation Period Expansion

**Module**: `postprocessing.expand_observation_periods()`
**Input**: observation_period, measurement, observation, drug_exposure DataFrames

The initial observation period end date is set to either the discontinuation
date or the last visit date. However, some clinical events (measurements,
observations, drug exposures) may have dates beyond the last recorded visit.
This step extends `observation_period_end_date` to the latest event date per
person.

Observed result: approximately 4,404 of 6,945 persons have their observation
period expanded.

### 10.3 Visit Linkage (exact match — not post-processing)

**Module**: `helpers.prepare_source_df()` (applied during extraction, not post-processing)
**Method**: exact `BID`+`VISCODE` key (or exact synthetic date for imaging)

Records are linked to visits by an exact key match: `prepare_source_df` builds
`BID_VISCODE` and merges against `visit_occurrence` on that key. Imaging tables,
which carry no VISCODE, link by exact `*_DAYS_CONSENT` synthetic date instead.

There is **no fuzzy/day-window matching**. Records with no matching VISCODE or
date — subject-level derived values, date-only imaging (e.g. retinal merged
without a visit frame), or assessments without a recorded VISCODE — keep a null
`visit_occurrence_id`.

Observed result: approximately 3,517,849 of 4,499,674 measurements (~78%) carry
a `visit_occurrence_id`; the remainder are left null.

---

## 11. Validation

The `validate_etl()` function in `export.py` performs five automated quality
checks after the pipeline completes:

| Check | Description | Expected Result |
|-------|-------------|-----------------|
| 1. Person count | Number of PERSON rows equals number of unique BIDs in SUBJINFO | 6,945 = 6,945 |
| 2. Visit count | Number of VISIT_OCCURRENCE rows is within 5% of SV rows (excluding "Not Done") | Within tolerance |
| 3. No orphan visits | Every `person_id` in visit_occurrence exists in the person table | 0 orphans |
| 4. Observation period coverage | Every person has at least one observation period | 0 missing |
| 5. Drug exposure count | Number of DRUG_EXPOSURE rows equals dose.csv rows where DONE='Yes' | 74,777 = 74,777 |

The pipeline prints PASS or FAIL for each check and returns a dictionary of
boolean results.

---

## 12. Running the Pipeline

### Prerequisites

- Python 3.x
- pandas (the only external dependency)
- Source data files in `Raw Data/`, `Derived Data/`, and `External Data/`
  subdirectories
- Concept mapping CSVs in `concept_maps/`

### Execution

Run the pipeline using either of these commands from the project root:

```bash
# Option 1: Top-level script
python run_etl.py

# Option 2: Package module
python -m a4_omop_etl
```

### Output

The pipeline writes 8 CSV files to `OMOP_Output/` and prints progress and
validation results to stdout. A successful run ends with:

```
============================================================
ETL Complete - ALL VALIDATIONS PASSED
Output files in: OMOP_Output
============================================================
```

### Runtime Behavior

The pipeline loads all 48 source files into memory at startup and processes them
sequentially. Each phase prints the number of input and output records for
traceability. The `main()` function returns a dictionary containing all output
DataFrames and validation results, which can be used for downstream analysis in
an interactive session:

```python
from a4_omop_etl.pipeline import main
results = main()
person_df = results['person']
```

---

## 13. Key Design Decisions

### Single-script orchestration

The `pipeline.py` module reads like a table of contents. Each phase calls one or
two functions from a domain module and passes the result forward. This makes the
execution order explicit and easy to audit.

### Externalized concept mappings

All OMOP concept IDs are stored in CSV files under `concept_maps/` rather than
hardcoded in Python. This allows clinical informaticists to review and update
mappings without modifying code.

### Privacy-preserving dates via MD5 hashing

The date anchoring strategy uses a deterministic hash to generate per-subject
date offsets. This avoids the need for a separate de-identification key file
while still producing reproducible dates across runs.

### Measurement table consolidation

Ten separate measurement-creation functions produce partial DataFrames that are
concatenated into a single MEASUREMENT table. This separation keeps each domain
module focused on one data type while producing a unified output that conforms
to OMOP's single-table-per-domain design.

### Post-processing as a separate phase

Unit mapping and observation period expansion are applied
after all domain tables are built. This avoids circular dependencies (for
example, expanding observation periods requires knowing the latest measurement
date, which is not available until all measurements are created).

### Visit linkage pattern

Every domain module follows the same linkage pattern: merge on BID for
`person_id`, construct `BID_VISCODE` for `visit_occurrence_id`, and merge with
the date anchor for event dates. The `helpers.py` module provides reusable
functions for these operations, although some modules implement the pattern
inline for domain-specific requirements.

### Multi-racial handling

The `ptdemog.csv` file contains comma-separated race values in the PTRACE
field. The person table preserves the original multi-racial string in
`race_source_value` while mapping the primary RACE code from SUBJINFO to a
standard concept ID for `race_concept_id`.

---

*This document describes the ETL architecture as implemented in version 3.0.0
of the a4_omop_etl package.*
