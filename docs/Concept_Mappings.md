# A4/LEARN OMOP ETL -- Concept Mappings Reference

This document describes every OMOP concept mapping used in the A4/LEARN ETL pipeline. It is intended for collaborators and reviewers who need to audit, verify, or modify the mappings that translate raw clinical trial data into OMOP CDM v5.4 format.

**Pipeline version**: Modular package (`a4_omop_etl/`)
**Target CDM**: OMOP CDM v5.4
**Custom vocabulary ID**: `A4_LEARN`

---

## Table of Contents

1. [How Concept Mapping Works](#how-concept-mapping-works)
2. [Concept Map Files at a Glance](#concept-map-files-at-a-glance)
3. [Demographics (demographics.csv)](#1-demographics)
4. [Visits (visits.csv)](#2-visits)
5. [Drugs (drugs.csv)](#3-drugs)
6. [Units (units.csv)](#4-units)
7. [Vitals (vitals.csv)](#5-vitals)
8. [Labs (labs.csv)](#6-labs)
9. [ECG (ecg.csv)](#7-ecg)
10. [Cognitive Assessments (cognitive.csv)](#8-cognitive-assessments)
11. [CogState (cogstate.csv)](#9-cogstate)
12. [Biomarkers (biomarkers.csv)](#10-biomarkers)
13. [Imaging (imaging.csv)](#11-imaging)
14. [Observations (observations.csv)](#12-observations)
15. [Conditions (conditions.csv)](#13-conditions)
16. [Milestones (milestones.csv)](#14-milestones)
17. [C-SSRS (cssrs.csv)](#15-c-ssrs)
18. [C-SSRS Lifetime Columns (cssrslv_columns.csv)](#16-c-ssrs-lifetime-columns)
19. [Questionnaires (questionnaires.csv)](#17-questionnaires)
20. [ADQS (adqs.csv)](#18-adqs)
21. [Procedures (procedures.csv)](#19-procedures)
22. [Modalities (modalities.csv)](#20-modalities)
23. [Image Feature Types (image_feature_types.csv)](#21-image-feature-types)
24. [Image Findings (image_findings.csv)](#22-image-findings)
25. [Custom Concept ID Ranges](#custom-concept-id-ranges)
26. [Custom Concepts Registry](#custom-concepts-registry)
27. [Unit Concept Mapping in Post-Processing](#unit-concept-mapping-in-post-processing)
28. [How to Review or Edit Mappings](#how-to-review-or-edit-mappings)

---

## How Concept Mapping Works

The pipeline stores all source-to-OMOP concept mappings in plain CSV files rather than in Python code. This separation gives domain experts a way to review and edit mappings in a spreadsheet application without touching the ETL source.

### Architecture

```
concept_maps/                   a4_omop_etl/concepts.py       Domain modules
 22 CSV files                    Loader functions              (person.py, measurement_*.py, ...)
 +-----------------+             +-------------------+         +---------------------+
 | demographics.csv| --read by-> | load_gender_      | -used-> | person.py           |
 | visits.csv      | --read by-> |   concepts()      |         | visit.py            |
 | labs.csv         | --read by-> | load_lab_concepts | -used-> | measurement_        |
 | ...             |             | ...               |         |   clinical.py       |
 +-----------------+             +-------------------+         +---------------------+
```

**Step by step:**

1. Each CSV file in `concept_maps/` contains rows that map a source code to an OMOP `concept_id`, along with the concept name and any relevant metadata (units, grouping, notes).
2. The `a4_omop_etl/concepts.py` module provides a loader function for each CSV. These functions read the CSV at runtime and return Python dictionaries.
3. Domain modules (`person.py`, `measurement_clinical.py`, `observation.py`, and so on) call the appropriate loader and use the returned dictionary to assign concept IDs during transformation.
4. Post-processing in `postprocessing.py` applies the unit concept map across all measurement records.

### Loader patterns

The `concepts.py` module uses two loading patterns.

**Simple key-value loaders** return `{source_code: concept_id}` dictionaries. Examples: `load_gender_concepts()`, `load_lab_concepts()`, `load_visit_concepts()`.

```python
# Example return value from load_lab_concepts()
{
    "HMT1": 3000963,   # Hemoglobin
    "HMT2": 3009542,   # Hematocrit
    ...
}
```

**Dict-of-dicts loaders** return `{source_code: {concept_id, name, unit, ...}}` dictionaries. These are used when the domain module needs the concept name or unit alongside the ID. Examples: `load_vitals_concepts()`, `load_biomarker_concepts()`.

```python
# Example return value from load_vitals_concepts()
{
    "STDWT": {"concept_id": 3025315, "name": "Body weight",
              "unit": "kg", "unit_concept_id": 9529},
    ...
}
```

Some CSVs contain a `group` column that subdivides entries (for example, `core` vs. `extended` cognitive tests). The loaders accept an optional `group_filter` parameter so that different pipeline phases can load the subset they need.

---

## Concept Map Files at a Glance

| # | File | Entries | Columns | OMOP Domain | Standard Vocabulary |
|---|------|---------|---------|-------------|---------------------|
| 1 | `demographics.csv` | 12 | category, source_code, concept_id, concept_name, notes | Person | OMOP Gender/Race/Ethnicity (SNOMED/LOINC) |
| 2 | `visits.csv` | 6 | source_code, concept_id, concept_name, notes | Visit | OMOP Visit |
| 3 | `drugs.csv` | 3 | source_code, concept_id, concept_name, notes | Drug | RxNorm Extension (Solanezumab) |
| 4 | `units.csv` | 43 | unit_source_value, unit_concept_id, notes | Measurement | UCUM |
| 5 | `vitals.csv` | 7 | source_code, concept_id, concept_name, unit, unit_concept_id, notes | Measurement | LOINC (all Athena-verified) |
| 6 | `labs.csv` | 96 | source_code, concept_id, concept_name, notes | Measurement | LOINC / SNOMED / A4_LEARN customs |
| 7 | `ecg.csv` | 5 | source_code, concept_id, concept_name, unit, notes | Measurement | LOINC / SNOMED |
| 8 | `cognitive.csv` | 54 | source_code, concept_id, concept_name, unit, group, notes | Measurement | CDISC (most items) / LOINC / SNOMED / A4_LEARN |
| 9 | `cogstate.csv` | 63 | source_code, concept_id, concept_name, unit, group, notes | Measurement | A4_LEARN (CogState is proprietary) |
| 10 | `biomarkers.csv` | 20 | source_code, concept_id, concept_name, unit, notes | Measurement | LOINC (GFAP/NFL/PTAU/APOE) / A4_LEARN customs (Abeta forms) |
| 11 | `imaging.csv` | 13 | source_code, concept_id, concept_name, unit, group, notes | Measurement | A4_LEARN (FreeSurfer regions, algorithm-derived) |
| 12 | `observations.csv` | 16 | source_code, concept_id, concept_name, group, notes | Observation | SNOMED / LOINC / A4_LEARN |
| 13 | `conditions.csv` | 17 | source_code, concept_id, concept_name, group, notes | Condition | SNOMED (phyneuro findings) |
| 14 | `milestones.csv` | 15 | source_code, concept_id, concept_name, notes | Observation | LOINC / SNOMED / A4_LEARN |
| 15 | `cssrs.csv` | 29 | source_code, concept_id, concept_name, category, notes | Observation | LOINC (1001xxx) + A4_LEARN customs |
| 16 | `cssrslv_columns.csv` | 15 | lifetime_column, standard_key, notes | (column alias) | N/A |
| 17 | `questionnaires.csv` | 99 | source_code, concept_id, concept_name, unit, group, notes | Measurement / Observation | LOINC (IES, GDS, STAI, ADL items via CDISC) / A4_LEARN |
| 18 | `adqs.csv` | 28 | source_code, concept_id, concept_name, domain, value_as_concept_id, notes | Measurement / Observation | LOINC (APOE, education) / SNOMED (BMI, retirement) / A4_LEARN (TX) |
| 19 | `procedures.csv` | 4 | source_code, concept_id, concept_name, notes | Procedure | LOINC / SNOMED (Athena-verified standards) |
| 20 | `modalities.csv` | 3 | source_code, concept_id, concept_name, notes | (MI-CDM) | DICOM (DICOM2OMOP standard, Park & Jeon 2024) |
| 21 | `image_feature_types.csv` | 2 | source_code, concept_id, concept_name, notes | (MI-CDM) | OMOP Type Concept |
| 22 | `image_findings.csv` | 7 | source_code, concept_id, concept_name, notes | (MI-CDM) | A4_LEARN (custom) |

---

## 1. Demographics

**File**: `concept_maps/demographics.csv`
**Loader**: `load_gender_concepts()`, `load_race_concepts()`, `load_ethnicity_concepts()`
**Consumer**: `person.py`
**Entries**: 13

The `category` column subdivides this file into three logical groups. Each loader filters on the category it needs.

### Gender

| source_code | concept_id | concept_name | Source Field |
|-------------|-----------|--------------|-------------|
| 1 | 8532 | Female | SUBJINFO: SEX=1 |
| 2 | 8507 | Male | SUBJINFO: SEX=2 |

### Race

| source_code | concept_id | concept_name |
|-------------|-----------|--------------|
| 1 | 8527 | White |
| 2 | 8516 | Black or African American |
| 58 | 8515 | Asian |
| 79 | 8557 | Native Hawaiian or Other Pacific Islander |
| 84 | 8657 | American Indian or Alaska Native |
| 97 | 0 | Unknown |
| 100 | 0 | More than one race |

Race codes 97 (Unknown) and 100 (More than one race) map to concept_id `0`, meaning no standard concept is assigned.

### Ethnicity

| source_code | concept_id | concept_name |
|-------------|-----------|--------------|
| 50 | 38003563 | Hispanic or Latino |
| 56 | 38003564 | Not Hispanic or Latino |
| 97 | 0 | Unknown |

---

## 2. Visits

**File**: `concept_maps/visits.csv`
**Loader**: `load_visit_concepts()`
**Consumer**: `visit.py`
**Entries**: 6

| source_code | concept_id | concept_name |
|-------------|-----------|--------------|
| screening | 32035 | Visit derived from EHR |
| baseline | 32035 | Visit derived from EHR |
| clinic | 32035 | Visit derived from EHR |
| infusion | 32036 | Drug administration visit |
| unscheduled | 32220 | Urgent care visit |
| default | 32035 | Default |

The `default` row is a fallback applied when a visit type cannot be classified into one of the other categories.

---

## 3. Drugs

**File**: `concept_maps/drugs.csv`
**Loader**: `load_drug_concepts()`
**Consumer**: `drug_exposure.py`
**Entries**: 3

| source_code (dose mg) | concept_id | concept_name |
|------------------------|-----------|--------------|
| 400 | 2000000001 | Solanezumab 400mg IV infusion |
| 800 | 2000000002 | Solanezumab 800mg IV infusion |
| 1600 | 2000000003 | Solanezumab 1600mg IV infusion |

All three concepts are custom (`A4_LEARN` vocabulary). Solanezumab is an investigational anti-amyloid monoclonal antibody; no standard OMOP drug concept exists for the study-specific dose formulations.

---

## 4. Units

**File**: `concept_maps/units.csv`
**Loader**: `load_unit_concept_map()`
**Consumer**: `postprocessing.py` (applied globally after all measurement records are built)
**Entries**: 43

This file maps unit strings found in measurement records to OMOP `unit_concept_id` values based on the UCUM standard.

### Standard units (mapped to non-zero concept IDs)

| unit_source_value | unit_concept_id | Description |
|-------------------|----------------|-------------|
| mmHg | 8876 | Blood pressure |
| beats/min | 8541 | Heart/pulse rate |
| breaths/min | 8483 | Respiratory rate |
| Cel | 586323 | Celsius temperature |
| kg | 9529 | Kilograms |
| cm | 8582 | Centimeters |
| mL | 8587 | Milliliters |
| msec | 8588 | Milliseconds |
| mmol/L | 8753 | Millimoles per liter |
| GI/L | 8848 | 10^9/L (billion per liter) |
| U/L | 8645 | Units per liter |
| umol/L | 8749 | Micromoles per liter |
| g/L | 8713 | Grams per liter |
| pg/mL | 8845 | Picograms per milliliter |
| ng/L | 8725 | Nanograms per liter |
| ratio | 8523 | Ratio (dimensionless) |
| % | 8554 | Percent |
| mg/dL | 8840 | Milligrams per deciliter |
| mEq/L | 9557 | Milliequivalents per liter |
| fL | 8583 | Femtoliter |
| pg | 8564 | Picogram |
| g/dL | 8713 | Grams per deciliter |
| mg/L | 8751 | Milligrams per liter |
| ng/mL | 8842 | Nanograms per milliliter |
| NG/ML | 8842 | Case variant of ng/mL |
| PG/ML | 8845 | Case variant of pg/mL |
| UG/ML | 8859 | Micrograms per milliliter |
| U/mL | 8763 | Units per milliliter |
| Ratio | 8523 | Case variant of ratio |
| TI/L | 8848 | Tera per liter (10^12/L) |
| sec | 8555 | Seconds |
| IU/mL | 8985 | International units per milliliter |

### Non-standard units (mapped to concept_id 0)

The following unit strings appear in source data but have no standard UCUM equivalent. They are mapped to `0` to indicate "no matching standard unit."

| unit_source_value | Notes |
|-------------------|-------|
| TITER | Titer is a ratio with no standard unit |
| 0 | Invalid unit source value |
| score | Non-standard (cognitive test scores) |
| z-score | Non-standard (composite z-scores) |
| SUVR | Standardized Uptake Value Ratio (PET imaging) |
| log10(ms) | CogState reaction time transform |
| arcsine(sqrt(proportion)) | CogState accuracy transform |
| NO UNITS | Explicit no-unit marker |
| B/M | Bound/free marker ratio |
| count | Non-standard count |
| binary | Binary 0/1 indicator |

### Case sensitivity note

Several entries exist specifically to handle case variants in source data (for example, both `ng/mL` and `NG/ML` map to `8842`). When adding new unit mappings, check whether a case variant already exists.

---

## 5. Vitals

**File**: `concept_maps/vitals.csv`
**Loader**: `load_vitals_concepts()`
**Consumer**: `measurement_clinical.py`
**Entries**: 7

| source_code | concept_id | concept_name | unit | unit_concept_id |
|-------------|-----------|--------------|------|----------------|
| STDWT | 3025315 | Body weight | kg | 9529 |
| STDHT | 3036277 | Body height | cm | 8582 |
| VSBPSYS | 3004249 | Systolic BP | mmHg | 8876 |
| VSBPDIA | 3012888 | Diastolic BP | mmHg | 8876 |
| VSPULSE | 3027018 | Heart rate | beats/min | 8541 |
| VSRESP | 3024171 | Respiratory rate | breaths/min | 8541 |
| STDTEMP | 3020891 | Body temperature | Cel | 586323 |

All vitals concepts are standard LOINC measurements. This file also carries the `unit_concept_id` column so that vitals records receive their unit mapping at creation time rather than during post-processing.

---

## 6. Labs

**File**: `concept_maps/labs.csv`
**Loader**: `load_lab_concepts()`
**Consumer**: `measurement_clinical.py`
**Entries**: 96

This is the largest concept map in the pipeline. It covers hematology, chemistry, urinalysis, coagulation, serology, immunology, genetics, and drug-specific biomarkers. The loader returns a simple `{source_code: concept_id}` dictionary.

### Hematology (HMT codes)

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| HMT1 | 3000963 | Hemoglobin | LOINC 718-7 |
| HMT2 | 3009542 | Hematocrit | LOINC 4544-3 |
| HMT3 | 3020416 | RBC | LOINC 789-8 |
| HMT4 | 3010813 | WBC | LOINC 6690-2 |
| HMT7 | 3010813 | WBC | Duplicate code |
| HMT13 | 3024929 | Platelets | LOINC 777-3 |
| HMT40 | 3000963 | Hemoglobin | Duplicate code |
| HMT102 | 3009744 | MCHC | LOINC 786-4 |
| HMT8 | 3017732 | Neutrophils | LOINC 751-8 |
| HMT9 | 3004327 | Lymphocytes | LOINC 731-0 |
| HMT10 | 3001604 | Monocytes | LOINC 742-7 |
| HMT11 | 3013115 | Eosinophils | LOINC 711-2 |
| HMT12 | 3006315 | Basophils | LOINC 704-7 |
| HMT20 | 3004809 | Band neutrophils | LOINC 764-1 |
| HMT71 | 2100000401 | RBC Morphology | Custom |
| HMT71_1 through HMT71_5 | 2100000401 | RBC Morphology | Repeat specimens |
| HMT95 | 3013498 | Atypical/Variant lymphocytes | LOINC 733-6 |
| HMT98 | 37173288 | Nucleated RBC count | SNOMED |
| HMT370 | 3004410 | Hemoglobin A1c | LOINC 4548-4 |

### Chemistry (RCT codes)

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| RCT1 | 3024128 | Total Bilirubin | LOINC 1975-2 |
| RCT3 | 3004077 | GGT | LOINC 2324-2 |
| RCT4 | 3006923 | ALT/SGPT | LOINC 1742-6 |
| RCT5 | 3013721 | AST | LOINC 1920-8 |
| RCT6 | 3013682 | BUN | LOINC 3094-0 |
| RCT8 | 3037556 | Uric Acid/Urate | LOINC 3084-1 |
| RCT9 | 2100000400 | Phosphorus | Custom (API lookup failed) |
| RCT12 | 3020630 | Total Protein | LOINC 2885-2 |
| RCT13 | 3024561 | Albumin | LOINC 1751-7 |
| RCT14 | 3019550 | CK | LOINC 2157-6 |
| RCT15 | 3019550 | Sodium | LOINC 2951-2 |
| RCT16 | 3023103 | Potassium | LOINC 2823-3 |
| RCT18 | 3014576 | Chloride | LOINC 2075-0 |
| RCT20 | 3027114 | Cholesterol | LOINC 2093-3 |
| RCT29 | 3027597 | Direct Bilirubin | LOINC 1968-7 |
| RCT142 | 3004501 | Fasting Glucose | LOINC 2345-7 |
| RCT183 | 3006906 | Calcium | LOINC 17861-6 |
| RCT392 | 3016723 | Creatinine | LOINC 2160-0 |
| RCT1407 | 3035995 | Alkaline Phosphatase | LOINC 6768-6 |
| RCT1669 | 3004501 | Random Glucose | LOINC 2345-7 |

### Urinalysis (UAT codes)

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| UAT1 | 3027162 | Urine Color | LOINC 5778-6 |
| UAT2 | 3033543 | Urine Specific Gravity | LOINC 5811-5 |
| UAT3 | 3015736 | Urine pH | LOINC 5803-2 |
| UAT5 | 3009261 | Urine Glucose | LOINC 5792-7 |
| UAT6 | 3016436 | Urine Ketones | LOINC 5797-6 |
| UAT11 | 3010156 | Urine Leukocyte Esterase | LOINC 5799-2 |
| UAT13 | 3007876 | Urine Clarity/Appearance | LOINC 5767-9 |
| UAT43 | 3020891 | Urine Blood | LOINC 5794-3 |
| UAT49 | 3014051 | Urine Protein | LOINC 5804-0 |

### Coagulation (CGT codes)

| source_code | concept_id | concept_name |
|-------------|-----------|--------------|
| CGT283 | 3034426 | Prothrombin Time PT |
| CGT564 | 3022217 | INR |

### Serology and Infectious Disease (CNT, ORT, SCT, IMT codes)

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| SCT1528 | 3010156 | CRP high sensitivity | LOINC 30522-7 |
| SCT2356 | 3012336 | Haptoglobin | LOINC 4542-7 |
| CNT63 | 4014007 | Hepatitis B Surface Antigen | SNOMED |
| CNT68 | 42537336 | Hepatitis B Core Antibody | SNOMED |
| CNT69 | 4196134 | Hepatitis C Antibody | SNOMED |
| CNT70 | 37394378 | Hepatitis A IgM Antibody | SNOMED |
| CNT73 | 37392817 | Hepatitis A Total Antibody | SNOMED |
| CNT350 | 4196134 | Hepatitis C Antibody | Duplicate |
| CNT353 | 4278658 | Hepatitis B Surface Antibody | SNOMED |
| CNT550 | 4014007 | Hepatitis B Surface Antigen II | Duplicate |
| ORT7923 | 4295162 | Hepatitis E IgG | SNOMED |
| ORT7924 | 4268445 | Hepatitis E IgM | SNOMED |
| ORT11357 | 4295162 | Hepatitis E IgG | Duplicate |
| ORT11358 | 4268445 | Hepatitis E IgM | Duplicate |
| IMT1669 | 37173542 | ANA | SNOMED |
| IMT1669_1 through IMT1669_3 | 37173542 | ANA | Repeat specimens |
| IMT1754 | 4217559 | Anti-Smooth Muscle Ab IgG | SNOMED |

### Genetics

| source_code | concept_id | concept_name |
|-------------|-----------|--------------|
| CLT1878 | 3029139 | APOE genotype |

### Drug-Specific and Specialized Biomarkers (custom concepts in labs.csv)

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| ROCHE: | 2100000500 | Roche biomarker panel category marker | Custom |
| SRT20477 | 2100000501 | Anti-Solanezumab antibody level | Custom |
| SRT16102 | 2100000502 | Solanezumab plasma concentration | Custom |
| SRT21423 | 2100000503 | Anti-Solanezumab neutralizing antibody | Custom |
| SRT20478 | 2100000504 | Anti-Solanezumab antibody titer | Custom |
| ORT13169 | 2100000505 | Solanezumab CSF concentration | Custom |
| AB:FP40/TP40 | 2100000510 | Free/Total plasma Abeta-40 ratio | Custom |
| AB:FP42/FP40 | 2100000511 | Free plasma Abeta-42/40 ratio | Custom |
| AB:FP42/TP42 | 2100000512 | Free/Total plasma Abeta-42 ratio | Custom |
| SRT15753 | 2100000520 | CSF modified Abeta-40 | Custom |
| SRT15754 | 2100000521 | CSF modified Abeta-42 | Custom |
| SRT10631 | 43055225 | CSF pTau-181 | LOINC standard |
| SRT10630 | 2100000523 | CSF total Tau | Custom |
| SRT18142 | 2100000524 | CSF free Abeta-40 | Custom |
| SRT18047 | 2100000525 | CSF free Abeta-42 | Custom |
| ORT11360 | 2100000530 | Hep E IgG/IgM interpretation | Custom |
| ORT11360_1 through ORT11360_5 | 2100000530 | Hep E interpretation | Repeat specimens |
| GET1881 | 2100000531 | HCV RNA viral load | Custom |

### Duplicate codes

Several source codes map to the same concept because the A4/LEARN data dictionary assigns different codes to repeated specimens or re-runs of the same assay. These are called out in the `notes` column of the CSV. For example, HMT4 and HMT7 both map to WBC (3010813).

---

## 7. ECG

**File**: `concept_maps/ecg.csv`
**Loader**: `load_ecg_concepts()`
**Consumer**: `measurement_clinical.py`
**Entries**: 5

| source_code | concept_id | concept_name | unit | Vocabulary |
|-------------|-----------|--------------|------|------------|
| RATE | 3027018 | Heart rate | beats/min | LOINC |
| QT | 4116637 | QT interval duration | ms | SNOMED |
| QRS | 3022022 | QRS duration | ms | LOINC |
| PR | 4092020 | PR interval duration | ms | SNOMED |
| RR | 3013078 | R-R interval by EKG | ms | LOINC |

---

## 8. Cognitive Assessments

**File**: `concept_maps/cognitive.csv`
**Loader**: `load_cognitive_concepts()` (group=core), `load_cognitive_extended()` (group=extended)
**Consumer**: `measurement_cognitive.py`
**Entries**: 16

### Core cognitive tests (group: core)

| source_code | concept_id | concept_name | unit |
|-------------|-----------|--------------|------|
| PACC | 2100000001 | PACC Composite Score | z-score |
| MMSCORE | 42869860 | Total score [MMSE] | score |
| CDGLOBAL | 2100000002 | CDR Global Score | score |
| CDSOB | 2100000003 | CDR Sum of Boxes | score |
| FCTOTAL96 | 2100000004 | FCSRT-96 Total | score |
| LDELTOTAL | 2100000005 | Logical Memory Delayed | score |
| DIGITTOTAL | 2100000006 | Digit Symbol Total | score |
| LIMMTOTAL | 2100000007 | Logical Memory Immediate | score |

MMSE (MMSCORE) is the only cognitive test mapped to a standard LOINC concept (42869860). All others require custom concepts because the specific scoring variants used in A4/LEARN do not have standard OMOP equivalents.

### Extended cognitive tests (group: extended)

| source_code | concept_id | concept_name | unit |
|-------------|-----------|--------------|------|
| CFIPTTOTAL | 2100000050 | CFI Patient Total | score |
| CFSPTTOTAL | 2100000051 | CFI Study Partner Total | score |
| DIGITTOTAL | 2100000052 | Digit Symbol Total | score |
| FCTOTAL96 | 2100000053 | FCSR Total 96 | score |
| FCTOTF | 2100000056 | FCSR Free Recall Total | score |
| FCTOTC | 2100000057 | FCSR Cued Recall Total | score |
| LIMMTOTAL | 2100000054 | Logical Memory Immediate | score |
| LDELTOTAL | 2100000055 | Logical Memory Delayed | score |

Some source codes (DIGITTOTAL, FCTOTAL96, LIMMTOTAL, LDELTOTAL) appear in both `core` and `extended` groups with different concept IDs. The `group` column and the group-filtered loaders ensure that each pipeline phase gets the correct mapping. The core versions correspond to the primary PACC battery; the extended versions correspond to standalone administrations of those tests.

---

## 9. CogState

**File**: `concept_maps/cogstate.csv`
**Loader**: `load_cogstate_concepts()` (test + composite), `load_cogstate_battery_concepts()` (battery), `load_cogstate_questionnaire_concepts()` (questionnaire)
**Consumer**: `measurement_cogstate.py`
**Entries**: 21

### Individual tests (group: test)

| source_code | concept_id | concept_name | unit |
|-------------|-----------|--------------|------|
| DET | 2100000040 | CogState Detection | log10(ms) |
| IDN | 2100000041 | CogState Identification | log10(ms) |
| ONB | 2100000042 | CogState One-Back | log10(ms) |
| OCL | 2100000043 | CogState One-Card Learning | arcsine(sqrt(proportion)) |
| CPAL | 2100000044 | CogState CPAL | arcsine(sqrt(proportion)) |
| LNS | 2100000045 | CogState Letter-Number Sequencing | score |
| FNMT | 2100000047 | CogState Face-Name Memory Test | score |
| FNLT | 2100000048 | CogState Face-Name Learning Test | score |
| FSBT | 2100000049 | CogState Face-Symbol Binding Test | score |
| BPXT | 2100000140 | CogState Brief Psychomotor Test | score |

### Composite scores (group: composite)

| source_code | concept_id | concept_name | unit |
|-------------|-----------|--------------|------|
| COGSTATE_COMPOSITE | 2100000046 | CogState Composite Score | z-score |
| C3Comp | 2100000141 | CogState C3 Composite | z-score |
| C3AbrComp | 2100000142 | CogState C3 Abbreviated Composite | z-score |
| AttnComp | 2100000143 | CogState Attention Composite | z-score |
| LearnWMComp | 2100000144 | CogState Learning/Working Memory Composite | z-score |
| OCLONBComp | 2100000145 | CogState OCL-ONB Composite | z-score |
| PsychAttnComp | 2100000146 | CogState Psychomotor/Attention Composite | z-score |

### Battery measures (group: battery)

| source_code | concept_id | concept_name | unit |
|-------------|-----------|--------------|------|
| BPET | 2100000147 | CogState Brief Psychomotor Exam | arcsine(sqrt(proportion)) |
| FNFT | 2100000148 | CogState Face-Name Feature Test | arcsine(sqrt(proportion)) |

### CogState questionnaires (group: questionnaire)

| source_code | concept_id | concept_name | unit |
|-------------|-----------|--------------|------|
| MCQT_TOTAL | 2100000090 | MACQ Memory Complaint Total | score |
| CPATH_TOTAL | 2100000091 | C-PATH Total Score | score |

All CogState concepts are custom. The non-standard unit values (`log10(ms)`, `arcsine(sqrt(proportion))`) reflect CogState's published data transformations.

---

## 10. Biomarkers

**File**: `concept_maps/biomarkers.csv`
**Loader**: `load_biomarker_concepts()`
**Consumer**: `measurement_biomarkers.py`
**Entries**: 21

### Plasma amyloid-beta

| source_code | concept_id | concept_name | unit |
|-------------|-----------|--------------|------|
| TP40 | 2100000011 | Total Plasma Abeta-40 | pg/mL |
| TP42 | 2100000012 | Total Plasma Abeta-42 | pg/mL |
| BP40 | 2100000013 | Bound Plasma Abeta-40 | pg/mL |
| BP42 | 2100000014 | Bound Plasma Abeta-42 | pg/mL |
| FP40 | 2100000015 | Free Plasma Abeta-40 | pg/mL |
| FP42 | 2100000016 | Free Plasma Abeta-42 | pg/mL |
| TP42/TP40 | 2100000010 | Amyloid-beta 42/40 Ratio | ratio |
| FP40/TP40 | 2100000510 | Free/Total Plasma Abeta-40 Ratio | ratio |
| FP42/FP40 | 2100000511 | Free Plasma Abeta-42/40 Ratio | ratio |
| FP42/TP42 | 2100000512 | Free/Total Plasma Abeta-42 Ratio | ratio |

### Tau and neurodegeneration markers

| source_code | concept_id | concept_name | unit | Notes |
|-------------|-----------|--------------|------|-------|
| PTAU217 | 1092155 | Tau protein.phosphorylated 217 [Mass/volume] in Serum or Plasma by Immunoassay | U/mL | LOINC 104663-0 |
| TPP181 | 1259491 | Phosphorylated tau 181 [Mass/volume] in Plasma by Immunoassay | pg/mL | LOINC 103675-5 (Roche LBTESTCD) |
| GFAP | 1761505 | Glial fibrillary acidic protein [Mass/volume] in Serum by Immunoassay | pg/mL | LOINC 100435-7 |
| NFL | 3966310 | Neurofilament light chain [Mass/volume] in Serum or Plasma by Immunoassay | pg/mL | LOINC 101281-4 |
| NF-L  | 3966310 | Neurofilament light chain [Mass/volume] in Serum or Plasma by Immunoassay | pg/mL | Trailing-space variant from source LBTESTCD |

The GFAP and NF-L entries include trailing-space variants to handle whitespace artifacts in the source LBTESTCD values.

### Alternative source codes (Roche platform)

| source_code | concept_id | concept_name |
|-------------|-----------|--------------|
| AMYLB40 | 2100000011 | Total Plasma Abeta-40 |
| AMYLB42 | 2100000012 | Total Plasma Abeta-42 |
| APOE4 | 3029139 | APOE Genotype |

---

## 11. Imaging

**File**: `concept_maps/imaging.csv`
**Loader**: `load_imaging_concepts()` (group=core), `load_imaging_extended()` (group=extended)
**Consumer**: `measurement_imaging.py`
**Entries**: 13

### Core imaging (group: core)

| source_code | concept_id | concept_name | unit |
|-------------|-----------|--------------|------|
| MRI_VOLUME | 2100000030 | Brain Region Volume | mL |
| SUVR_AMYLOID | 2100000031 | Amyloid PET SUVR | ratio |
| SUVR_TAU | 2100000032 | Tau PET SUVR | ratio |

For MRI volumes, the specific brain region is stored in the `measurement_source_value` field of the output. A single concept ID covers all volumetric MRI measures, with the region name providing the specificity.

### Extended imaging (group: extended)

| source_code | concept_id | concept_name | unit |
|-------------|-----------|--------------|------|
| MCH | 2100000070 | Microhemorrhage Count | count |
| LOBAR | 2100000075 | Lobar Microhemorrhage | binary |
| DEEP | 2100000076 | Deep Microhemorrhage | binary |
| WMH_VOL | 2100000071 | White Matter Hyperintensity Volume | mL |
| WMH_CORRECTED | 2100000072 | WMH Corrected for ICV | % |
| ICV | 2100000077 | Intracranial Volume | mL |
| RETINAL_AI | 2100000073 | Retinal AI Score | score |
| PET_VA_SUVR | 2100000074 | PET Visual Assessment SUVR | ratio |
| TAU_PETSURFER | 2100000078 | Tau PET SUVR PetSurfer | SUVR |
| TAU_STANFORD | 2100000079 | Tau PET SUVR Stanford | SUVR |

---

## 12. Observations

**File**: `concept_maps/observations.csv`
**Loader**: `load_observation_concepts()` (lifestyle + family_history), `load_study_partner_concepts()` (study_partner)
**Consumer**: `observation.py`
**Entries**: 14

### Lifestyle observations (group: lifestyle)

| source_code | concept_id | concept_name | Vocabulary |
|-------------|-----------|--------------|------------|
| SMOKE | 43054909 | Tobacco smoking status | SNOMED |
| ALCOHOL | 4238768 | Details of alcohol drinking behavior | SNOMED |
| CAFFEINE | 37153131 | Caffeine intake | SNOMED |
| AEROBIC | 4312325 | Active physical exercise | SNOMED |
| WALKING | 2100000300 | Walking exercise frequency | Custom |
| SLEEP | 2100000301 | Sleep duration hours | Custom |

### Family history (group: family_history)

| source_code | concept_id | concept_name | Vocabulary |
|-------------|-----------|--------------|------------|
| FAMHX_MOTHER | 4167217 | Family history of clinical finding | SNOMED |
| FAMHX_FATHER | 4167217 | Family history of clinical finding | SNOMED |
| FAMHX_SIBLING | 4167217 | Family history of clinical finding | SNOMED |

All three family history entries map to the same SNOMED concept. The specific relationship (mother, father, sibling) is preserved in the source value field of the observation record.

### Study partner (group: study_partner)

| source_code | concept_id | concept_name |
|-------------|-----------|--------------|
| RELATIONSHIP | 2100000080 | Study Partner Relationship |
| CONTACT_HRS | 2100000081 | Study Partner Contact Hours |
| COHABITATION | 2100000082 | Study Partner Cohabitation |
| SP_AGE | 2100000083 | Study Partner Age |
| SP_GENDER | 2100000084 | Study Partner Gender |

All study partner concepts are custom. These capture the required study partner demographics and contact information mandated by the A4/LEARN protocol.

---

## 13. Conditions

**File**: `concept_maps/conditions.csv`
**Loader**: `load_condition_concepts()`
**Consumer**: `condition.py`
**Entries**: 10

| source_code | concept_id | concept_name | Vocabulary |
|-------------|-----------|--------------|------------|
| PXCARD | 4103183 | Cardiac finding | SNOMED |
| PXPULM | 4024567 | Respiratory finding | SNOMED |
| PXABDOM | 441840 | Clinical finding | SNOMED |
| PXMUSCUL | 135930 | Musculoskeletal finding | SNOMED |
| PXEDEMA | 4158343 | Peripheral edema | SNOMED |
| PXSKIN | 141960 | Skin finding | SNOMED |
| NXGAIT | 4203631 | Motor dysfunction | SNOMED |
| NXMOTOR | 4203631 | Motor dysfunction | SNOMED |
| NXSENSOR | 4161682 | Hypoesthesia | SNOMED |
| NXTREMOR | 43531003 | Essential tremor | SNOMED |

Source codes beginning with `PX` come from the physical exam; codes beginning with `NX` come from the neurological exam. NXGAIT and NXMOTOR both map to Motor dysfunction (4203631) because the OMOP vocabulary does not distinguish gait-specific motor dysfunction from general motor dysfunction at the granularity needed.

PXABDOM maps to the generic "Clinical finding" concept (441840) because there is no specific SNOMED concept for abnormal abdominal exam findings at the appropriate level of generality.

---

## 14. Milestones

**File**: `concept_maps/milestones.csv`
**Loader**: `load_milestone_concepts()`
**Consumer**: `observation.py` (study disposition events)
**Entries**: 15

| source_code | concept_id | concept_name | Vocabulary |
|-------------|-----------|--------------|------------|
| INFORMED CONSENT OBTAINED | 3018196 | Informed consent obtained | LOINC |
| RANDOMIZED | 2000000010 | Study randomization | Custom |
| COMPLETED | 2000000011 | Study completion | Custom |
| SCREEN FAILURE | 2000000012 | Screen failure | Custom |
| WITHDRAWAL BY SUBJECT | 2000000013 | Withdrawal by subject | Custom |
| STUDY TERMINATED BY SPONSOR | 2000000014 | Study termination by sponsor | Custom |
| ADVERSE EVENT | 2000000015 | Discontinuation due to adverse event | Custom |
| DEATH | 4306655 | Death | SNOMED |
| LOST TO FOLLOW UP | 2000000016 | Lost to follow-up | Custom |
| OTHER | 2000000017 | Discontinuation for other reason | Custom |
| WITHDRAWAL BY PARENT/GUARDIAN | 2000000018 | Withdrawal by parent/guardian | Custom |
| LACK OF EFFICACY | 2000000019 | Discontinuation due to lack of efficacy | Custom |
| SAFETY RISK | 2000000020 | Discontinuation due to safety risk | Custom |
| PHYSICIAN DECISION | 2000000021 | Discontinuation by physician decision | Custom |
| PROTOCOL DEVIATION | 2000000022 | Discontinuation due to protocol deviation | Custom |

Two milestones use standard concepts: informed consent (LOINC 3018196) and death (SNOMED 4306655). All others are custom because the specific clinical trial disposition reasons have no standard OMOP equivalents.

---

## 15. C-SSRS

**File**: `concept_maps/cssrs.csv`
**Loader**: `load_cssrs_concepts()`
**Consumer**: `measurement_questionnaires.py`
**Entries**: 20

The Columbia Suicide Severity Rating Scale (C-SSRS) items are organized by the `category` column.

### Ideation items

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| WISHLIFE | 2100000100 | C-SSRS Wish to be Dead | Binary 0/1 |
| ACTLIFE | 2100000101 | C-SSRS Active Suicidal Ideation | Binary 0/1 |
| METHOD | 2100000102 | C-SSRS Has Method | Binary 0/1 |
| INTENT | 2100000103 | C-SSRS Has Intent | Binary 0/1 |
| PLAN | 2100000104 | C-SSRS Has Plan | Binary 0/1 |

### Attempt and self-injury items

| source_code | concept_id | concept_name | Category |
|-------------|-----------|--------------|----------|
| ATTMPT | 2100000105 | C-SSRS Suicide Attempt | attempt |
| ATTMPT5 | 2100000106 | C-SSRS Attempt Past 5 Years | attempt |
| ATTMPTN | 2100000107 | C-SSRS Number of Attempts | attempt |
| NONSUI | 2100000108 | C-SSRS Non-Suicidal Self-Injury | self_injury |
| NONSUI5 | 2100000111 | C-SSRS NSSI Past 5 Years | self_injury |

### Behavior items

| source_code | concept_id | concept_name |
|-------------|-----------|--------------|
| INTER | 2100000112 | C-SSRS Interrupted Attempt |
| ABORT | 2100000113 | C-SSRS Aborted Attempt |
| PREP | 2100000114 | C-SSRS Preparatory Behavior |
| BEHAVLIF | 2100000115 | C-SSRS Suicidal Behavior Lifetime |

### Severity and lethality items

| source_code | concept_id | concept_name | Category |
|-------------|-----------|--------------|----------|
| SEVLIFE | 2100000116 | C-SSRS Ideation Severity | severity (1-5 scale) |
| RECENTDAM | 2100000109 | C-SSRS Recent Attempt Damage | lethality |
| RECENTPOT | 2100000110 | C-SSRS Recent Attempt Lethality | lethality |
| LETHALDAM | 2100000117 | C-SSRS Most Lethal Damage | lethality |
| LETHALPOT | 2100000118 | C-SSRS Most Lethal Potential | lethality |

### Outcome

| source_code | concept_id | concept_name |
|-------------|-----------|--------------|
| SUICIDE | 2100000119 | C-SSRS Suicide Completion |

All C-SSRS concepts are custom (range 2100000100-2100000119).

---

## 16. C-SSRS Lifetime Columns

**File**: `concept_maps/cssrslv_columns.csv`
**Loader**: `load_cssrslv_column_map()`
**Consumer**: `measurement_questionnaires.py`
**Entries**: 15

This file does not contain concept IDs. It maps column names from the lifetime version of the C-SSRS (CSSRSLV form) to the standard C-SSRS keys used in the concept lookup. This allows both the standard and lifetime C-SSRS forms to share the same concept mapping.

| lifetime_column | standard_key |
|-----------------|-------------|
| WISHLV | WISHLIFE |
| ACTLV | ACTLIFE |
| METHODLV | METHOD |
| INTENTLV | INTENT |
| PLANLV | PLAN |
| ATTMPTLV | ATTMPT |
| ATTMLVN | ATTMPTN |
| NONSUILV | NONSUI |
| INTERLV | INTER |
| ABORTLV | ABORT |
| PREPLV | PREP |
| SEVLV | SEVLIFE |
| RECLVDAM | RECENTDAM |
| RECLVPOT | RECENTPOT |
| SUICIDE | SUICIDE |

---

## 17. Questionnaires

**File**: `concept_maps/questionnaires.csv`
**Loader**: `load_questionnaire_concepts()` (group=primary), `load_secondary_questionnaire_concepts()` (group=secondary)
**Consumer**: `measurement_questionnaires.py`
**Entries**: 18

### Primary questionnaires (group: primary)

| source_code | concept_id | concept_name | unit | Vocabulary |
|-------------|-----------|--------------|------|------------|
| GDTOTAL | 3051694 | Geriatric depression scale (GDS) total | score | LOINC standard |
| STAITOTAL | 2100000060 | STAI Total Score | score | Custom |
| ASSCORE | 37525066 | ADL01-Total ADCS-ADL Score | score | CDISC standard |
| CADDVLP | 2100000062 | AD Concern Development | score | Custom |
| CADKNOW | 2100000063 | AD Concern Knowledge | score | Custom |
| CADBLIEV | 2100000064 | AD Concern Belief | score | Custom |
| CADWRST | 2100000065 | AD Concern Worry | score | Custom |
| CADCNCRN | 2100000066 | AD Concern Total | score | Custom |

GDS (GDTOTAL) is the only primary questionnaire mapped to a standard concept (SNOMED 4159706). The AD Concern subscales are A4/LEARN-specific instruments without standard OMOP equivalents.

### Secondary questionnaires (group: secondary)

| source_code | concept_id | concept_name | Vocabulary |
|-------------|-----------|--------------|------------|
| IESCORE | 2100000200 | Impact of Events Scale Total | Custom |
| FTP_METHOD | 2100000201 | Future Time Perspective Method | Custom |
| RSS_QUALITY | 2100000202 | Research Satisfaction Quality | Custom |
| RSS_RECOMMEND | 2100000203 | Research Satisfaction Recommend | Custom |
| VIEWS_SEEK | 2100000204 | Views Seek Knowledge | Custom |
| RUIB_ADMIT | 2100000205 | Resource Use Hospital Admission | Custom |
| RUIB_VOLUNTEER | 2100000206 | Resource Use Volunteer Work | Custom |
| RUIB_EMPLOY | 2100000207 | Resource Use Employment | Custom |
| RUIB1_NIGHTS | 2100000208 | Hospital Overnight Stay Nights | Custom |
| RUIB1_TYPE | 2100000209 | Hospital Stay Type | Custom |

All secondary questionnaire concepts are custom. The RUIB (Resource Utilization in Brain-impaired patients) entries capture healthcare resource use data.

---

## 18. ADQS

**File**: `concept_maps/adqs.csv`
**Module**: `observation_adqs.py`
**Destination**: OBSERVATION
**Records created**: ~32,876 (subject-level observations)

The ADQS (Analysis Data Questionnaire Scores) file contains subject-level derived data including genetic information, treatment assignment, and study population flags. This data is extracted once per subject (not per visit) and produces OBSERVATION records.

### APOE Genotype

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| APOEGN | 3029139 | APOE gene alleles e2 and e3 and e4 [Identifier] in Blood or Tissue | LOINC 42315-2 |
| E2E2 | 36307526 | APOE e2/e2 | LOINC answer LA21356-3 |
| E2E3 | 36310377 | APOE e2/e3 | LOINC answer LA21357-1 |
| E2E4 | 36308156 | APOE e2/e4 | LOINC answer LA21361-3 |
| E3E3 | 36309003 | APOE e3/e3 (wild type) | LOINC answer LA21358-9 |
| E3E4 | 36311054 | APOE e3/e4 | LOINC answer LA21359-7 |
| E4E4 | 36303222 | APOE e4/e4 | LOINC answer LA21360-5 |

### APOE4 Carrier Status

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| APOEGNPRSNFLG | 3006041 | Apolipoprotein E4 [Presence] in Blood | LOINC 15353-6 |
| APOE4_POSITIVE | 4188539 | APOE epsilon 4 allele | SNOMED - carrier |
| APOE4_NEGATIVE | 4188540 | APOE epsilon 4 allele absence | SNOMED - non-carrier |

### Treatment Assignment

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| TX | 2100000400 | Treatment assignment | Randomization arm |
| TX_PLACEBO | 2100000401 | Placebo treatment arm | Custom |
| TX_SOLANEZUMAB | 2100000402 | Solanezumab treatment arm | Custom |

### Baseline Demographics (from SUBJINFO.csv)

Reviewer-confirmed in `Derived Dict mapping.xlsx`; sourced from `SUBJINFO.csv` (one row per subject).

| source_code | concept_id | concept_name | Destination | Notes |
|-------------|-----------|--------------|-------------|-------|
| EDCCNTU | 1015298 | Years of education | OBSERVATION | LOINC; value_as_number = years (0–36) |
| BMIBL | 4245997 | Body mass index | MEASUREMENT | SNOMED; value_as_number = baseline BMI (kg/m², unit 9531) |
| WRKRET | 44803812 | Retirement | OBSERVATION | SNOMED; value_as_concept 1=Yes (4188539) / 0=No (4188540) / 96=Unknown (0) |

### Study Population Flags

| source_code | concept_id | concept_name | Notes |
|-------------|-----------|--------------|-------|
| SUBJITTTR | 2100000410 | Intent-to-treat population flag | ITT analysis cohort |
| MITTFL | 2100000411 | Modified intent-to-treat population flag | mITT analysis cohort |
| SUBJPPSTR | 2100000412 | Per-protocol population flag | PP analysis cohort |
| SUBJSAFTR | 2100000413 | Safety population flag | Safety analysis cohort |

The population flags use value_as_concept_id to indicate Yes (4188539) or No (4188540) inclusion in each analysis population. These flags are critical for defining which subjects should be included in different types of statistical analyses.

---

## 19. Procedures

**File**: `concept_maps/procedures.csv`
**Loader**: `concepts.load_procedure_concepts()`
**Used by**: `procedure_occurrence.py`, `image_occurrence.py`

Maps imaging procedure type codes to OMOP PROCEDURE_OCCURRENCE concept IDs.

| source_code | concept_id | concept_name | notes |
|-------------|-----------|-------------|-------|
| MRI_BRAIN | 2100000080 | MRI Brain | Volumetric MRI of brain |
| PET_AMYLOID | 2100000081 | PET Amyloid | Florbetapir amyloid PET |
| PET_TAU | 2100000082 | PET Tau | Flortaucipir tau PET |
| RETINAL_IMAGING | 2100000083 | Retinal Imaging | Retinal OCT/fundus imaging |

---

## 20. Modalities

**File**: `concept_maps/modalities.csv`
**Loader**: `concepts.load_modality_concepts()`
**Used by**: `image_occurrence.py`, `image_feature.py`

Maps DICOM modality codes to standard OMOP concept IDs from the DICOM vocabulary (DICOM2OMOP, Park et al. 2025, PMID 38315345). These replaced earlier custom IDs 2100000090-92 (now reused exclusively for CogState questionnaires; see Section 9).

| source_code | concept_id | concept_name | notes |
|-------------|-----------|-------------|-------|
| MR | 2128009230 | Magnetic resonance | DICOM2OMOP standard (Park et al. 2025) |
| PT | 2128009252 | Positron emission tomography | DICOM2OMOP standard (Park et al. 2025) |
| OP | 2128009239 | Ophthalmic photography | DICOM2OMOP standard (Park et al. 2025) — retinal OCT/fundus |

---

## 21. Image Feature Types

**File**: `concept_maps/image_feature_types.csv`
**Loader**: `concepts.load_image_feature_type_concepts()`
**Used by**: `image_feature.py`

Maps provenance types to standard OMOP type concept IDs. Used for `image_feature_type_concept_id` in the IMAGE_FEATURE table.

| source_code | concept_id | concept_name | notes |
|-------------|-----------|-------------|-------|
| derived | 32880 | Derived value | Algorithm-derived measurement |
| ehr | 32817 | EHR | Direct clinical observation |

---

## 22. Image Findings

**File**: `concept_maps/image_findings.csv`
**Loader**: `concepts.load_image_finding_concepts()`
**Used by**: `image_feature.py`

Maps finding categories to custom concept IDs for grouping related image features via `image_finding_concept_id`.

| source_code | concept_id | concept_name | notes |
|-------------|-----------|-------------|-------|
| brain_volume | 2100000093 | Brain volumetric measurement | MRI FreeSurfer volumes |
| amyloid_suvr | 2100000094 | Amyloid PET SUVR | Amyloid PET uptake ratio |
| tau_suvr | 2100000095 | Tau PET SUVR | Tau PET uptake ratio |
| mri_read | 2100000096 | MRI radiological read | Qualitative MRI assessment |
| flair_volume | 2100000097 | FLAIR lesion volume | White matter hyperintensity |
| retinal_measure | 2100000098 | Retinal imaging measurement | OCT/fundus metrics |
| pet_visual_assessment | 2100000099 | PET visual assessment | Qualitative PET read |

---

## Custom Concept ID Ranges

All custom concept IDs follow a structured numbering scheme. The table below summarizes each allocated range and its domain.

Active custom concept ranges (185 total):

| Range | Domain | Count | Description |
|-------|--------|-------|-------------|
| 2000000001 -- 2000000003 | Drug | 3 | Solanezumab dose formulations |
| 2000000010 -- 2000000022 | Observation | 13 | Study milestones and discontinuation reasons |
| 2100000001 / 005 / 006 / 007 | Measurement | 4 | Core cognitive tests (PACC, LDELTOTAL, DIGITTOTAL, LIMMTOTAL) |
| 2100000010 -- 2100000022 | Measurement | 7 | Plasma AD biomarkers (Abeta forms TP/BP/FP × 40/42, ratio) — research-specific |
| 2100000030 -- 2100000032 | Measurement | 3 | Core neuroimaging (MRI volume, amyloid PET, tau PET) |
| 2100000040 -- 2100000049 | Measurement | 10 | CogState individual tests (DET, IDN, ONB, OCL, CPAL, LNS, etc.) |
| 2100000050 / 051 / 052 / 054 -- 057 | Measurement | 7 | Extended cognitive: CFI patient/SP totals, Digit Symbol ext, Logical Memory ext (immediate/delayed), FCSR free/cued |
| 2100000060 / 062 -- 067 | Observation | 7 | Questionnaire scales: STAI total, AD Concern items, AISCORE (ADLPQSP total) |
| 2100000070 -- 2100000079 | Measurement | 10 | Extended neuroimaging (microhemorrhage, WMH, retinal, PetSurfer, Stanford tau) |
| 2100000080 -- 2100000084 | Observation | 5 | Study partner demographics |
| 2100000090 / 091 | Measurement | 2 | CogState questionnaire totals (MACQ_TOTAL, CPATH_TOTAL) |
| 2100000093 -- 2100000099 | MI-CDM | 7 | Image findings (brain volume, SUVR, MRI read, FLAIR, retinal, PET VA) |
| 2100000100 -- 2100000119 | Observation | 4 | C-SSRS time-window customs (ATTMPT5, NONSUI5, BEHAVLIF, SUICIDE) |
| 2100000140 -- 2100000148 | Measurement | 9 | CogState composites and battery (BPET/FNFT) |
| 2100000163 | Measurement | 1 | MMSE WORLD attention letters |
| 2100000187 | Measurement | 1 | CDRSB Revised |
| 2100000200 -- 2100000209 | Observation | 8 | Secondary questionnaires (FTP_METHOD, RSS_QUALITY/RECOMMEND, VIEWS_SEEK, RUIB_ADMIT, RUIB1_NIGHTS/TYPE) |
| 2100000210 -- 2100000212 | Observation | 3 | Family history by relationship (Mother, Father, Sibling) |
| 2100000213 -- 2100000216 | Observation | 4 | ADLPQ items without standard CDISC concepts (ASPAY, ASTIMES, ASWDOWN, ASMOVIE) |
| 2100000217 -- 2100000226 | Observation | 10 | FTP Scale individual items |
| 2100000227 -- 2100000235 | Observation | 9 | RSS individual items (RSSTST uses SNOMED 4322976) |
| 2100000236 -- 2100000244 | Observation | 9 | VIEWS individual items |
| 2100000280 -- 2100000285 | Measurement | 6 | CogState MACQ individual items |
| 2100000290 -- 2100000315 | Measurement | ~26 | CogState C-PATH individual items |
| 2100000300 | Observation | 1 | Walking exercise frequency |
| 2100000400 -- 2100000402 | Observation | 3 | ADQS treatment arm (TX, TX_PLACEBO, TX_SOLANEZUMAB) |
| 2100000500 -- 2100000531 | Measurement | ~10 | Specialized lab biomarkers: Solanezumab PK/ADA panel (501-505), CSF Abeta forms (520-525), Hep E interp + HCV RNA (530-531), Edema severity (500) |

### Range allocation conventions

- **2000000xxx**: Study-level concepts (drugs, milestones, disposition)
- **2100000xxx**: Measurement and observation concepts specific to clinical instruments
- Gaps between ranges allow future additions within each domain without renumbering

---

## Custom Concepts Registry

The file `custom_concepts_needed.csv` at the project root serves as a formal vocabulary registry for all custom concepts. It follows the OMOP vocabulary format and contains the following columns:

| Column | Description |
|--------|-------------|
| concept_id | The custom concept ID |
| source_code | Source variable name |
| concept_name | Human-readable concept name |
| domain_id | OMOP domain (Measurement, Drug, Observation) |
| vocabulary_id | Always `A4_LEARN` |
| concept_class_id | Classification (e.g., Clinical Test, Drug) |
| standard_concept | Always `S` (standard) |
| concept_code | Internal code (e.g., A4_PACC_COMPOSITE) |
| valid_start_date | 2020-01-01 |
| valid_end_date | 2099-12-31 |
| invalid_reason | Empty (all valid) |
| record_count | Number of records in the output using this concept |
| category | Grouping label (Cognitive, CogState, Biomarker, etc.) |
| notes | Free-text description |

This file can be submitted to an OMOP vocabulary server or used as supporting documentation for data sharing agreements. It documents every custom concept alongside the record counts that justify its creation.

---

## Audit History and Pending Decisions

See `docs/Concept_Mapping_Decisions.md` for the full audit history (provenance of every concept_id correction, retirement, and architectural decision) and the list of pending architectural questions.

Key resolved decisions captured there:
- Reviewer-spreadsheet reconciliation against the curated mapping team's recommendations
- DICOM2OMOP reconciliation for MI-CDM modality concepts (per Park & Jeon et al. 2024)
- Adoption of LOINC standard concepts for biomarkers (GFAP, NFL, pTau-181/-217, APOE genotype)
- Routing of phyneuro exam findings to `condition_occurrence` (OMOP Condition-domain convention)

---

## Unit Concept Mapping in Post-Processing

Unit mapping occurs in two phases.

**Phase 1 -- At creation time**: Domain modules that have unit information in their concept CSV (vitals, biomarkers, imaging) assign `unit_source_value` and `unit_concept_id` when building measurement rows.

**Phase 2 -- Post-processing**: After all measurement records are assembled, `postprocessing.py:map_unit_concepts()` applies the global `units.csv` map to any record where `unit_concept_id` is still `0` but a non-null `unit_source_value` exists.

The post-processing step is necessary because many lab and clinical measurement records receive their unit strings from the source data rather than from the concept map, and those strings need to be resolved to standard UCUM concept IDs.

Records that remain unmapped after post-processing fall into two categories:
- Records with no unit (the measurement is unitless)
- Records with non-standard unit strings that have no UCUM equivalent (mapped to concept_id `0` in `units.csv`)

---

## How to Review or Edit Mappings

### Viewing mappings

Open any CSV file in the `concept_maps/` directory using a spreadsheet application (Excel, Google Sheets, LibreOffice Calc) or a text editor. Every column is self-documenting:

- **source_code**: The value from the source data that triggers this mapping
- **concept_id**: The target OMOP concept ID
- **concept_name**: Human-readable label for the concept
- **notes**: Explains the mapping rationale or flags special cases (duplicates, custom concepts, standard references)

### Adding a new mapping

1. Identify the correct CSV file for the data domain.
2. Add a row with the source code, target OMOP concept_id, concept name, and any required metadata (unit, group, notes).
3. If the concept is custom (no standard OMOP equivalent), select an ID from the appropriate range listed in [Custom Concept ID Ranges](#custom-concept-id-ranges) and add a corresponding entry to `custom_concepts_needed.csv`.
4. No Python code changes are needed. The `concepts.py` loaders read the CSV dynamically.

### Changing an existing mapping

1. Open the relevant CSV and locate the row by source_code.
2. Edit the `concept_id` column to the new OMOP concept ID.
3. Update the `concept_name` and `notes` columns to reflect the change.
4. If replacing a custom concept with a standard one, the custom concept entry in `custom_concepts_needed.csv` can be removed.

### Removing a mapping

Delete the row from the CSV. Any source records with that code will receive concept_id `0` (unmapped) in the output.

### Validation after changes

Re-run the pipeline and check the console output for mapping counts and validation results:

```bash
python -m a4_omop_etl
```

The pipeline prints record counts for each domain table and runs referential integrity checks. Compare output record counts before and after your changes to verify the edit had the expected effect.

### Important considerations when editing

- **Group column**: If the CSV has a `group` column, make sure new rows have the correct group value. The loader may filter on group, so a missing or incorrect value will cause the mapping to be silently excluded.
- **Duplicate source codes**: Some source codes intentionally appear multiple times (e.g., repeat specimens HMT71_1 through HMT71_5). These are legitimate and should not be removed.
- **Case sensitivity**: Source code matching is case-sensitive. If the source data contains case variants, add separate rows for each variant (see `units.csv` for examples).
- **Trailing whitespace**: Some biomarker source codes include trailing spaces (e.g., `GFAP `, `NF-L `). These are intentional and handle whitespace artifacts in the source data files.
