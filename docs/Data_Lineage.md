# Data Lineage

Field-level audit trail tracing every source field through the ETL to its OMOP output column. For each output table, this document describes the source files, filtering criteria, field transformations, concept lookups, and date calculations applied.

---

## Table of Contents

1. [date_anchor](#1-date_anchor)
2. [person](#2-person)
3. [visit_occurrence](#3-visit_occurrence)
4. [observation_period](#4-observation_period)
5. [drug_exposure](#5-drug_exposure)
6. [measurement](#6-measurement)
7. [observation](#7-observation)
8. [condition_occurrence](#8-condition_occurrence)
9. [procedure_occurrence (MI-CDM)](#9-procedure_occurrence-mi-cdm)
10. [image_occurrence (MI-CDM)](#10-image_occurrence-mi-cdm)
11. [image_feature (MI-CDM)](#11-image_feature-mi-cdm)

---

## 1. date_anchor

**Module:** `helpers.py` / `create_date_anchor()`
**Source:** SUBJINFO.csv (Derived Data)
**Records:** 6,945

| Output Column | Source | Transformation |
|---|---|---|
| `BID` | SUBJINFO.BID | Unique subject identifiers extracted |
| `offset_days` | Computed | `MD5(BID) mod 365` (range 0-364) |
| `synthetic_consent_date` | Computed | `2020-01-01 + offset_days` |

All downstream date calculations use `synthetic_consent_date + *_DAYS_CONSENT` to produce calendar dates.

---

## 2. person

**Module:** `person.py` / `create_person_table()`
**Sources:** SUBJINFO.csv (Derived Data), ptdemog.csv (Raw Data)
**Records:** 6,945

| Output Column | Source Field | Transformation |
|---|---|---|
| `person_id` | -- | Sequential integer 1..N |
| `gender_concept_id` | SUBJINFO.SEX | Mapped via `demographics.csv`: 1->8507 (Male), 2->8532 (Female) |
| `year_of_birth` | SUBJINFO.AGEYR + date_anchor | `synthetic_consent_date.year - AGEYR` |
| `month_of_birth` | -- | Fixed value: 6 (mid-year estimate) |
| `day_of_birth` | -- | Fixed value: 15 |
| `birth_datetime` | -- | NULL |
| `race_concept_id` | SUBJINFO.RACE | Mapped via `demographics.csv`: 5->8527 (White), 4->8516 (Black), 2->8515 (Asian), 1->8657 (AI/AN), 6->8557 (NH/PI) |
| `ethnicity_concept_id` | SUBJINFO.ETHNIC | Mapped via `demographics.csv`: 1->38003563 (Hispanic), 2->38003564 (Not Hispanic) |
| `race_source_value` | ptdemog.PTRACE | Raw multi-racial string preserved (may contain comma-separated values) |
| `gender_source_value` | SUBJINFO.SEX | Raw integer as string |
| `ethnicity_source_value` | SUBJINFO.ETHNIC | Raw integer as string |
| `person_source_value` | SUBJINFO.BID | Blinded subject ID (primary linkage key) |
| `location_id` | -- | NULL |
| `provider_id` | -- | NULL |
| `care_site_id` | -- | NULL |
| `*_source_concept_id` | -- | 0 for all three |

**Filtering:** None. All SUBJINFO rows produce person records.

**Multi-racial handling:** The primary `race_concept_id` comes from the SUBJINFO.RACE integer code. The `race_source_value` is populated from ptdemog.PTRACE, which may contain comma-separated values like "White,Asian". When RACE maps to 0 (unmapped), the subject likely has a multi-racial or other unlisted race code.

---

## 3. visit_occurrence

**Module:** `visit.py` / `create_visit_occurrence()`
**Source:** SV.csv (Derived Data)
**Records:** 99,795

| Output Column | Source Field | Transformation |
|---|---|---|
| `visit_occurrence_id` | -- | Sequential integer 1..N |
| `person_id` | SV.BID | Looked up from person table via BID match |
| `visit_concept_id` | SV.VISITCD, SV.VISIT | Rule-based mapping via `map_visit_concept()`: 001-005 -> screening, 006 -> baseline, "Infusion" in name -> infusion, 701-705 -> unscheduled, else -> default outpatient |
| `visit_start_date` | SV.SVSTDTC_DAYS_CONSENT | `synthetic_consent_date + SVSTDTC_DAYS_CONSENT` |
| `visit_end_date` | SV.SVSTDTC_DAYS_CONSENT | Same as start date (single-day visits) |
| `visit_type_concept_id` | -- | 32817 (EHR) |
| `visit_source_value` | SV.BID + SV.VISITCD | `"{BID}_{VISITCD zero-padded to 3}"` (e.g., "B10081264_001") |
| `visit_start_datetime` | -- | NULL |
| `visit_end_datetime` | -- | NULL |
| `visit_source_concept_id` | -- | 0 |
| `admitted_from_concept_id` | -- | 0 |
| `discharged_to_concept_id` | -- | 0 |
| `preceding_visit_occurrence_id` | -- | NULL |

**Filtering:** `SV.SVTYPE != 'Not Done'`. Rows where the visit was not performed are excluded.

**VISCODE zero-padding:** VISITCD values are cast to string and zero-padded to 3 digits (e.g., 1 -> "001", 24 -> "024"). This standardized format is used throughout the pipeline as the visit linkage key.

**Visit concept mapping** (from `visits.csv`):

| VISITCD Range | Category | Example |
|---|---|---|
| 001-005 | Screening | screening concept |
| 006 | Baseline | baseline concept |
| Contains "Infusion" | Drug infusion | infusion concept |
| 701-705 | Unscheduled | unscheduled concept |
| All others | Default outpatient | default concept |

---

## 4. observation_period

**Module:** `visit.py` / `create_observation_period()`
**Sources:** SUBJINFO.csv (Derived Data), SV.csv (Derived Data)
**Records:** 6,945

| Output Column | Source Field | Transformation |
|---|---|---|
| `observation_period_id` | -- | Sequential integer 1..N |
| `person_id` | -- | Sequential integer 1..N (matches person table) |
| `observation_period_start_date` | date_anchor | `synthetic_consent_date` (day 0 = consent) |
| `observation_period_end_date` | SUBJINFO.DISCDTC_DAYS_CONSENT or SV max | Prefers `synthetic_consent_date + DISCDTC_DAYS_CONSENT`; falls back to max visit date per person from SV |
| `period_type_concept_id` | -- | 32817 (EHR) |

**Post-processing expansion:** After all domain tables are built, `expand_observation_periods()` extends `observation_period_end_date` to cover the latest date across measurement, observation, and drug_exposure tables per person. Approximately 4,404 of 6,945 periods are expanded.

---

## 5. drug_exposure

**Module:** `drug_exposure.py` / `create_drug_exposure()`
**Source:** dose.csv (Raw Data)
**Records:** 74,777

| Output Column | Source Field | Transformation |
|---|---|---|
| `drug_exposure_id` | -- | Sequential integer 1..N |
| `person_id` | dose.BID | Looked up from person table via BID match |
| `drug_concept_id` | dose.BLINDDOSE | Mapped via `drugs.csv`: 400->2000000001, 800->2000000002, 1600->2000000003 |
| `drug_exposure_start_date` | dose.STARTDATE_DAYS_CONSENT | `synthetic_consent_date + STARTDATE_DAYS_CONSENT` |
| `drug_exposure_end_date` | dose.ENDDATE_DAYS_CONSENT | `synthetic_consent_date + ENDDATE_DAYS_CONSENT` |
| `drug_type_concept_id` | -- | 32838 (EHR administration record) |
| `stop_reason` | dose.COMPLETE | Raw completion status string |
| `quantity` | dose.BLINDDOSE | Dose in mg (400, 800, or 1600) |
| `route_concept_id` | -- | 4171047 (Intravenous) |
| `visit_occurrence_id` | dose.VISCODE | Linked via `BID_VISCODE` -> visit_source_value lookup |
| `drug_source_value` | dose.BLINDDOSE | `"Solanezumab {BLINDDOSE}mg"` |
| `route_source_value` | -- | "IV infusion" |
| `dose_unit_source_value` | -- | "mg" |
| `drug_source_concept_id` | -- | 0 |
| `days_supply`, `sig`, `refills`, `lot_number`, `verbatim_end_date` | -- | NULL |
| `drug_exposure_start_datetime`, `drug_exposure_end_datetime` | -- | NULL |

**Filtering:** `dose.DONE == 'Yes'`. Only completed infusions are included.

**Note:** 5 records have `drug_concept_id=0` due to BLINDDOSE=0 (unblinded/placebo records with no dose mapping).

---

## 6. measurement

**Records:** 4,494,112 (combined from 9 sub-modules; grew across Rounds 1-5 with item-level cognitive/CogState/biomarker additions)

All measurement records share a common set of columns populated identically:

| Column | Value | Notes |
|---|---|---|
| `measurement_type_concept_id` | 32817 | EHR source |
| `measurement_datetime` | NULL | Not available in source data |
| `measurement_time` | NULL | Not available |
| `operator_concept_id` | NULL | Not applicable |
| `value_as_concept_id` | NULL | Numeric values only |
| `unit_concept_id` | 0 initially | Populated by `map_unit_concepts()` post-processing |
| `provider_id` | NULL | Not tracked |
| `visit_detail_id` | NULL | Not used |
| `measurement_source_concept_id` | 0 | Custom vocabulary |

After all sub-modules produce their records, three pipeline-level steps are applied:
1. **Concatenation:** All partial DataFrames are combined with `pd.concat(..., ignore_index=True)`
2. **ID assignment:** `measurement_id` is reassigned as sequential integers 1..N
3. **Unit mapping:** `map_unit_concepts()` maps `unit_source_value` strings to `unit_concept_id` values using `units.csv`

### 6.1 Clinical (Vitals)

**Module:** `measurement_clinical.py` / `create_measurement_vitals()`
**Source:** vitals.csv (Raw Data)
**Filtering:** `DONE == 1`

| Source Column | OMOP Column | Concept | Unit |
|---|---|---|---|
| STDWT | value_as_number | Weight (from `vitals.csv` concept map) | kg |
| STDHT | value_as_number | Height | cm |
| VSBPSYS | value_as_number | Systolic BP | mmHg |
| VSBPDIA | value_as_number | Diastolic BP | mmHg |
| VSPULSE | value_as_number | Pulse | bpm |
| VSRESP | value_as_number | Respiration Rate | /min |
| STDTEMP | value_as_number | Temperature | degF |

**Date:** Uses `visit_start_date` from linked visit (no separate date column in vitals).
**measurement_source_value:** Column name (e.g., "STDWT").
**Visit linkage:** `BID_VISCODE` -> visit_source_value.

### 6.2 Clinical (Labs)

**Module:** `measurement_clinical.py` / `create_measurement_labs()`
**Source:** clrm_lab.csv (External Data)
**Filtering:** `TSTSTAT == 'D'` (done/completed)

| Source Column | OMOP Column | Notes |
|---|---|---|
| LBTESTCD | measurement_concept_id | Mapped via `labs.csv` (96 test codes) |
| SIRESN | value_as_number | Numeric SI result |
| SIU | unit_source_value | SI unit string |
| SINRLO | range_low | Normal range lower bound |
| SINRHI | range_high | Normal range upper bound |
| SIRESC | value_source_value | Raw result string |
| LBDTM_DAYS_CONSENT | measurement_date | `synthetic_consent_date + LBDTM_DAYS_CONSENT` |

**measurement_source_value:** `"{LBTESTCD}: {LBTEST}"` (code + test name).

### 6.3 Clinical (ECG)

**Module:** `measurement_clinical.py` / `create_measurement_ecg()`
**Source:** clrm_ecg.csv (External Data)
**Filtering:** `TSTSTAT == 'D'` AND `LBTESTCD in ['RATE', 'QT', 'QRS', 'PR', 'RR']`

Only numeric ECG parameters are extracted (text assessments like "INTP" are excluded).

| Source Column | OMOP Column | Notes |
|---|---|---|
| LBTESTCD | measurement_concept_id | Mapped via `ecg.csv` |
| SIRESN | value_as_number | |
| LBDTM_DAYS_CONSENT | measurement_date | |

### 6.4 Cognitive (PACC)

**Module:** `measurement_cognitive.py` / `create_measurement_pacc()`
**Source:** PACC.csv (Derived Data)
**Filtering:** None (all rows processed)

| Source Column | OMOP Column | Concept Name |
|---|---|---|
| PACC | value_as_number | PACC Composite Score |
| FCTOTAL96 | value_as_number | FCSRT-96 Total |
| LDELTOTAL | value_as_number | Logical Memory Delayed Total |
| DIGITTOTAL | value_as_number | Digit Symbol Total |

**Date:** Uses `visit_start_date` from linked visit.
**Note:** MMSCORE is excluded from PACC processing -- it is handled by the dedicated MMSE module.

### 6.5 Cognitive (MMSE)

**Module:** `measurement_cognitive.py` / `create_measurement_mmse()`
**Source:** mmse.csv (Raw Data)
**Filtering:** `DONE == 'Yes'` AND `MMSCORE` is not null

| Source Column | OMOP Column | Notes |
|---|---|---|
| MMSCORE | value_as_number | MMSE Total Score (0-30) |

**Date:** Uses `visit_start_date` from linked visit.
**range_low/range_high:** Set to 0 and 30 respectively.

### 6.6 Cognitive (CDR)

**Module:** `measurement_cognitive.py` / `create_measurement_cdr()`
**Source:** cdr.csv (Raw Data)
**Filtering:** `DONE == 'Yes'`

| Source Column | OMOP Column | Concept Name |
|---|---|---|
| CDGLOBAL | value_as_number | CDR Global Score |
| CDSOB | value_as_number | CDR Sum of Boxes |

**Date:** `synthetic_consent_date + CDADTC_DAYS_CONSENT` (CDR has its own date column).

### 6.7 Cognitive Extended

**Module:** `measurement_cognitive.py` / `create_measurement_cognitive_extended()`
**Sources:** cfi.csv, cfisp.csv, cogdigit.csv, cogfcsr16.csv, coglogic.csv (all Raw Data)
**Filtering:** `DONE == 'Yes'` (where column exists)

All five files are processed with a shared `process_cognitive_file()` function:

| File | Score Fields Extracted |
|---|---|
| cfi.csv | CFIPTTOTAL (CFI Patient Total) |
| cfisp.csv | CFSPTTOTAL (CFI Study Partner Total) |
| cogdigit.csv | DIGITTOTAL (Digit Symbol Total) |
| cogfcsr16.csv | FCTOTAL96, FCTOTF, FCTOTC (FCSR-16 Total, Free, Cued) |
| coglogic.csv | LIMMTOTAL, LDELTOTAL (Logical Memory Immediate, Delayed) |

**Date:** Uses `synthetic_consent_date` (no specific date column).
**Concept lookup:** `cognitive.csv` with `group_filter='extended'`.

### 6.8 Biomarkers

**Module:** `measurement_biomarkers.py` / `create_measurement_biomarkers()`
**Sources:** biomarker_AB_Test.csv, biomarker_pTau217.csv, biomarker_Plasma_Roche_Results.csv (all External Data)

#### Amyloid-Beta (AB_Test)

| Source Column | OMOP Column | Notes |
|---|---|---|
| LBTESTCD | measurement_concept_id | Mapped via `biomarkers.csv` (e.g., TP40, TP42, BP40, BP42, FP40, FP42) |
| LBORRES | value_as_number | Raw result value |
| LBORRESU | unit_source_value | Unit from source (fallback to concept map unit) |

**Date:** Uses `visit_start_date` from linked visit.

#### pTau-217

| Source Column | OMOP Column | Notes |
|---|---|---|
| ORRES / ORRESRAW | value_as_number | If ORRES starts with "<" (below LLOQ), uses ORRESRAW instead |
| ORRESU | unit_source_value | |
| COLLECTION_DATE_DAYS_CONSENT | measurement_date | `synthetic_consent_date + COLLECTION_DATE_DAYS_CONSENT` |

**measurement_source_value:** "PTAU217"

#### Roche Panel

| Source Column | OMOP Column | Notes |
|---|---|---|
| LBTESTCD | measurement_concept_id | Mapped via `biomarkers.csv` |
| LABRESN | value_as_number | Numeric lab result |
| LABORESU | unit_source_value | |
| LABD_DAYS_CONSENT | measurement_date | `synthetic_consent_date + LABD_DAYS_CONSENT` |

**measurement_source_value:** `"ROCHE:{LBTESTCD}"`

### 6.9 Imaging (Core)

**Module:** `measurement_imaging.py` / `create_measurement_imaging()`
**Sources:** imaging_volumetric_mri.csv, imaging_SUVR_amyloid.csv, imaging_SUVR_tau.csv (all External Data)

#### Volumetric MRI

All non-metadata columns are treated as brain region volumes. Each row x region produces one measurement record.

| Source Column | OMOP Column | Notes |
|---|---|---|
| Each ROI column | value_as_number | Brain region volume |
| Date_DAYS_CONSENT | measurement_date | `synthetic_consent_date + Date_DAYS_CONSENT` |

**measurement_source_value:** `"MRI:{region_column_name}"`
**Concept:** Single concept `MRI_VOLUME` applied to all regions.

#### Amyloid PET SUVR

**Filtering:** `scan_analyzed == 'Yes'`

| Source Column | OMOP Column | Notes |
|---|---|---|
| suvr_cer | value_as_number | Cerebellar-referenced SUVR |
| brain_region | measurement_source_value | `"AMYLOID:{brain_region}"` |
| scan_date_DAYS_CONSENT | measurement_date | |

#### Tau PET SUVR

**Filtering:** `scan_analyzed == 'Yes'`

| Source Column | OMOP Column | Notes |
|---|---|---|
| suvr_persi (preferred) or suvr_cer | value_as_number | Uses suvr_persi if available, falls back to suvr_cer |
| brain_region | measurement_source_value | `"TAU:{brain_region}"` |

### 6.10 Imaging Extended

**Module:** `measurement_imaging.py` / `create_measurement_imaging_extended()`
**Sources:** imaging_MRI_reads.csv, imaging_FLAIR_WMH_QC.csv, imaging_retinal.csv, imaging_PET_VA.csv, imaging_Tau_PET_PetSurfer.csv, imaging_Tau_PET_Stanford.csv (all External Data)

#### MRI Reads (Microhemorrhage)

| Source Column | OMOP Column | Concept Key |
|---|---|---|
| Definite.MCH | value_as_number | MCH |
| Lobar | value_as_number | LOBAR |
| Deep | value_as_number | DEEP |
| STUDYDATE_DAYS_CONSENT | measurement_date | |

#### FLAIR WMH

| Source Column | OMOP Column | Concept Key |
|---|---|---|
| WMHvol_masked | value_as_number | WMH_VOL |
| WMH_corrected | value_as_number | WMH_CORRECTED |
| ICV | value_as_number | ICV |

#### Retinal Imaging

| Source Column | OMOP Column | Notes |
|---|---|---|
| RAIModelScore | value_as_number | AI model score |
| ExamDate_DAYS_CONSENT | measurement_date | |

**measurement_source_value:** `"RETINAL:Eye={Eye},Field={Field}"`

#### PET VA (Visual Assessment)

| Source Column | OMOP Column | Notes |
|---|---|---|
| pmod_suvr | value_as_number | |
| scan_date_DAYS_CONSENT | measurement_date | |

**measurement_source_value:** `"PET_VA:ligand={ligand}"`

#### Tau PetSurfer / Tau Stanford

Both alternative tau pipelines pivot all region columns into individual measurement records. Each non-metadata column is a brain region.

**Stanford filtering:** Excludes columns starting with `Volume_mm3` (brain volumes, not SUVR ratios).

### 6.11 CogState (Computerized)

**Module:** `measurement_cogstate.py` / `create_measurement_cogstate()`
**Source:** COGSTATE_COMPUTERIZED.csv (Derived Data)
**Filtering:** `VALUE` is not null

| Source Column | OMOP Column | Notes |
|---|---|---|
| TESTCD | measurement_concept_id | Mapped via `cogstate.csv` (group: test/composite). Tests: DET, IDN, ONB, OCL, CPAL, LNS, FNMT, FNLT, etc. |
| VALUE | value_as_number | Test result |
| TESTDATE_DAYS_CONSENT | measurement_date | `synthetic_consent_date + TESTDATE_DAYS_CONSENT` |

**AVISIT-to-VISCODE mapping:** CogState uses AVISIT labels instead of VISCODE. A mapping dict converts labels like "Screening 1" -> "001", "Baseline" -> "006", "Week 24" -> "012", etc.

**measurement_source_value:** `"COGSTATE:{TESTCD}:{TRIAL}"`

### 6.12 CogState (Battery BPET/FNFT)

**Module:** `measurement_cogstate.py` / `create_measurement_cogstate_battery()`
**Source:** cogstate_battery.csv (External Data)
**Filtering:** `TCode in ['BPET', 'FNFT']` AND `acc` is not null

| Source Column | OMOP Column | Notes |
|---|---|---|
| TCode | measurement_concept_id | Mapped via `cogstate.csv` (group: battery) |
| acc | value_as_number | Accuracy metric |
| TDate_DAYS_CONSENT | measurement_date | |

Only BPET (Brief Pattern Evaluation Test) and FNFT (Face-Name Free Trial) are extracted -- these are not present in COGSTATE_COMPUTERIZED.

### 6.13 CogState (Questionnaires)

**Module:** `measurement_cogstate.py` / `create_measurement_cogstate_questionnaires()`
**Sources:** cogstate_macq.csv, cogstate_cpath.csv (both External Data)

#### MACQ (Memory Assessment Clinics Questionnaire)

**Filtering:** `Question == 'MCQT Total'`

| Source Column | OMOP Column | Notes |
|---|---|---|
| Score | value_as_number | Total score |
| Date_DAYS_CONSENT | measurement_date | |

**measurement_source_value:** `"cogstate_macq:MCQT_Total:{Session_ID}"`

#### C-PATH (Cognitive Function)

**Processing:** Individual question rows (Question Number 1-30) are aggregated by BID + VISCODE + Session_ID. The sum of Score values produces the total.

| Source Column | OMOP Column | Notes |
|---|---|---|
| Score (sum) | value_as_number | Aggregated total across questions |
| Date_DAYS_CONSENT | measurement_date | First value per group |

---

## 7. observation

**Records:** 1,600,129 (combined from 7 sub-modules; grew across Rounds 1-5 with ADLPQ/GDS/IES/FTP/RSS/VIEWS item-level extraction)

All observation records share:

| Column | Value |
|---|---|
| `observation_type_concept_id` | 32817 (EHR) |
| `observation_datetime` | NULL |
| `observation_source_concept_id` | 0 |
| `unit_concept_id` | 0 |

### 7.1 Lifestyle (Habits)

**Module:** `observation.py` / `create_observation_lifestyle()`
**Source:** habits.csv (Raw Data)
**Filtering:** `DONE == 1`

| Source Column | OMOP Column | Concept Key |
|---|---|---|
| SMOKE | value_as_number | SMOKE |
| ALCOHOL | value_as_number | ALCOHOL |
| CAFFEINE | value_as_number | CAFFEINE |
| AEROBIC | value_as_number | AEROBIC |
| WALKING | value_as_number | WALKING |
| SLEEP | value_as_number | SLEEP |

Each non-null lifestyle column produces one observation record per row. **Date:** Uses `visit_start_date` from linked visit.

**observation_source_value:** `"HABITS:{column_name}"`

### 7.2 Family History (Parents)

**Module:** `observation.py` / `create_observation_family_history()`
**Source:** famhxpar.csv (Raw Data)
**Filtering:** MOTHER/FATHER values must be 1 (Yes) or 2 (No)

| Source Column | OMOP Column | Notes |
|---|---|---|
| MOTHER | value_as_number | 1=Yes, 2=No (family history of Alzheimer's/dementia) |
| FATHER | value_as_number | 1=Yes, 2=No |

**value_as_concept_id:** 4188539 (Yes) when value=1, 4188540 (No) when value=2.
**Date:** Uses `synthetic_consent_date`.

### 7.3 Family History (Siblings)

**Module:** `observation.py` / `create_observation_family_history()`
**Source:** famhxsib.csv (Raw Data)
**Filtering:** `SIBDEMENT == 1` (only records where sibling has dementia are included)

| Source Column | OMOP Column | Notes |
|---|---|---|
| SIBDEMENT | value_as_number | 1.0 (always Yes, since only positive records are kept) |
| RECNO | observation_source_value | `"FAMHX:SIBLING_{RECNO}"` identifies which sibling |

### 7.4 Milestones (Disposition)

**Module:** `observation.py` / `create_observation_milestones()`
**Source:** DS.csv (Derived Data)
**Filtering:** `DSDECOD` is not null

| Source Column | OMOP Column | Notes |
|---|---|---|
| DSDECOD | observation_concept_id | Mapped via `milestones.csv` (e.g., "Randomized", "Completed", "Adverse Event") |
| DSDECOD | value_as_string | Raw disposition event name |
| DSSTDTC_DAYS_CONSENT | observation_date | `synthetic_consent_date + DSSTDTC_DAYS_CONSENT` |
| DSCAT | qualifier_source_value | Disposition category |

**observation_source_value:** `"DS:{DSDECOD}:{DSCAT}:{EPOCH}"`

### 7.5 C-SSRS (Columbia Suicide Severity Rating Scale)

**Module:** `observation.py` / `create_observation_cssrs()`
**Sources:** cssrs.csv (Raw Data, current), cssrslv.csv (Raw Data, lifetime)

#### Current C-SSRS (cssrs.csv)

Items extracted: WISHLIFE, ACTLIFE, METHOD, INTENT, PLAN, ATTMPT, ATTMPT5, ATTMPTN, NONSUI, NONSUI5, INTER, ABORT, PREP, BEHAVLIF, SEVLIFE, RECENTDAM, RECENTPOT, LETHALDAM, LETHALPOT

Each item in each row produces one observation record. Values are typically 0 (No) or 1 (Yes).

| Column | Value |
|---|---|
| `qualifier_concept_id` | 32880 (Current) |
| `qualifier_source_value` | "Current" |
| `value_as_concept_id` | 4188539 (Yes) if value=1, 4188540 (No) if value=0 |

#### Lifetime C-SSRS (cssrslv.csv)

Items extracted: WISHLIFE, ACTLIFE, METHOD, INTENT, PLAN, ATTMPT, ATTMPTN, NONSUI, INTER, ABORT, PREP, SEVLIFE, RECENTDAM, RECENTPOT, SUICIDE

The lifetime file has different column names than the standard keys. The `cssrslv_columns.csv` mapping file translates lifetime column names to standard concept keys (e.g., lifetime source column -> standard key like "WISHLIFE").

| Column | Value |
|---|---|
| `qualifier_concept_id` | 4181344 (Lifetime) |
| `qualifier_source_value` | "Lifetime" |

**Date:** Uses `synthetic_consent_date` for both files.

### 7.6 Study Partner

**Module:** `observation.py` / `create_observation_study_partner()`
**Source:** spinfo.csv (Raw Data)

Three observation types per study partner record:

| Source Column | Concept Key | Notes |
|---|---|---|
| INFRELAT | RELATIONSHIP | Relationship code (integer) |
| INFHRS | CONTACT_HRS | Hours per week (filtered: > 0) |
| INFLIVE | COHABITATION | 1=Lives with participant, else not |

**value_as_concept_id** for INFLIVE: 4188539 (Yes) if 1, 4188540 (No) otherwise.
**observation_source_value:** `"SPINFO:BPID={BPID}:{field}"`

### 7.7 Secondary Questionnaires

**Module:** `observation.py` / `create_observation_secondary_questionnaires()`
**Sources:** ies.csv, ftpscale.csv, rss.csv, views.csv, ruib.csv, ruib1.csv (all Raw Data)

| File | Filtering | Field(s) | Concept Key(s) |
|---|---|---|---|
| ies.csv | DONE == 1 | IESCORE | IESCORE (Impact of Events total) |
| ftpscale.csv | DONE == 1 | FTMETHOD | FTP_METHOD (Future Time Perspective) |
| rss.csv | DONE == 1 | RSSQUAL, RSSRECOM | RSS_QUALITY, RSS_RECOMMEND |
| views.csv | DONE == 1 | VSEEK | VIEWS_SEEK |
| ruib.csv | DONE == 1 | BRADMIT, VOLUNTEER, EMPLOY | RUIB_ADMIT, RUIB_VOLUNTEER, RUIB_EMPLOY |
| ruib1.csv | None | BR1NIGHT, BR1TYPE | RUIB1_NIGHTS, RUIB1_TYPE |

**Date calculations:**
- IES: `synthetic_consent_date + IEDATE_DAYS_CONSENT`
- FTP, RSS, VIEWS, RUIB, RUIB1: `synthetic_consent_date` (no date offset column)

For RUIB binary fields (BRADMIT, VOLUNTEER, EMPLOY): `value_as_concept_id` is set to 4188539 (Yes) or 4188540 (No) based on the value.

### 7.7 ADQS (Subject-Level Data)

**Module:** `observation_adqs.py` / `create_observation_adqs()`
**Source:** ADQS.csv (Derived Data)
**Records:** ~32,876

Subject-level derived data including APOE genotype, treatment assignment, and study population flags.

#### APOE Genotype

| Source Column | OMOP Column | Notes |
|---|---|---|
| APOEGN | measurement_concept_id | 3029139 (LOINC 42315-2 APOE gene alleles e2/e3/e4 [Identifier]) |
| APOEGN | value_as_string | Genotype string (E2E2, E2E3, E3E3, E3E4, E4E4, etc.) |
| APOEGN | value_as_concept_id | LOINC LA answer code per genotype (36307526/36310377/36308156/36309003/36311054/36303222) |

**observation_source_value:** `"ADQS:APOEGN:{genotype}"`

#### APOE4 Carrier Status

| Source Column | OMOP Column | Notes |
|---|---|---|
| APOEGNPRSNFLG | measurement_concept_id | 3006041 (LOINC 15353-6 Apolipoprotein E4 [Presence] in Blood) |
| APOEGNPRSNFLG | value_as_concept_id | 4188539 (Yes) if carrier, 4188540 (No) otherwise |

**observation_source_value:** `"ADQS:APOE4_CARRIER"`

#### Treatment Assignment

| Source Column | OMOP Column | Notes |
|---|---|---|
| TX | observation_concept_id | 2100000400 (Treatment assignment) |
| TX | value_as_string | "Placebo" or "Solanezumab" |
| TX | value_as_concept_id | 2100000401 (Placebo) or 2100000402 (Solanezumab) |

**Filtering:** Only records where TX is "Placebo" or "Solanezumab".
**observation_source_value:** `"ADQS:TX:{treatment}"`

#### Study Population Flags

| Source Column | Concept ID | Description |
|---|---|---|
| SUBJITTTR | 2100000410 | Intent-to-treat population |
| MITTFL | 2100000411 | Modified intent-to-treat population |
| SUBJPPSTR | 2100000412 | Per-protocol population |
| SUBJSAFTR | 2100000413 | Safety population |

**Filtering:** Only records where flag value is 'Y' or 'Yes'.
**value_as_concept_id:** 4188539 (Yes) for all included records.
**observation_source_value:** `"ADQS:{flag_column}"`

**Date:** Uses `synthetic_consent_date` (baseline subject-level data).

#### Baseline Demographics (SUBJINFO)

Sourced from `SUBJINFO.csv` (one row per subject), not ADQS — these are static baseline attributes. Reviewer-confirmed in `Derived Dict mapping.xlsx`.

| Source Column | OMOP Column | Destination | Notes |
|---|---|---|---|
| EDCCNTU | observation_concept_id | OBSERVATION | 1015298 (LOINC "Years of education"); value_as_number = years (0–36) |
| BMIBL | measurement_concept_id | MEASUREMENT | 4245997 (SNOMED "Body mass index"); value_as_number = baseline BMI; unit kg/m² → 9531 |
| WRKRET | observation_concept_id | OBSERVATION | 44803812 (SNOMED "Retirement"); value_as_concept_id 1=Yes (4188539) / 0=No (4188540) / 96=Unknown (0) |

**source_value:** `"SUBJINFO:EDCCNTU={years}"`, `"SUBJINFO:BMIBL={bmi}"`, `"SUBJINFO:WRKRET={code}"`. `NA` values skipped (6,856 education / 5,562 BMI / 6,882 retirement rows produced).

### 7.8 Questionnaires (Primary)

**Module:** `observation_questionnaires.py` / `create_observation_questionnaires()`
**Sources:** psychwell.csv, adlpq.csv, adlpqsp.csv, concerns.csv (all Raw Data)
**Records:** ~134,613

Questionnaire data was moved from MEASUREMENT to OBSERVATION domain per OMOP CDM specification (questionnaires are clinical observations, not physical measurements).

All four files use a shared `process_questionnaire()` function.

| File | Filtering | Score Fields | Notes |
|---|---|---|---|
| psychwell.csv | DONE == 1 | GDTOTAL (GDS), STAITOTAL (STAI) | Geriatric Depression Scale + State-Trait Anxiety |
| adlpq.csv | DONE == 'Yes' | ASSCORE | Activities of Daily Living - Patient |
| adlpqsp.csv | DONE == 'Yes' | ASSCORE | Activities of Daily Living - Study Partner |
| concerns.csv | DONE == 1 | CADDVLP, CADKNOW, CADBLIEV, CADWRST, CADCNCRN | AD Concern Scale (5 items) |

| Source Column | OMOP Column | Notes |
|---|---|---|
| Score field | value_as_number | Numeric questionnaire score |
| Score field name | observation_concept_id | Mapped via `questionnaires.csv` (group='primary') |
| Score field name | observation_source_value | Format: `"QUEST:{source_file}:{field}"` |

**Date:** Uses `visit_start_date` from linked visit when available, otherwise `synthetic_consent_date`.
**Concept lookup:** `questionnaires.csv` with `group_filter='primary'`.

**Note:** Prior ETL versions mapped these to MEASUREMENT. Per OMOP specification, questionnaire scores are clinical observations (non-physical measurements) and belong in the OBSERVATION table.

---

## 8. condition_occurrence

**Module:** `condition.py` / `create_condition_occurrence()`
**Source:** phyneuro.csv (Raw Data)
**Records:** 7,391 (abnormal physical & neurological exam findings from phyneuro). Normal findings are dropped per OMOP convention; PXEDSEV severity (ordinal 0-4) is stored in measurement.

| Output Column | Source Field | Transformation |
|---|---|---|
| `condition_occurrence_id` | -- | Sequential integer 1..N |
| `person_id` | phyneuro.BID | Looked up from person table |
| `condition_concept_id` | phyneuro field name | Mapped via `conditions.csv`: PXCARD, PXPULM, PXABDOM, PXMUSCUL, PXEDEMA, PXSKIN (physical) + NXGAIT, NXMOTOR, NXSENSOR, NXTREMOR (neuro) |
| `condition_start_date` | date_anchor | `synthetic_consent_date` |
| `condition_type_concept_id` | -- | 32817 (EHR) |
| `condition_status_source_value` | -- | "Abnormal" |
| `visit_occurrence_id` | phyneuro.VISCODE | Linked via `BID_VISCODE` |
| `condition_source_value` | -- | `"PHYNEURO:{field_name}"` |

**Filtering:** `DONE == 1` AND field value == 2 (Abnormal)

Physical and neurological exam fields use a coded scale: 1=Normal, 2=Abnormal, 3=Not examined. Only value==2 produces a condition record.

**Fields checked:**

| Field | Exam Type | Clinical Domain |
|---|---|---|
| PXCARD | Physical | Cardiovascular |
| PXPULM | Physical | Pulmonary |
| PXABDOM | Physical | Abdominal |
| PXMUSCUL | Physical | Musculoskeletal |
| PXEDEMA | Physical | Edema |
| PXSKIN | Physical | Dermatological |
| NXGAIT | Neurological | Gait |
| NXMOTOR | Neurological | Motor function |
| NXSENSOR | Neurological | Sensory function |
| NXTREMOR | Neurological | Tremor |

---

## Post-Processing Transformations

### Unit Concept Mapping

**Module:** `postprocessing.py` / `map_unit_concepts()`
**Applied to:** measurement table (after concatenation)
**Mapping source:** `concept_maps/units.csv` (43 unit entries)

Scans rows where `unit_concept_id == 0` and `unit_source_value` is not null, then applies the mapping. Example mappings:

| unit_source_value | unit_concept_id | Standard Unit |
|---|---|---|
| kg | 9529 | kilogram |
| mmHg | 8876 | millimeter mercury column |
| pg/mL | 8845 | picogram per milliliter |
| score | 0 | No standard UCUM code |

Result: ~30-55% of measurements have mapped unit concepts (varies as item-level data has been added); remaining are primarily unitless (scores, SUVR ratios, z-scores, and other non-UCUM units).

### Visit Linkage

**Module:** `helpers.py` / `prepare_source_df()` — applied at extraction time, not as a post-processing step
**Method:** exact VISCODE (or exact date) match — no fuzzy/day-window matching

Records are linked to visits by exact key: `prepare_source_df` builds `BID_VISCODE` and merges against `visit_occurrence` on that key. Imaging tables link by exact synthetic date (`*_DAYS_CONSENT`) instead. Records with no matching VISCODE or date — subject-level derived values, retinal scans merged without a visit frame, etc. — keep a null `visit_occurrence_id`. Result: ~78% of measurements carry a `visit_occurrence_id`.

### Observation Period Expansion

**Module:** `postprocessing.py` / `expand_observation_periods()`
**Applied to:** observation_period table

Extends `observation_period_end_date` to cover the latest event date per person across measurement, observation, and drug_exposure tables. ~4,404 of 6,945 persons have their periods expanded.

---

## 9. procedure_occurrence (MI-CDM)

**Module:** `procedure_occurrence.py` / `create_procedure_occurrence()`
**Sources:** imaging_mri, imaging_amyloid, imaging_tau, imaging_mri_reads, imaging_flair, imaging_retinal, imaging_pet_va, tau_petsurfer, tau_stanford (External Data)
**Records:** 20,307 (deduplicated from 358,679 raw)

| Output Column | Source | Transformation |
|---|---|---|
| `procedure_occurrence_id` | Generated | Sequential 1..N |
| `person_id` | Source BID | Lookup via person table |
| `procedure_concept_id` | Source file type | Map via `concept_maps/procedures.csv` |
| `procedure_date` | `*_DAYS_CONSENT` | Anchored date: `synthetic_consent_date + days` |
| `visit_occurrence_id` | BID + VISCODE | Visit lookup |
| `procedure_source_value` | Source file type | e.g., `MRI_BRAIN`, `PET_AMYLOID`, `PET_TAU`, `RETINAL_IMAGING` |

**Deduplication:** One row per unique (person_id, procedure_concept_id, procedure_date).

---

## 10. image_occurrence (MI-CDM)

**Module:** `image_occurrence.py` / `create_image_occurrence()`
**Sources:** Same imaging sources as procedure_occurrence
**Records:** 23,898

| Output Column | Source | Transformation |
|---|---|---|
| `image_occurrence_id` | Generated | Sequential 1..N |
| `person_id` | Source BID | Lookup via person table |
| `procedure_occurrence_id` | Computed | Join on (person_id, procedure_concept_id, date) |
| `visit_occurrence_id` | BID + VISCODE | Visit lookup |
| `anatomic_site_concept_id` | Series type | 4007117 (Brain) for MRI/PET, 4103720 (Eye) for retinal |
| `wadors_uri` | -- | Always NULL (no PACS) |
| `local_path` | -- | Always NULL (no local DICOM) |
| `image_occurrence_date` | `*_DAYS_CONSENT` | Anchored date |
| `image_study_UID` | BID + date + modality | Synthetic: `2.25.{int(MD5(seed)[:24], 16)}` |
| `image_series_UID` | BID + date + modality + series_type | Synthetic: `2.25.{int(MD5(seed)[:24], 16)}` |
| `modality_concept_id` | Series type | Map via `concept_maps/modalities.csv` (MR→2128009230, PT→2128009252, OP→2128009239; DICOM2OMOP standard, Park et al. 2025) |

**Granularity:** One row per unique (person_id, series_type, date).

---

## 11. image_feature (MI-CDM)

**Module:** `image_feature.py` / `create_image_feature()`
**Sources:** measurement table (filtered to rows with `_mi_cdm_modality` annotation), image_occurrence table
**Records:** 675,690

| Output Column | Source | Transformation |
|---|---|---|
| `image_feature_id` | Generated | Sequential 1..N |
| `person_id` | measurement.person_id | Direct |
| `image_occurrence_id` | Computed | Join measurement to image_occurrence on (person_id, date, modality) |
| `image_feature_event_field_concept_id` | Constant | 1147330 (= measurement.measurement_id concept) |
| `image_feature_event_id` | measurement.measurement_id | Direct (polymorphic FK) |
| `image_feature_concept_id` | measurement.measurement_concept_id | Direct |
| `image_feature_type_concept_id` | Constant | 32880 (Derived value) |
| `image_finding_concept_id` | `_mi_cdm_pipeline` annotation | Map via `_PIPELINE_TO_FINDING` → `concept_maps/image_findings.csv` |
| `image_finding_id` | Computed | Auto-increment per (person, date, series_type, pipeline) group |
| `anatomic_site_concept_id` | image_occurrence.anatomic_site_concept_id | Inherited from matched image_occurrence |
| `alg_system` | `_mi_cdm_pipeline` annotation | Map via `_PIPELINE_TO_ALG_SYSTEM` (e.g., `urn:a4:pipeline:petsurfer`) |
| `alg_datetime` | -- | Always NULL |

**Grouping:** Measurements from the same (person, date, series_type, pipeline) share an `image_finding_id`.

**Annotations:** Temporary `_mi_cdm_modality`, `_mi_cdm_series_type`, `_mi_cdm_pipeline` columns are added by `measurement_imaging.py` and stripped by `strip_mi_cdm_annotations()` before measurement export.
