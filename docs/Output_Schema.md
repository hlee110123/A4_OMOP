# Output Schema Reference

A4/LEARN OMOP CDM v5.4 ETL Pipeline -- Output File Specification

**Pipeline**: `a4_omop_etl`
**OMOP CDM version**: 5.4
**Output directory**: `OMOP_Output/`
**Last verified**: 2026-02-05

---

## Contents

- [Overview](#overview)
- [File Summary](#file-summary)
- [person.csv](#personcsv)
- [visit_occurrence.csv](#visit_occurrencecsv)
- [observation_period.csv](#observation_periodcsv)
- [drug_exposure.csv](#drug_exposurecsv)
- [measurement.csv](#measurementcsv)
- [observation.csv](#observationcsv)
- [condition_occurrence.csv](#condition_occurrencecsv)
- [procedure_occurrence.csv](#procedure_occurrencecsv)
- [mi_cdm/image_occurrence.csv](#mi_cdmimage_occurrencecsv)
- [mi_cdm/image_feature.csv](#mi_cdmimage_featurecsv)
- [date_anchor.csv](#date_anchorcsv)
- [Date Handling](#date-handling)
- [Joining Tables](#joining-tables)
- [Data Quality Notes](#data-quality-notes)
- [OMOP Concept Quick Reference](#omop-concept-quick-reference)

---

## Overview

The ETL pipeline transforms clinical trial data from the A4 (Anti-Amyloid Treatment in Asymptomatic Alzheimer's Disease) and LEARN (Longitudinal Evaluation of Amyloid Risk and Neurodegeneration) studies into the OMOP Common Data Model v5.4 format. It produces eight CSV files covering demographics, visits, drug exposures, clinical measurements, observations, and conditions.

All dates in the output are **synthetic**. The pipeline applies a deterministic per-subject offset (0--364 days from 2020-01-01) derived from an MD5 hash of the subject's blinded ID (BID). Temporal relationships within each subject are preserved exactly. See [Date Handling](#date-handling) for details.

---

## File Summary

| File | OMOP Table | Records | Description |
|------|-----------|--------:|-------------|
| `person.csv` | PERSON | 6,945 | Subject demographics |
| `visit_occurrence.csv` | VISIT_OCCURRENCE | 99,795 | Clinical site visits |
| `observation_period.csv` | OBSERVATION_PERIOD | 6,945 | Per-subject enrollment windows |
| `drug_exposure.csv` | DRUG_EXPOSURE | 74,777 | Solanezumab infusion records |
| `measurement.csv` | MEASUREMENT | 4,494,112 | Labs, vitals, cognitive tests + items, biomarkers, imaging, CogState (battery + MACQ + C-PATH items) |
| `observation.csv` | OBSERVATION | 1,511,872 | Lifestyle, family history, C-SSRS, ADQS, questionnaire items (ADLPQ, GDS, IES, FTP, RSS, VIEWS, etc.) |
| `condition_occurrence.csv` | CONDITION_OCCURRENCE | 7,391 | Abnormal physical & neurological exam findings from phyneuro |
| `procedure_occurrence.csv` | PROCEDURE_OCCURRENCE | 20,783 | Imaging procedures (MRI brain, PET amyloid, PET tau, retinal) — standard OMOP CDM v5.4 table |
| `mi_cdm/image_occurrence.csv` | IMAGE_OCCURRENCE | 23,898 | DICOM series equivalents — MI-CDM extension (Park & Jeon et al. 2024) |
| `mi_cdm/image_feature.csv` | IMAGE_FEATURE | 675,690 | Polymorphic bridge: image ↔ measurement — MI-CDM extension (Park & Jeon et al. 2024) |
| `date_anchor.csv` | _(utility)_ | 6,945 | De-identification offset reference |

**Total records across all files**: 7,003,365 (counts grew substantially across Rounds 1-5 with item-level mapping additions for ADLPQ, IES, GDS, CogState MACQ/C-PATH, FTP/RSS/VIEWS, and ADQS APOE genotypes)

---

## person.csv

Demographics for every enrolled subject. One row per person.

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `person_id` | integer | No | Sequential identifier, 1--6,945 |
| `gender_concept_id` | integer | No | OMOP gender concept |
| `year_of_birth` | integer | No | Birth year (range: 1928--1961) |
| `month_of_birth` | integer | No | Birth month (set to 6 for all subjects) |
| `day_of_birth` | integer | No | Birth day (set to 15 for all subjects) |
| `birth_datetime` | datetime | Yes | Always NULL |
| `race_concept_id` | integer | No | OMOP race concept |
| `ethnicity_concept_id` | integer | No | OMOP ethnicity concept |
| `location_id` | integer | Yes | Always NULL |
| `provider_id` | integer | Yes | Always NULL |
| `care_site_id` | integer | Yes | Always NULL |
| `person_source_value` | string | No | Blinded subject ID (e.g., `B00000000`) |
| `gender_source_value` | integer | No | Source `SUBJINFO.SEX` code (1=Female, 2=Male) |
| `gender_source_concept_id` | integer | No | Always 0 |
| `race_source_value` | string | No | Source race code(s) |
| `race_source_concept_id` | integer | No | Always 0 |
| `ethnicity_source_value` | string | No | Source ethnicity code |
| `ethnicity_source_concept_id` | integer | No | Always 0 |

### Key Value Distributions

**Gender**

| `gender_concept_id` | Label | Count |
|---------------------:|-------|------:|
| 8507 | Male | 2,940 |
| 8532 | Female | 4,005 |

**Race**

| `race_concept_id` | Label | Count |
|-------------------:|-------|------:|
| 8527 | White | 6,176 |
| 8516 | Black or African American | 339 |
| 8515 | Asian | 291 |
| 0 | Unknown / Multi-racial | 115 |
| 8657 | American Indian or Alaska Native | 19 |
| 8557 | Native Hawaiian or Other Pacific Islander | 5 |

**Ethnicity**

| `ethnicity_concept_id` | Label | Count |
|------------------------:|-------|------:|
| 38003564 | Not Hispanic or Latino | 6,598 |
| 38003563 | Hispanic or Latino | 276 |
| 0 | Unknown | 71 |

### Notes

- `month_of_birth` and `day_of_birth` are set to fixed placeholder values (June 15) for all subjects because exact birth dates are not available in the source data. Only `year_of_birth` varies by subject.
- `birth_datetime` is always NULL.
- `location_id`, `provider_id`, and `care_site_id` are always NULL (not captured in this dataset).
- Subjects with multiple race codes in the source receive `race_concept_id = 0`.

---

## visit_occurrence.csv

Clinical site visits. Excludes visits recorded as "Not Done" in the source schedule (SV) data.

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `visit_occurrence_id` | integer | No | Sequential identifier |
| `person_id` | integer | No | FK to `person.person_id` |
| `visit_concept_id` | integer | No | OMOP visit type concept |
| `visit_start_date` | date | No | Visit date (synthetic) |
| `visit_start_datetime` | datetime | Yes | Always NULL |
| `visit_end_date` | date | No | Same as `visit_start_date` (single-day visits) |
| `visit_end_datetime` | datetime | Yes | Always NULL |
| `visit_type_concept_id` | integer | No | Always 32817 (EHR) |
| `provider_id` | integer | Yes | Always NULL |
| `care_site_id` | integer | Yes | Always NULL |
| `visit_source_value` | string | No | Format: `BID_VISCODE` (e.g., `B00000000_006`) |
| `visit_source_concept_id` | integer | No | Always 0 |
| `admitted_from_concept_id` | integer | No | Always 0 |
| `admitted_from_source_value` | string | Yes | Always NULL |
| `discharged_to_concept_id` | integer | No | Always 0 |
| `discharged_to_source_value` | string | Yes | Always NULL |
| `preceding_visit_occurrence_id` | integer | Yes | Always NULL |

### Visit Concept Distribution

| `visit_concept_id` | Label | Count |
|--------------------:|-------|------:|
| 32035 | Visit derived from EHR encounter record (screening/baseline) | 50,103 |
| 32036 | Visit derived from EHR order (treatment/infusion/unscheduled) | 49,597 |
| 32220 | Other visit type | 95 |

### Notes

- All visits are modeled as single-day events (`visit_end_date = visit_start_date`).
- The `visit_source_value` is a composite key of `BID` and `VISCODE`, joined by an underscore.
- VISCODE values such as `001` indicate screening, while higher codes represent follow-up, treatment, and unscheduled visits.

---

## observation_period.csv

One row per person defining the window during which clinical observations were recorded.

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `observation_period_id` | integer | No | Sequential identifier, matches `person_id` |
| `person_id` | integer | No | FK to `person.person_id` |
| `observation_period_start_date` | date | No | Earliest visit date for the subject |
| `observation_period_end_date` | date | No | Latest date across visits, measurements, observations, and drug exposures |
| `period_type_concept_id` | integer | No | Always 32817 (EHR) |

### Notes

- Start dates range from 2020-01-01 to 2020-12-30 (determined by the synthetic consent date offset).
- End dates extend as far as 2029-10-03, reflecting the full longitudinal follow-up period.
- The end date is expanded during post-processing to cover the latest recorded event (measurement, observation, or drug exposure) for each subject. This expansion affected 4,404 of 6,945 subjects.

---

## drug_exposure.csv

Solanezumab intravenous infusion records. Only doses marked as `DONE='Yes'` in the source are included (74,777 of 75,241 source records).

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `drug_exposure_id` | integer | No | Sequential identifier |
| `person_id` | integer | No | FK to `person.person_id` |
| `drug_concept_id` | integer | No | Custom OMOP concept for dose level |
| `drug_exposure_start_date` | date | No | Infusion date (synthetic) |
| `drug_exposure_start_datetime` | datetime | Yes | Always NULL |
| `drug_exposure_end_date` | date | No | Same as start date (single-day infusions) |
| `drug_exposure_end_datetime` | datetime | Yes | Always NULL |
| `verbatim_end_date` | date | Yes | Always NULL |
| `drug_type_concept_id` | integer | No | Always 32838 (EHR dispensing record) |
| `stop_reason` | string | Yes | Dose completion status |
| `refills` | integer | Yes | Always NULL |
| `quantity` | float | No | Dose in mg (0, 400, 800, or 1600) |
| `days_supply` | integer | Yes | Always NULL |
| `sig` | string | Yes | Always NULL |
| `route_concept_id` | integer | No | Always 4171047 (Intravenous) |
| `lot_number` | string | Yes | Always NULL |
| `provider_id` | integer | Yes | Always NULL |
| `visit_occurrence_id` | float | Yes | FK to `visit_occurrence.visit_occurrence_id` |
| `visit_detail_id` | integer | Yes | Always NULL |
| `drug_source_value` | string | No | e.g., `Solanezumab 400.0mg` |
| `drug_source_concept_id` | integer | No | Always 0 |
| `route_source_value` | string | No | Always `IV infusion` |
| `dose_unit_source_value` | string | No | Always `mg` |

### Drug Concept Distribution

| `drug_concept_id` | Description | Quantity (mg) | Count |
|-------------------:|-------------|------:|------:|
| 2000000001 | Solanezumab 400 mg | 400 | 23,707 |
| 2000000002 | Solanezumab 800 mg | 800 | 2,280 |
| 2000000003 | Solanezumab 1600 mg | 1,600 | 48,785 |
| 0 | Unmapped (0 mg dose) | 0 | 5 |

### Dose Completion

| `stop_reason` | Count |
|----------------|------:|
| Complete dose given (400mg: >=52.5mL \| 800mg: >=105mL \| 1600mg: >=210mL) | 74,747 |
| Partial dose given (400mg: <52.5mL \| 800mg: <105mL \| 1600mg: <210mL) | 30 |

### Notes

- 74,775 of 74,777 records are linked to a visit via `visit_occurrence_id`. Two records could not be matched.
- The 5 records with `drug_concept_id = 0` correspond to doses with 0.0 mg quantity.
- `visit_occurrence_id` is stored as float because pandas represents nullable integers as float when NaN values are present.

---

## measurement.csv

The largest output file. Contains clinical labs, vitals, ECG parameters, cognitive assessments, AD biomarkers, neuroimaging results, CogState computerized tests, and questionnaire scores.

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `person_id` | integer | No | FK to `person.person_id` |
| `measurement_concept_id` | integer | No | OMOP or custom concept ID |
| `measurement_date` | date | No | Measurement date (synthetic) |
| `measurement_datetime` | datetime | Yes | Always NULL |
| `measurement_time` | time | Yes | Always NULL |
| `measurement_type_concept_id` | integer | No | Always 32817 (EHR) |
| `operator_concept_id` | integer | Yes | Always NULL |
| `value_as_number` | float | Yes | Numeric result value |
| `value_as_concept_id` | integer | Yes | Concept for categorical results |
| `unit_concept_id` | integer | No | OMOP unit concept (0 if unmapped) |
| `range_low` | float | Yes | Reference range lower bound |
| `range_high` | float | Yes | Reference range upper bound |
| `provider_id` | integer | Yes | Always NULL |
| `visit_occurrence_id` | float | Yes | FK to `visit_occurrence.visit_occurrence_id` |
| `visit_detail_id` | integer | Yes | Always NULL |
| `measurement_source_value` | string | No | Source test identifier |
| `measurement_source_concept_id` | integer | No | Always 0 |
| `unit_source_value` | string | Yes | Original unit string from source |
| `value_source_value` | string | Yes | Original result value from source |
| `measurement_id` | integer | No | Sequential identifier, 1--4,494,112 |
| `measurement_event_id` | integer | Yes | Always NULL |
| `meas_event_field_concept_id` | integer | Yes | Always NULL |

### Domain Breakdown

Measurements are distinguished by the prefix of `measurement_source_value`. The table below groups related source prefixes into clinical domains.

| Domain | Source Value Prefixes | Records | Description |
|--------|----------------------|--------:|-------------|
| **Vitals** | `STDWT`, `STDHT`, `STDTEMP`, `VSBPSYS`, `VSBPDIA`, `VSPULSE`, `VSRESP` | ~129,729 | Weight, height, temperature, blood pressure, pulse, respiration |
| **ECG** | `RR`, `QRS`, `QT`, `RATE`, `PR` | ~177,434 | Electrocardiogram intervals and heart rate |
| **Labs** | `RCT*`, `HMT*`, `UAT*`, `SRT*`, `SCT*`, `CLT*`, `ORT*`, `CGT*`, `CNT*`, `IMT*`, `GET*` | ~580,357 | Chemistry, hematology, urinalysis, and specialty lab panels |
| **Cognitive** | `PACC`, `MMSE`, `CDR` | ~157,434 | Core cognitive assessments |
| **Cognitive Extended** | `CFI`, `CFISP`, `COGDIGIT`, `COGFCSR`, `COGLOGIC` | ~189,070 | CFI, digit span, FCSR, logical memory |
| **Biomarkers** | `AB`, `ROCHE`, `PTAU217` | ~46,026 | Amyloid-beta, p-tau, NfL, GFAP |
| **Imaging** | `AMYLOID`, `TAU`, `MRI` | ~497,659 | Amyloid PET SUVR, tau PET SUVR, MRI volumes |
| **Imaging Extended** | `TAU_PETSURFER`, `TAU_STANFORD`, `FLAIR`, `MRI_READS`, `PET_VA`, `RETINAL` | ~209,149 | PetSurfer, Stanford tau, FLAIR, visual reads, retinal imaging |
| **CogState** | `COGSTATE` | 315,596 | CogState computerized cognitive tests |
| **CogState Battery** | `COGSTATE_BAT` | 55,524 | CogState battery composites (BPET/FNFT) |
| **CogState Questionnaires** | `cogstate_cpath`, `cogstate_macq` | ~55,224 | C-PATH functional, MACQ memory complaints |

### Measurement Source Value Format

The `measurement_source_value` column identifies the source test. Formats vary by domain:

| Domain | Format | Example |
|--------|--------|---------|
| Vitals | `field_name` | `STDWT` |
| ECG | `field_name` | `QT` |
| Labs | `test_code` | `RCT1` |
| Cognitive | `test:subtest` | `PACC:FCSRTFR` |
| CogState | `COGSTATE:task:metric` | `COGSTATE:DET:1` |
| Biomarkers | `analyte` | `AB` |
| Imaging | `modality:region` | `MRI:Hippocampus` |

### Unit Coverage

| `unit_concept_id` | Status | Records |
|-------------------:|--------|--------:|
| 0 | Not mapped or not applicable | ~45-70% (varies; mostly unitless: scores, ratios, z-scores) |
| Non-zero | Mapped to OMOP unit concept | ~30-55% (varies with item-level expansions across Rounds 1-5) |

Common mapped units include `8523` (mm), `8587` (mL), `8588` (mm3), `8753` (mg/dL), `8848` (pg/mL).

### Visit Linkage

| Status | Records | Percentage |
|--------|--------:|----------:|
| Linked to visit | ~3.52M | ~78% |
| No matching visit (NULL) | ~982K | ~22% |

Records with NULL `visit_occurrence_id` had no exact `BID`+`VISCODE` (or exact date, for imaging) match to a visit. There is no fuzzy/day-window matching; linkage is exact and happens at extraction time.

---

## observation.csv

Lifestyle data, family history, suicide risk screening (C-SSRS), study milestones, study partner information, and secondary questionnaires.

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `person_id` | integer | No | FK to `person.person_id` |
| `observation_concept_id` | integer | No | OMOP or custom concept ID |
| `observation_date` | date | No | Observation date (synthetic) |
| `observation_datetime` | datetime | Yes | Always NULL |
| `observation_type_concept_id` | integer | No | Always 32817 (EHR) |
| `value_as_number` | float | Yes | Numeric value |
| `value_as_string` | string | Yes | Text value |
| `value_as_concept_id` | integer | Yes | Concept ID for categorical values |
| `qualifier_concept_id` | integer | Yes | Qualifier concept |
| `unit_concept_id` | integer | No | OMOP unit concept (0 if not applicable) |
| `provider_id` | integer | Yes | Always NULL |
| `visit_occurrence_id` | float | Yes | FK to `visit_occurrence.visit_occurrence_id` |
| `visit_detail_id` | integer | Yes | Always NULL |
| `observation_source_value` | string | No | Source observation identifier |
| `observation_source_concept_id` | integer | No | Always 0 |
| `unit_source_value` | string | Yes | Original unit string |
| `qualifier_source_value` | string | Yes | Qualifier text |
| `observation_id` | integer | No | Sequential identifier |

### Domain Breakdown

| Domain | Source Value Prefix | Records | Description |
|--------|---------------------|--------:|-------------|
| **C-SSRS Lifetime** | `CSSRSLV` | 150,113 | Columbia Suicide Severity Rating Scale -- lifetime items |
| **Questionnaires** | `QUEST` | ~134,613 | GDS, STAI, ADL-PQ, AD Concerns (moved from MEASUREMENT) |
| **Habits** | `HABITS` | 84,335 | Smoking, alcohol, exercise, diet |
| **C-SSRS** | `CSSRS` | 58,674 | C-SSRS current assessments |
| **ADQS** | `ADQS` | ~32,876 | APOE genotype, treatment assignment, population flags |
| **RUIB** | `RUIB`, `RUIB1` | 29,140 | Resource Use in Brain Disorders |
| **Study Partner** | `SPINFO` | 22,607 | Study partner demographics and relationship |
| **FTP** | `FTP` | 17,450 | Future Time Perspective |
| **Milestones** | `DS` | 16,249 | Study disposition events (enrollment, discontinuation) |
| **RSS** | `RSS` | 14,174 | RSS questionnaire |
| **VIEWS** | `VIEWS` | 10,130 | VIEWS questionnaire |
| **Family History** | `FAMHX` | 5,379 | Family history of Alzheimer's and dementia |
| **IES** | `IES` | 4,336 | Impact of Event Scale |

### Observation Source Value Format

| Domain | Format | Example |
|--------|--------|---------|
| Lifestyle | `HABITS:field` | `HABITS:SMOKE` |
| Family History | `FAMHX:field` | `FAMHX:FATHDEM` |
| Milestones | `DS:event` | `DS:CONSENT` |
| C-SSRS | `CSSRS:item` | `CSSRS:SUICIDEATTEMPT` |
| Study Partner | `SPINFO:field` | `SPINFO:SPAGE` |
| Secondary | `QUESTIONNAIRE:field` | `FTP:FTP1` |
| ADQS | `ADQS:field:value` | `ADQS:APOEGN:E3E4`, `ADQS:TX:Solanezumab` |
| Questionnaires | `QUEST:source:field` | `QUEST:psychwell:GDTOTAL` |

---

## condition_occurrence.csv

Abnormal findings from physical and neurological examinations. Only findings coded as abnormal (source value = 2) in the `phyneuro` data are included.

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `condition_occurrence_id` | integer | No | Sequential identifier |
| `person_id` | integer | No | FK to `person.person_id` |
| `condition_concept_id` | integer | No | OMOP condition concept |
| `condition_start_date` | date | No | Date of finding (synthetic) |
| `condition_start_datetime` | datetime | Yes | Always NULL |
| `condition_end_date` | date | Yes | Always NULL |
| `condition_end_datetime` | datetime | Yes | Always NULL |
| `condition_type_concept_id` | integer | No | Always 32817 (EHR) |
| `condition_status_concept_id` | integer | No | Always 0 |
| `stop_reason` | string | Yes | Always NULL |
| `provider_id` | integer | Yes | Always NULL |
| `visit_occurrence_id` | float | Yes | FK to `visit_occurrence.visit_occurrence_id` |
| `visit_detail_id` | integer | Yes | Always NULL |
| `condition_source_value` | string | No | Format: `PHYNEURO:field_name` |
| `condition_source_concept_id` | integer | No | Always 0 |
| `condition_status_source_value` | string | No | Always `Abnormal` |

### Notes

- `condition_occurrence.csv` contains 7,391 abnormal phyneuro exam findings. SNOMED Clinical Finding concepts are appropriate for the Condition domain. Normal findings are dropped (OMOP convention: absence of disease is not a condition; exam completion is implicit from visit_occurrence and the DONE=1 filter on the source). PXEDSEV severity scores (ordinal 0-4) remain in `measurement.csv`.
- `condition_source_value` uses the format `PHYNEURO:field_name` (e.g., `PHYNEURO:PXMUSCUL` for musculoskeletal abnormality).
- Only exam fields where the source value equals 2 (abnormal) are included; normal findings are excluded.
- `condition_end_date` is always NULL because the source data records point-in-time findings without resolution dates.

---

## procedure_occurrence.csv

Imaging procedures deduplicated to one row per (person, procedure type, date). Standard OMOP CDM v5.4 PROCEDURE_OCCURRENCE table — referenced by `image_occurrence.procedure_occurrence_id` per the MI-CDM extension (Park & Jeon et al. 2024).

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `procedure_occurrence_id` | integer | No | Sequential identifier |
| `person_id` | integer | No | FK to `person.person_id` |
| `procedure_concept_id` | integer | No | Custom imaging procedure concept |
| `procedure_date` | date | No | Procedure date (synthetic) |
| `procedure_datetime` | datetime | Yes | Always NULL |
| `procedure_end_date` | date | Yes | Always NULL |
| `procedure_end_datetime` | datetime | Yes | Always NULL |
| `procedure_type_concept_id` | integer | No | Always 32817 (EHR) |
| `modifier_concept_id` | integer | No | Always 0 |
| `quantity` | integer | No | Always 1 |
| `provider_id` | integer | Yes | Always NULL |
| `visit_occurrence_id` | float | Yes | FK to `visit_occurrence.visit_occurrence_id` |
| `visit_detail_id` | integer | Yes | Always NULL |
| `procedure_source_value` | string | No | e.g., `MRI_BRAIN`, `PET_AMYLOID` |
| `procedure_source_concept_id` | integer | No | Always 0 |
| `modifier_source_value` | string | Yes | Always NULL |

### Procedure Concept Distribution

| `procedure_concept_id` | Label | Count |
|------------------------:|-------|------:|
| 2100000080 | MRI Brain | 7,296 |
| 2100000081 | PET Amyloid | 6,398 |
| 2100000082 | PET Tau | 6,074 |
| 2100000083 | Retinal Imaging | 539 |

### Notes

- Deduplicated from 358,679 raw imaging source records.
- Links to IMAGE_OCCURRENCE via `procedure_occurrence_id`.

---

## mi_cdm/image_occurrence.csv

MI-CDM extension table (Park et al. 2025). One row per DICOM series equivalent, identified by (person, modality, series_type, date). Contains synthetic DICOM UIDs since real DICOM metadata is unavailable.

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `image_occurrence_id` | integer | No | Sequential identifier |
| `person_id` | integer | No | FK to `person.person_id` |
| `procedure_occurrence_id` | float | Yes | FK to `procedure_occurrence.procedure_occurrence_id` |
| `visit_occurrence_id` | float | Yes | FK to `visit_occurrence.visit_occurrence_id` |
| `anatomic_site_concept_id` | integer | No | SNOMED body structure (4007117=Brain, 4103720=Eye) |
| `wadors_uri` | string | Yes | Always NULL (no PACS available) |
| `local_path` | string | Yes | Always NULL (no local DICOM files) |
| `image_occurrence_date` | date | No | Imaging date (synthetic) |
| `image_study_UID` | string | No | Synthetic DICOM Study UID (format: `2.25.{integer}`) |
| `image_series_UID` | string | No | Synthetic DICOM Series UID (format: `2.25.{integer}`) |
| `modality_concept_id` | integer | No | DICOM modality concept |

### Modality Distribution

| `modality_concept_id` | Label | Count |
|------------------------:|-------|------:|
| 2128009230 | MR (Magnetic resonance) | 11,539 |
| 2128009252 | PT (Positron emission tomography) | 12,110 |
| 2128009239 | OP (Ophthalmic photography) | 249 |

### Anatomic Site Distribution

| `anatomic_site_concept_id` | Label | Count |
|----------------------------:|-------|------:|
| 4007117 | Brain (SNOMED) | 23,649 |
| 4103720 | Eye (SNOMED) | 249 |

### Notes

- Synthetic DICOM UIDs use the `2.25.{integer}` format derived from MD5 hash of (BID, date, modality, series_type).
- 100% of rows are linked to a procedure_occurrence record.
- Multiple image_occurrences may share the same image_study_UID (same study, different series).

---

## mi_cdm/image_feature.csv

MI-CDM extension table (Park et al. 2025). Polymorphic bridge linking each imaging measurement to its source image_occurrence. Uses the OMOP event pattern: `image_feature_event_field_concept_id` identifies the target table's PK field (1147330 = measurement.measurement_id), and `image_feature_event_id` holds the actual measurement_id value.

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `image_feature_id` | integer | No | Sequential identifier |
| `person_id` | integer | No | FK to `person.person_id` |
| `image_occurrence_id` | integer | No | FK to `image_occurrence.image_occurrence_id` |
| `image_feature_event_field_concept_id` | integer | No | Always 1147330 (measurement.measurement_id) |
| `image_feature_event_id` | integer | No | Actual measurement_id value (polymorphic FK) |
| `image_feature_concept_id` | integer | No | LOINC/custom concept for the specific feature measured |
| `image_feature_type_concept_id` | integer | No | Always 32880 (Derived value) |
| `image_finding_concept_id` | integer | No | Grouping concept (e.g., brain_volume, amyloid_suvr) |
| `image_finding_id` | integer | No | Local grouping ID — related features share this value |
| `anatomic_site_concept_id` | integer | No | Body site (inherited from image_occurrence) |
| `alg_system` | string | No | Pipeline provenance URI |
| `alg_datetime` | datetime | Yes | Always NULL (processing date unknown) |

### Pipeline Distribution (alg_system)

| `alg_system` | Pipeline | Count |
|--------------|----------|------:|
| `urn:a4:pipeline:suvr_tau` | Tau PET SUVR (standard) | 263,808 |
| `urn:a4:pipeline:petsurfer` | Tau PET PetSurfer | 107,690 |
| `urn:a4:pipeline:volumetric_mri` | MRI volumetrics | 100,893 |
| `urn:a4:pipeline:stanford` | Tau PET Stanford | 71,045 |
| `urn:a4:pipeline:suvr_amyloid` | Amyloid PET SUVR | 62,775 |
| `urn:a4:pipeline:mri_reads` | MRI radiological reads | 41,052 |
| `urn:a4:pipeline:flair_wmh` | FLAIR WMH quantification | 18,067 |
| `urn:a4:pipeline:retinal_ai` | Retinal imaging | 5,086 |
| `urn:a4:pipeline:pet_visual_assessment` | PET visual assessment | 5,274 |

### Finding Concept Distribution

| `image_finding_concept_id` | Finding | Count |
|----------------------------:|---------|------:|
| 2100000095 | Tau PET SUVR | 442,543 |
| 2100000093 | Brain volumetric measurement | 100,893 |
| 2100000094 | Amyloid PET SUVR | 62,775 |
| 2100000096 | MRI radiological read | 41,052 |
| 2100000097 | FLAIR lesion volume | 18,067 |
| 2100000098 | Retinal imaging measurement | 5,086 |
| 2100000099 | PET visual assessment | 5,274 |

### Notes

- Every `image_feature_event_id` references a valid `measurement.measurement_id`.
- Every `image_occurrence_id` references a valid `image_occurrence.image_occurrence_id`.
- For tau PET, one physical scan generates features from up to 3 pipelines (suvr_tau, petsurfer, stanford) — all sharing the same image_occurrence but with distinct `alg_system` URNs.
- The `image_finding_id` groups related measurements from the same analysis (e.g., all FreeSurfer regions from one MRI scan).

---

## date_anchor.csv

Utility table documenting the date de-identification offsets applied to each subject. This is **not** a standard OMOP CDM table. It is included to support data lineage verification and date arithmetic when comparing against source data.

### Column Schema

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `BID` | string | No | Blinded subject ID (matches `person.person_source_value`) |
| `offset_days` | integer | No | Days added to 2020-01-01 to create synthetic consent date (range: 0--364) |
| `synthetic_consent_date` | date | No | 2020-01-01 + `offset_days` (range: 2020-01-01 to 2020-12-30) |

### Notes

- The offset is deterministic: it is derived from the MD5 hash of the BID, so re-running the pipeline produces identical offsets.
- All dates in every output file are computed as: `synthetic_consent_date + days_from_consent` (where `days_from_consent` comes from the source data).
- This table is the key to understanding how output dates relate to the original relative time offsets in the source data.

---

## Date Handling

All source dates in the A4/LEARN dataset are recorded as **days from consent** (e.g., `VITALS_DAYS_CONSENT = 180` means 180 days after the subject's consent date). The ETL converts these relative offsets into synthetic absolute dates using the following procedure:

1. **Generate offset**: Compute `MD5(BID)`, convert the first 8 hex characters to an integer, and take modulo 365. This yields a deterministic offset in the range 0--364.
2. **Compute synthetic consent date**: `2020-01-01 + offset_days`.
3. **Compute event dates**: `synthetic_consent_date + days_from_consent`.

**Implications for analysis**:

- Calendar dates in the output are **not real dates**. Do not interpret them as actual calendar dates.
- **Within-subject** temporal intervals (e.g., days between visits, time on treatment) are preserved exactly.
- **Between-subject** date comparisons are **not meaningful** because each subject has a different random offset.
- To recover the original relative timeline, subtract the subject's `synthetic_consent_date` from any event date.

---

## Joining Tables

All tables link through `person_id` (subject level) and `visit_occurrence_id` (visit level). The following pandas examples demonstrate common query patterns.

### Get all measurements for a specific person

```python
import pandas as pd

person = pd.read_csv('OMOP_Output/person.csv')
measurement = pd.read_csv('OMOP_Output/measurement.csv', low_memory=False)

# All measurements for person_id=1
person_1_meas = measurement[measurement['person_id'] == 1]
```

### Link measurements to their visit dates

```python
visit = pd.read_csv('OMOP_Output/visit_occurrence.csv')
measurement = pd.read_csv('OMOP_Output/measurement.csv', low_memory=False)

meas_with_visits = measurement.merge(
    visit[['visit_occurrence_id', 'visit_start_date', 'visit_source_value']],
    on='visit_occurrence_id',
    how='left'
)
```

### Filter measurements by clinical domain

```python
# Cognitive test scores (PACC composite and subtests)
cognitive = measurement[
    measurement['measurement_source_value'].str.startswith('PACC:')
]

# All lab results (source values starting with RCT, HMT, UAT, etc.)
labs = measurement[
    measurement['measurement_source_value'].str.match(r'^(RCT|HMT|UAT|SRT|SCT|CLT)')
]

# Amyloid PET imaging
amyloid_pet = measurement[
    measurement['measurement_source_value'].str.startswith('AMYLOID')
]
```

### Get observations for screening visits

```python
visit = pd.read_csv('OMOP_Output/visit_occurrence.csv')
observation = pd.read_csv('OMOP_Output/observation.csv', low_memory=False)

screening_visits = visit[visit['visit_source_value'].str.endswith('_001')]
screening_obs = observation.merge(
    screening_visits[['visit_occurrence_id']],
    on='visit_occurrence_id'
)
```

### Build a longitudinal drug exposure timeline

```python
drug = pd.read_csv('OMOP_Output/drug_exposure.csv')

# Count infusions per subject
infusions_per_person = drug.groupby('person_id').agg(
    n_infusions=('drug_exposure_id', 'count'),
    first_dose=('drug_exposure_start_date', 'min'),
    last_dose=('drug_exposure_start_date', 'max')
).reset_index()
```

### Combine person demographics with measurements

```python
person = pd.read_csv('OMOP_Output/person.csv')
measurement = pd.read_csv('OMOP_Output/measurement.csv', low_memory=False)

# MMSE scores with demographics
mmse = measurement[measurement['measurement_source_value'] == 'MMSE']
mmse_with_demo = mmse.merge(
    person[['person_id', 'year_of_birth', 'gender_concept_id', 'race_concept_id']],
    on='person_id'
)
```

---

## Data Quality Notes

### NULL and Placeholder Values

| Column Pattern | Value | Meaning |
|---------------|-------|---------|
| `*_datetime` columns | NULL | Datetime precision not available; use the corresponding `*_date` column |
| `concept_id = 0` | 0 | Source value could not be mapped to a standard OMOP concept |
| `unit_concept_id = 0` | 0 | Unit not mapped or not applicable to this measurement type |
| `visit_occurrence_id = NULL` | NULL | No exact `BID`+`VISCODE`/date match to a visit (subject-level or date-only sources) |
| `provider_id`, `care_site_id`, `location_id` | NULL | Not captured in the source data |

### Coverage Statistics

| Metric | Value |
|--------|------:|
| Subjects with observation periods | 6,945 / 6,945 (100%) |
| Drug exposures linked to visits | 74,775 / 74,777 (99.997%) |
| Measurements linked to visits | ~78% (exact `BID`+`VISCODE`/date match) |
| Measurements with mapped units | ~30-55% (many unitless: scores, ratios; verified by postprocessing.map_unit_concepts) |

### Known Limitations

- **Datetime precision**: All `*_datetime` and `*_time` columns are NULL. Only date-level precision is available from the source data.
- **Unit mapping gaps**: 45.2% of measurements have `unit_concept_id = 0`. This occurs primarily for dimensionless scores (cognitive tests), ordinal scales, and non-UCUM units like SUVR, z-score, and score.
- **Visit linkage gaps**: ~22% of measurements have NULL `visit_occurrence_id`. Linkage is exact (`BID`+`VISCODE`, or exact date for imaging); records with no matching VISCODE/date — subject-level derived values, date-only imaging, etc. — are left unlinked. No fuzzy/day-window matching is performed.
- **Multi-racial coding**: Subjects with multiple race values in the source receive `race_concept_id = 0` (standard OMOP practice when a single concept cannot represent the data).
- **Custom concepts**: Drug concepts (2000000001--2000000003) and many measurement/observation concepts (2100000001+) are study-specific custom concepts not found in the OMOP Standardized Vocabularies. These require a local concept table for full resolution.
- **Synthetic dates**: All dates are offset from 2020-01-01. Cross-subject date comparisons are not meaningful. Within-subject temporal intervals are accurate.

---

## OMOP Concept Quick Reference

Frequently used concept IDs across all output files.

### Standard Type Concepts

| Concept ID | Concept Name | Used In |
|-----------:|-------------|---------|
| 32817 | EHR | `*_type_concept_id` in all clinical tables |
| 32838 | EHR dispensing record | `drug_type_concept_id` |

### Gender Concepts

| Concept ID | Label |
|-----------:|-------|
| 8507 | Male |
| 8532 | Female |

### Race Concepts

| Concept ID | Label |
|-----------:|-------|
| 8515 | Asian |
| 8516 | Black or African American |
| 8527 | White |
| 8557 | Native Hawaiian or Other Pacific Islander |
| 8657 | American Indian or Alaska Native |
| 0 | Unknown / Multi-racial |

### Ethnicity Concepts

| Concept ID | Label |
|-----------:|-------|
| 38003563 | Hispanic or Latino |
| 38003564 | Not Hispanic or Latino |
| 0 | Unknown |

### Visit Concepts

| Concept ID | Label | Usage |
|-----------:|-------|-------|
| 32035 | Visit derived from EHR encounter record | Screening, baseline visits |
| 32036 | Visit derived from EHR order | Treatment, infusion, unscheduled visits |
| 32220 | Other visit type | Uncategorized visit types |

### Drug Concepts (Custom)

| Concept ID | Label | Route |
|-----------:|-------|-------|
| 2000000001 | Solanezumab 400 mg | 4171047 (Intravenous) |
| 2000000002 | Solanezumab 800 mg | 4171047 (Intravenous) |
| 2000000003 | Solanezumab 1600 mg | 4171047 (Intravenous) |

### Common Unit Concepts

| Concept ID | Unit | Typical Domain |
|-----------:|------|---------------|
| 8523 | mm | Imaging (cortical thickness) |
| 8529 | kg | Vitals (weight) |
| 8582 | cm | Vitals (height) |
| 8587 | mL | Imaging (volumes) |
| 8588 | mm3 | Imaging (regional volumes) |
| 8645 | mg/L | Biomarkers |
| 8713 | mg/dL | Labs (chemistry) |
| 8749 | pg/mL | Biomarkers |
| 8753 | mg/dL | Labs |
| 8848 | pg/mL | Biomarkers (tau, NfL) |
| 8876 | mmol/L | Labs |
| 9529 | kg | Vitals (weight) |

### MI-CDM Extension Concepts

**Imaging Procedure Concepts (Custom)**

| Concept ID | Label |
|-----------:|-------|
| 2100000080 | MRI Brain |
| 2100000081 | PET Amyloid |
| 2100000082 | PET Tau |
| 2100000083 | Retinal Imaging |

**DICOM Modality Concepts (Standard, DICOM vocabulary)**

| Concept ID | Label | Source |
|-----------:|-------|--------|
| 2128009230 | MR (Magnetic resonance) | DICOM2OMOP / Park et al. 2025 |
| 2128009252 | PT (Positron emission tomography) | DICOM2OMOP / Park et al. 2025 |
| 2128009239 | OP (Ophthalmic photography) | DICOM2OMOP / Park et al. 2025 |

**Image Finding Concepts (Custom)**

| Concept ID | Label |
|-----------:|-------|
| 2100000093 | Brain volumetric measurement |
| 2100000094 | Amyloid PET SUVR |
| 2100000095 | Tau PET SUVR |
| 2100000096 | MRI radiological read |
| 2100000097 | FLAIR lesion volume |
| 2100000098 | Retinal imaging measurement |
| 2100000099 | PET visual assessment |

**Standard MI-CDM Concepts**

| Concept ID | Label | Usage |
|-----------:|-------|-------|
| 1147330 | measurement.measurement_id | `image_feature_event_field_concept_id` (polymorphic FK target) |
| 32880 | Derived value | `image_feature_type_concept_id` (algorithm-derived) |

---

## Related Documentation

- **Data Mapping Guide**: `A4_OMOP_ETL_Data_Mapping_Guide.md` -- detailed field-by-field source-to-OMOP mappings
- **Concept Maps**: `concept_maps/*.csv` -- all concept mapping tables (viewable in Excel)
- **Data Dictionaries**: `Documents/Data Dictionaries/*.csv` -- source field definitions
- **Clinical Methods**: `Documents/Methods/*.pdf` -- assay and imaging protocols
