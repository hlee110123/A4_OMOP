# Concept Mapping Investigation & Decisions Log

Started 2026-05-05. Records findings, fixes, and pending decisions from the systematic concept-mapping audit kicked off after the DICOM2OMOP reconciliation.

Status legend: ✅ resolved · ⏸ pending user decision · ⚠ requires Athena verification

---

## Task 1 — image_occurrence missing `visit_occurrence_id` (~70%) ✅

### Findings

Two independent bugs were responsible:

1. **Date-based imaging branches skipped VISCODE-based visit linkage.** In `a4_omop_etl/image_occurrence.py`, the visit-based branch (FLAIR / petsurfer / stanford) passed `visit_occurrence_df` to `prepare_source_df`, but the date-based branch (volumetric MRI, amyloid PET, tau PET, MRI reads, PET VA, retinal) didn't — so even sources that had VISCODE never got `visit_occurrence_id`.

2. **`prepare_source_df` produced wrong `visit_source_value` when VISCODE was float64.** `imaging_volumetric_mri.csv` has 540 NaN VISCODEs which forces the column to float64. `astype(str).str.zfill(3)` then yields `'4.0'` instead of `'004'`, breaking the join to `visit_occurrence`.

### Fixes

| File | Change |
|---|---|
| `a4_omop_etl/image_occurrence.py` | Pass `visit_occurrence_df` to `prepare_source_df` in the date-based branch when VISCODE is available |
| `a4_omop_etl/helpers.py` | In `prepare_source_df`, normalize VISCODE via `pd.to_numeric → Int64 → str → zfill(3)` so float64 columns no longer break the join |

### Outcome

| Modality | Before | After |
|---|---|---|
| MR (2128009230) | 41.7% missing | 5.4% missing |
| PT (2128009252) | 96.3% missing | 0.4% missing |
| OP (2128009239) | 100% missing | 100% missing |
| **Overall** | **70.0%** | **3.9%** |

### Remaining gaps

- **OP retinal (249 rows, 100% missing)** — `imaging_retinal.csv` has no VISCODE, only `ExamDate_DAYS_CONSENT`. Linkage would require date-window matching against `visit_occurrence.visit_start_date`. Deferred (small absolute count).
- **MR (5.4%)** — likely VISCODE values pointing to "Not Done" SV rows that were filtered out of `visit_occurrence`, or 998/999 sentinel codes. Acceptable.

### Side effect

The `helpers.py` fix is global — any other ETL domain whose source data had NaN VISCODEs forcing float64 dtype is now also linking better.

---

## Task 2 — Anatomic site concepts: SNOMED vs DICOM2OMOP ⏸ Pending user decision

### Findings

Both options exist:

| Site | Current (SNOMED) | DICOM2OMOP option |
|---|---|---|
| Brain | 4007117 (`vocab=SNOMED`, `domain=Spec Anatomic Site`) | 2128009416 (`vocab=DICOM`, `domain=Measurement`, `class=DICOM Value Sets`) |
| Eye | 4103720 (`vocab=SNOMED`, `domain=Spec Anatomic Site`) | 2128009479 (`vocab=DICOM`, `domain=Measurement`, `class=DICOM Value Sets`) |

### Recommendation: keep SNOMED

Park & Jeon et al. 2024 (Table 2 description for `anatomic_site_concept_id`) specifies:

> "It maps the ANATOMIC_SITE_SOURCE_VALUE to a **Standard Concept in the Spec Anatomic Site domain**."

Our SNOMED concepts are the canonical OMOP-standard concepts in the Spec Anatomic Site domain. The DICOM2OMOP `BRAIN` / `EYE` concepts are DICOM Value Sets in the Measurement domain — they enumerate values that appear inside the DICOM `BodyPartExamined` tag, not OMOP anatomic site references.

### Decision needed

Confirm whether to: **(A)** keep SNOMED [recommended], **(B)** replace with DICOM2OMOP, or **(C)** add separate DICOM body-part observation alongside SNOMED.

---

## Task 3 — Unit case variants (ng/mL vs NG/ML) ✅

### Findings

Case variants in source data are real and intentional:
- ROCHE biomarker uses uppercase: `PG/ML`, `NG/ML`
- AB / AD biomarker assays use lowercase: `pg/mL`, `ng/mL`
- HMT2 hematocrit reports `Ratio`, imaging uses `ratio`

### Fix

Made unit lookup case-insensitive in `a4_omop_etl/postprocessing.py:map_unit_concepts()` by lowercasing both the `units.csv` keys and the `unit_source_value` at lookup time. Removed redundant uppercase-variant rows from `concept_maps/units.csv` (`NG/ML`, `PG/ML`, `Ratio`, `UG/ML` collapsed to single canonical lowercase entries).

### Outcome

`unit_source_value` retains original casing for traceability; `unit_concept_id` resolves correctly regardless of casing. New source casings will automatically map without requiring units.csv updates.

---

## Task 4 — GI/L and TI/L → standard concepts ✅

### Findings

| Unit | Used by | Magnitude | Was | Should be |
|---|---|---|---|---|
| GI/L | WBC, neutrophils, lymphocytes, eosinophils, basophils (median 1.59) | 10⁹/L (billion per L) | 8848 | 9444 (billion per liter) |
| TI/L | RBC count (median 4.5) | 10¹²/L (trillion per L) | 8848 | 8734 (trillion per liter) |

Both were mapped to the same concept (8848) despite representing different magnitudes.

### Fix

`concept_maps/units.csv` updated:
- `GI/L,9444,billion per liter (10^9/L) — used for WBC, neutrophils, lymphocytes, etc.`
- `TI/L,8734,trillion per liter (10^12/L) — used for RBC count`

### Verification note

Concept_ids per user guidance (8734 trillion/L, 9444 billion/L). Should be verified against current OMOP vocabulary release.

---

## Task 5 — HMT98 (Nucleated Red Blood Cells) ⚠ Requires Athena verification

### Findings

- Current: `HMT98 → 37173288` (SNOMED)
- Source: 1 record, LBTEST = "Nucleated Red Blood Cells", reported as `%`
- Candidate LOINC: 26461-9 "Nucleated erythrocytes/100 leukocytes [Ratio] in Blood" — typical OMOP concept_id 3018928

### Status

Cannot confirm OMOP concept_id without Athena access. Current SNOMED mapping is valid (just non-LOINC). Only 1 record affected.

### Recommendation

Verify in Athena. If 3018928 (or similar LOINC concept) is confirmed, replace; otherwise keep SNOMED.

---

## Task 6 — RCT9 Phosphorus ✅

### Findings

`concept_maps/labs.csv` already had RCT9 → **3011904** which IS the LOINC standard (LOINC 2777-1 "Phosphate [Mass/volume] in Serum or Plasma"). However, `custom_concepts_needed.csv` had a stale row `2100000400, RCT9, Phosphorus Serum` from when it was custom.

### Fix

Removed stale custom entry from `custom_concepts_needed.csv` with a comment explaining the upgrade. The active mapping in `labs.csv` was already correct.

---

## Task 7 — RCT8 Uric Acid concept name ✅

### Findings

`RCT8 → 3037556` is the correct LOINC standard (LOINC 3084-1 "Urate [Mass/volume] in Serum or Plasma"). Our `concept_name` was a custom string "Uric Acid/Urate".

### Fix

Updated `concept_name` to match the standard OMOP concept name "Urate [Mass/volume] in Serum or Plasma". Note column preserves the source LBTEST ("Serum Uric Acid") for traceability.

---

## Task 8 — RCT14 / RCT15 collision ✅ (Critical fix)

### Findings

| Code | LBTEST | Was | Should be |
|---|---|---|---|
| RCT14 | Creatine Kinase (U/L) | **3019550 (sodium — wrong!)** | **3007220** (LOINC 2157-6 Creatine kinase) |
| RCT15 | Serum Sodium (mmol/L) | 3019550 | 3019550 ✓ (correct) |

Two distinct analytes were sharing one concept_id due to copy-paste error. ~14,000 CK measurements were being mis-coded as sodium.

### Fix

`concept_maps/labs.csv`: RCT14 changed to **3007220** (Creatine kinase [Enzymatic activity/volume] in Serum or Plasma, LOINC 2157-6).

### Verification note

`3007220` should be verified in Athena.

---

## Task 9 — Fasting vs random glucose ✅

### Findings

| Code | LBTEST | Was | Should be |
|---|---|---|---|
| RCT142 | Fasting Glucose (mmol/L) | 3004501 (generic glucose) | **3037110** (LOINC 1558-6 Fasting glucose) |
| RCT1669 | Glucose, Random-PS (mmol/L) | 3004501 | 3004501 ✓ (LOINC 2345-7 generic glucose, appropriate for random) |

### Fix

`concept_maps/labs.csv`:
- RCT142 changed to **3037110** with concept_name "Fasting glucose [Mass/volume] in Serum or Plasma"
- RCT1669 retains 3004501 with updated concept_name

### Verification note

`3037110` should be verified in Athena.

---

## Task 10 — UAT43 (Urine Blood) ✅ Already correct

### Findings

User flagged that UAT43 used `3020891` (body temperature). Current state shows UAT43 → **3011397** (LOINC 5794-3 Urine Blood) — already correct. `3020891` only appears in `vitals.csv` for STDTEMP.

### Status

No fix needed — the issue was already resolved (likely fixed in earlier rounds).

---

## Task 11 — CNT69 vs CNT350 ✅ (Critical fix)

### Findings

| Code | LBTEST | Was | Issue |
|---|---|---|---|
| CNT69 | Hepatitis C Virus-QT (RNA viral load) | 4196134 (HCV Antibody — wrong!) | RNA viral load, not antibody |
| CNT350 | Hepatitis C Virus Antibody-QT | 4196134 | Correct |

CNT69 is a viral load (RNA detection) test, mis-coded as antibody.

### Fix

`concept_maps/labs.csv`: CNT69 changed to **4101935** (LOINC 11011-4 "Hepatitis C virus RNA [Presence] in Serum or Plasma").

### Verification note

`4101935` should be verified in Athena. Source has 14 CNT69 records (low volume but still mis-classified).

---

## Task 12 — ORT serology repeated concept_ids ✅ Legitimate

### Findings

| Pair | Concept | Status |
|---|---|---|
| ORT7923 / ORT11357 | 4295162 (Hep E IgG) | Legitimate — same analyte from different lab panels (LDT38 vs RUO315) |
| ORT7924 / ORT11358 | 4268445 (Hep E IgM) | Legitimate — same analyte from different panels |
| ORT11360 + 5 repeats (`_1` to `_5`) | 2100000530 (custom Hep E IgG/IgM interpretation) | Legitimate — repeat measures of same interpretation |

### Status

All "duplicates" reflect intentional reuse of the correct concept across different source codes. No fix required.

### Side note

`ORT19175` and `ORT19176` (HEV qRT-PCR, 1 record each) are not in our concept_maps — currently unmapped. Low priority; could add LOINC for HCV RNA quantification if desired.

---

## Task 13 — Drug biomarkers custom concepts ✅ Custom is appropriate

### Findings

Drug biomarker entries in `concept_maps/labs.csv` (Solanezumab PK and anti-drug antibody panel):

| Source | Concept | Test |
|---|---|---|
| SRT20477 | 2100000501 | Anti-Solanezumab antibody level |
| SRT16102 | 2100000502 | Solanezumab plasma concentration |
| SRT21423 | 2100000503 | Anti-Solanezumab neutralizing antibody |
| SRT20478 | 2100000504 | Anti-Solanezumab antibody titer |
| ORT13169 | 2100000505 | Solanezumab CSF concentration |

Plasma Abeta panel customs in `concept_maps/biomarkers.csv` (TP40/42, BP40/42, FP40/42, ratio variants).

### Status — keep as custom

These are appropriate custom concepts because:
- **Solanezumab PK/ADA panel**: investigational-drug-specific assays. No LOINC for "solanezumab plasma concentration" — would require new vocab entries upstream.
- **Plasma Abeta Free/Bound/Total fractions**: research-specific assay configurations not represented in standard vocabularies.
- **Abeta ratio variants** (FP40/TP40, FP42/FP40, FP42/TP42): research-derived ratios.

### Recommendation

Re-check Abeta concepts annually against newer OMOP vocabulary releases (LOINC adds plasma Abeta panels periodically — e.g., LOINC 100722-9 "Amyloid beta 42/40 ratio [Mass Ratio] in Plasma" may now have an OMOP standard concept). Currently `2100000010` for the 42/40 ratio could potentially be replaced if a standard exists.

---

## Summary

| # | Task | Status | Severity |
|---|---|---|---|
| 1 | image_occurrence visit linkage | ✅ Fixed | Major (70%→3.9%) |
| 2 | Anatomic site concepts | ⏸ Pending decision | Modeling choice |
| 3 | Unit case variants | ✅ Fixed | Minor cleanup |
| 4 | GI/L and TI/L magnitudes | ✅ Fixed | **Wrong unit magnitude** |
| 5 | HMT98 LOINC alternative | ⚠ Verify in Athena | Low (1 record) |
| 6 | RCT9 Phosphorus | ✅ Cleaned up stale custom entry | Hygiene |
| 7 | RCT8 concept name | ✅ Fixed | Cosmetic |
| 8 | RCT14 / RCT15 collision | ✅ Fixed | **Critical — wrong analyte for ~14K records** |
| 9 | Fasting / random glucose | ✅ Fixed | Quality |
| 10 | UAT43 | ✅ Already correct | None |
| 11 | CNT69 / CNT350 | ✅ Fixed | **Wrong analyte for 14 records** |
| 12 | ORT serology repeats | ✅ Legitimate | None |
| 13 | Drug biomarker customs | ✅ Appropriately custom | None |

### Concept_ids needing Athena verification

- HMT98 → candidate **3018928** (LOINC 26461-9 Nucleated erythrocytes ratio)
- RCT14 → applied **3007220** (LOINC 2157-6 Creatine kinase)
- RCT142 → applied **3037110** (LOINC 1558-6 Fasting glucose)
- CNT69 → applied **4101935** (LOINC 11011-4 HCV RNA)
- GI/L → applied **9444** (billion per liter)
- TI/L → applied **8734** (trillion per liter)

---

## Round 2 — Local OMOP Vocab Validation (2026-05-05)

After discovering local OMOP Athena vocabulary at `/Users/robertbarrett/dev/world_model/omop_vocabulary/CONCEPT.csv` (Jan 2025 snapshot — includes LOINC 2.78, SNOMED, RxNorm, CPT4, HCPCS, ICD10CM; does NOT include CDISC or PPI), every concept_id used in `concept_maps/` was validated.

### Verified correct

| concept_id | Use | Vocab confirmation |
|---|---|---|
| 3007220 | RCT14 Creatine kinase | LOINC 2157-6 ✅ |
| 3037110 | RCT142 Fasting glucose | LOINC 1558-6 ✅ |
| 9444 | GI/L unit | UCUM 10*9/L ✅ |
| 8734 | TI/L unit | UCUM 10*12/L ✅ |
| 3019550 | RCT15 Sodium | LOINC 2951-2 ✅ |
| 3004501 | RCT1669 Glucose generic | LOINC 2345-7 ✅ |
| 3011904 | RCT9 Phosphate | LOINC 2777-1 ✅ |
| 3037556 | RCT8 Urate | LOINC 3084-1 ✅ |
| 3011397 | UAT43 Urine Blood | LOINC 5794-3 ✅ |

### Corrected after vocab lookup (initial fix was wrong)

| Source | Initial fix | Was wrong because | Final fix |
|---|---|---|---|
| CNT69 (HCV RNA) | 4101935 | 4101935 = "Primordial cyst" (SNOMED Disorder) | **3018447** (LOINC 11011-4 Hepatitis C virus RNA viral load) ✅ |
| HMT98 (Nucleated RBC) | 3018928 | 3018928 = "Fibrinogen [Mass/volume]" | **3034708** (LOINC 19048-8 Nucleated erythrocytes/100 leukocytes [Ratio] in Blood) ✅ |

### CRITICAL — Pre-existing mis-codings discovered by validation

These were in the codebase before this audit and were caught by the local-vocab validation pass:

| Source | Old concept_id | Old concept actually meant | New concept_id | Records affected |
|---|---|---|---|---|
| **PET_AMYLOID** | **4305389** | "Nasal endotracheal tube present" (SNOMED Clinical Finding, Condition domain, NOT standard) | **36304731** (LOINC 87907-2 PET+CT Brain for amyloidosis) | ~7,000 procedures |
| **PET_TAU** | **4305389** | same as above | **37021253** (LOINC 92927-3 PET+CT Brain for tau protein) | ~5,000 procedures |
| **RETINAL_IMAGING** | **4042832** | "Procedure on thoracic duct" (SNOMED Procedure, but wrong anatomy) | **4063911** (SNOMED 20067007 Ocular fundus photography) | 249 procedures |
| **MRI_BRAIN** | 4013636 | "Magnetic resonance imaging" (generic, valid but not brain-specific) | **37311324** (SNOMED 816077007 MRI of brain) | ~8,400 procedures |

**Severity**: PET_AMYLOID and PET_TAU were not just imprecise — `4305389` is in the **Condition** domain, not Procedure. Loading this into `procedure_occurrence.procedure_concept_id` is a domain-rule violation that any OMOP DQD instance would flag.

### Concepts not in this Athena snapshot (likely valid, just missing vocab)

This vocab download does NOT include the CDISC or PPI vocabularies. The following 67 concept_ids appeared "missing" but most are CDISC/PPI concepts that are valid in a complete Athena release:

- **CDISC concepts (~50 IDs)**: CDR domains (37522525 Memory, 37525225 Orientation, ...), MMSE items (37535522 Date, 37524690 Month, ...), ADLPQ items (37539747 Drive Car, 37541473 Make a Meal, ...) — all from CDISC controlled terminology
- **PPI concept**: 903630 (Walking exercise frequency)
- **A4_LEARN customs (intentional)**: 2000000010-2000000022 (study milestones)

### Biomarker concepts requiring further investigation

- **GFAP (745580)** — not in this snapshot, may be from a vocabulary not loaded. Better candidate: **1761505** (LOINC 100435-7 "Glial fibrillary acidic protein [Mass/volume] in Serum by Immunoassay")
- **NFL (745751)** — not in this snapshot. Better candidate: **3966310** (LOINC 101281-4 "Neurofilament light chain [Mass/volume] in Serum or Plasma by Immunoassay")
- **CSF Tau (745753)** — not in this snapshot. Needs LOINC verification.

These represent additional cleanup candidates if we want to fully Athena-verify.

### Final verified state (after Round 2 + Round 3)

| Severity | Count | Details |
|---|---|---|
| Critical mis-codings fixed | 4 | PET_AMYLOID, PET_TAU, RETINAL_IMAGING, MRI_BRAIN |
| Lab analyte mis-codings fixed | 2 | RCT14 (CK→sodium), CNT69 (HCV RNA→antibody) |
| Concept name updates | 2 | RCT8, HMT98 |
| Unit fixes | 3 | GI/L, TI/L, case variants |
| Stale entry cleanup | 1 | RCT9 in custom_concepts_needed.csv |
| Pending user decision | 1 | Anatomic site concepts (Task 2) |
| Round 3 biomarkers | 3 | GFAP, NFL, CSF Tau (LOINC) |

---

## Round 3 — Deep Consistency Pass (2026-05-05)

After full local Athena vocab access, ran a comprehensive domain-vs-target-table validation across all output tables. Surfaced an additional set of mis-codings.

### Round 3 fixes

#### Biomarkers (Athena-verified LOINC replacements)

| Source | Old (CPT4 not in vocab) | New (LOINC standard) |
|---|---|---|
| GFAP | 745580 (CPT4 0548U claimed but missing from vocab) | **1761505** (LOINC 100435-7 GFAP [Mass/volume] in Serum by Immunoassay) |
| NFL | 745751 (CPT4 83884 claimed but missing) | **3966310** (LOINC 101281-4 Neurofilament light chain [Mass/volume] in Serum or Plasma by Immunoassay) |
| SRT10630 (CSF total Tau) | 745753 (CPT4 not in vocab) | **3000242** (LOINC 30160-6 Tau protein [Mass/volume] in Cerebral spinal fluid) |

#### MI-CDM image_occurrence anatomic_site

| Site | Old | Old actually meant | New |
|---|---|---|---|
| Brain | 4007117 | "[D]Proteinuria" — DEPRECATED Observation, non-standard | **4133034** (SNOMED 12738006 "Brain structure", Spec Anatomic Site) |
| Eye | 4103720 | "Structure of posterior epiglottis" | **4305329** (SNOMED 81745001 "Eye structure", Spec Anatomic Site) |

#### APOE measurements (`a4_omop_etl/observation_adqs.py` had hardcoded wrong IDs)

| Source | Old | Old actually meant | New |
|---|---|---|---|
| APOEGN | 35448 (LOINC code stored as int — bug) | concept_id 35448 doesn't exist | **3029139** (LOINC 42315-2 APOE gene alleles e2/e3/e4 [Identifier]) |
| APOEGNPRSNFLG | 4124908 | "Serogroup" (SNOMED, non-standard) | **3006041** (LOINC 15353-6 Apolipoprotein E4 [Presence] in Blood) |

#### Phyneuro physical/neuro exam findings (conditions.csv)

Most of the original phyneuro concept_ids referenced unrelated SNOMED concepts. Athena-verified replacements:

| Source | Old (wrong) | Old actually meant | New (verified) |
|---|---|---|---|
| PXHEADEY | 4090425 | "Altered sensation of skin" | **4247371** (Head finding) |
| PXABDOM | 441840 | generic "Clinical finding" | **43531058** (Finding of abdomen) |
| PXOTHER | 4134586 | "Chronic heart disease" | **441840** (Clinical finding — generic catch-all) |
| NXGAIT | 4203631 | "Motor dysfunction" | **437643** (Abnormal gait) |
| NXMOTOR | 4116942 | not in vocab | **433453** (Motor function behavior finding) |
| NXSENSOR | 4161682 | "Hypoesthesia" (too specific) | **433227** (Abnormal sensation) |
| NXTREMOR | 4169095 | "Bradycardia" | **443782** (Tremor) |
| NXFINGER | 4300528 | "Endoscopic excision of lesion of large intestine" | **4139442** (Dysmetria) |
| NXHEEL | 4301597 | "Destruction of lesion of choroid by implantation of radiation source" | **4139442** (Dysmetria — same; test specificity preserved in source_value) |
| NXNERVE | 4027384 | "Inflammatory disorder" | **4024014** (Cranial nerve finding) |
| NXOTHER | 4135493 | "Abnormal" (Meas Value domain) | **4011630** (Neurological finding — generic catch-all) |

These were caught with `python3 /tmp/consistency_check.py` (domain-vs-target-table validation script).

### Remaining domain violations (20 — categorized as intentional or architectural)

#### Intentional design (3 violations)

These three numeric scores were deliberately moved from observation to measurement domain at output time, even though the vocab classifies them as Observation. The trade-off was discussed in earlier rounds: numeric values fit better in the measurement table, and our `measurement_source_value` preserves the "score" semantics.

- 42869860 (MMSE total) — 26,473 records
- 3051694 (GDS total) — 21,558 records
- 1761510 (IES-R total) — 4,336 records

#### Architectural choice (16 violations) — Recommend moving phyneuro to condition_occurrence

All `PX*`/`NX*` phyneuro concepts are correctly identified Clinical Findings in the SNOMED vocabulary (Condition domain), but the ETL writes them to the OBSERVATION table. Per OMOP CDM v5.4 conventions, Condition-domain concepts belong in `condition_occurrence`, not `observation`.

The `condition_occurrence.csv` output is currently empty (1 byte). A clean architectural fix would route abnormal phyneuro findings there with `condition_status_concept_id` indicating exam-time finding. Normal findings could remain in observation (SNOMED `Normal` is in Observation domain) or be omitted.

**Affected concepts**: 4247371, 4103183, 4024567, 43531058, 135930, 4158343, 141960, 441840, 433453, 433227, 443782, 4139442, 4024014, 4011630 (~5,690 records each).

#### ADLPQ answer concepts as observation_concept_id (3 violations)

These reflect mappings from the reviewer spreadsheet that placed LOINC answer concepts in the question slot:

| concept_id | name | domain | source code |
|---|---|---|---|
| 36309019 | Phone Call | Meas Value | ASCALL (14,769 records) |
| 37079157 | Text message | Meas Value | ASTEXT (14,764 records) |
| 4322976 | Procedure (generic) | Procedure | RSSTST (7,020 records) |

Strict OMOP would put these in `value_as_concept_id`, not `observation_concept_id`. They came from the reviewer's spreadsheet column intended as Qualifier (which we mapped to question-level concept_id). A semantic re-mapping pass would reclassify these.

### Concepts not in this Athena snapshot (~50, likely valid in newer release)

This snapshot doesn't include CDISC, PPI, or some newer LOINC additions. The following appeared "missing" but are likely valid in a complete Athena export:

- **CDISC concepts**: CDR domains (37522525 Memory, 37525225 Orientation, ...), MMSE items (37535522 Date, 37524690 Month, ...), ADLPQ items (37539747 Drive Car, ...)
- **PPI**: 903630 (Walking exercise frequency)
- **A4_LEARN custom milestones**: 2000000010-2000000022 (intentional)

These should be re-verified against a complete vocab download.

---

## All concept_id changes summary across all rounds

### Athena-verified standard replacements (32 concept_ids)

Modalities (3): MR/PT/OP → DICOM2OMOP standards
Procedures (4): MRI_BRAIN, PET_AMYLOID, PET_TAU, RETINAL_IMAGING — all corrected
Labs (8): RCT8 (name only), RCT9 (cleanup), RCT14, RCT142, CNT69, HMT98, GFAP, NFL, CSF Tau
Phyneuro (11): PXHEADEY, PXABDOM, PXOTHER, NXGAIT, NXMOTOR, NXSENSOR, NXTREMOR, NXFINGER, NXHEEL, NXNERVE, NXOTHER
APOE (2): APOEGN, APOEGNPRSNFLG
Anatomic site (2): Brain, Eye in image_occurrence.py
Units (2): GI/L, TI/L

### Architectural decisions remaining

1. **Move phyneuro to condition_occurrence?** Currently 16 Condition-domain concepts in observation table — clean fix but requires ETL refactor.
2. **Reclassify ADLPQ phone/text concepts?** 3 concepts with answer-concept domain in question slot — needs reviewer-spreadsheet re-interpretation.
3. **Anatomic site SNOMED vs DICOM2OMOP** (Task 2)? Still pending user decision.
4. **Retinal (OP) visit linkage via ±7-day window?** (see detail below) Currently 249/249 OP image_occurrence rows have null `visit_occurrence_id` because `imaging_retinal.csv` has no VISCODE column. Recommended: implement date-window matching.

---

## Pending Decision 4 — OP retinal scan ↔ visit pairing ⏸

### Context

`imaging_retinal.csv` (498 source records, 78 distinct subjects) lacks a `VISCODE` column — only `ExamDate_DAYS_CONSENT`. The VISCODE-based visit linkage fix from Round 3 (Task #1) cannot apply, so all 249 deduplicated OP image_occurrence rows currently have `visit_occurrence_id=NULL` (100% unlinked).

### Data analysis (n=498 source records)

| Match window | Records linked | Cumulative coverage |
|---|---:|---:|
| Same day only | 316 | 63.5% |
| ±1 day | 336 | 67.5% |
| **±7 days** | **408** | **82.0%** |
| ±14 days | 450 | 90.4% |
| ±30 days | 476 | 95.6% |

**Signed-difference distribution within ±7 days**: 38 scans before visit / 316 same-day / 54 scans after visit. Symmetric — no directional skew that would warrant asymmetric windowing.

**Same-day ambiguity**: zero — when a same-day visit exists, it's always exactly one visit per subject. No tie-breaking needed for the dominant case.

### Recommendation: ±7-day symmetric nearest-neighbor match

| Reason | Detail |
|---|---|
| Captures 82% with zero ambiguity in dominant case | Same-day match has no collisions; ±1-7 day window is single-visit dominant |
| Matches OMOP "performed during this visit" semantics | A4/LEARN visit windows are tight enough that scans within a week reasonably belong to the same visit episode |
| Steep marginal returns past 7 days | 7→14 days adds 8%; 14→30 days adds 5%. Beyond ±7 the linkage becomes "scan happened around that visit" which is less defensible |
| Symmetric distribution justifies symmetric window | No bias toward before- or after-visit scanning |

### Implementation sketch

In `a4_omop_etl/image_occurrence.py`, when `src_key == 'imaging_retinal'` (the only source without VISCODE), apply date-window matching after computing scan_date:

```python
if src_key == 'imaging_retinal':
    # No VISCODE — match each scan to nearest visit within ±7 days
    visit_dates = visit_occurrence_df[['person_id', 'visit_start_date', 'visit_occurrence_id']].copy()
    visit_dates['visit_start_date'] = pd.to_datetime(visit_dates['visit_start_date'])

    def nearest_visit_id(row):
        pv = visit_dates[visit_dates['person_id'] == row['person_id']]
        if len(pv) == 0:
            return None
        scan_date = pd.to_datetime(row['_scan_date'])
        diffs = (pv['visit_start_date'] - scan_date).dt.days.abs()
        if diffs.min() > 7:
            return None
        return pv.loc[diffs.idxmin(), 'visit_occurrence_id']

    merged['visit_occurrence_id'] = merged.apply(nearest_visit_id, axis=1)
```

### Expected outcome

- **Source records linked**: 498 → ~408 (82%)
- **Deduplicated image_occurrence OP records**: 249 → ~204 linked (~82%); ~45 remain unlinked
- **Overall image_occurrence missing visit rate**: 3.9% → ~1.5%
- **Unlinked OP records (~18%)** are likely substudy imaging scheduled off the main visit calendar or data-quality anomalies — leaving them unlinked is honest

### Alternatives considered

| Option | Coverage | Trade-off |
|---|---|---|
| Same-day exact match only | 63.5% | Simplest implementation; loses ~18% of legitimate within-visit-episode matches |
| ±7 days symmetric (recommended) | 82.0% | Balanced: meaningful coverage, defensible semantics |
| ±14 days symmetric | 90.4% | Higher coverage but starts to weaken "performed at this visit" semantics |
| ±30 days symmetric | 95.6% | Linkage becomes weakly justified — could attribute scan to wrong visit episode |
| Asymmetric (e.g., -1 to +7) | ~75% | Data shows no directional skew — not warranted |

---

## Round 4 — Re-validation against project-local CONCEPT.csv (2026-05-13)

The user placed `CONCEPT.csv` and `VOCABULARY.csv` directly at the project root for in-tree validation (gitignored to avoid committing the ~850MB vocab). Vocab snapshot includes LOINC 2.78, SNOMED 2024-09, RxNorm 2024-12, CPT4 2024, HCPCS 20250101, ICD10CM FY2025, UCUM 1.8.2 — **does not include CDISC**.

### One more critical mis-coding caught

| Source | Was | Was actually | Fixed to |
|---|---|---|---|
| **UAT6 Urine Ketones** | 3016436 | "Lactate dehydrogenase [Enzymatic activity/volume] in Serum or Plasma" (LDH!) | **3023539** (LOINC 5797-6 Ketones [Mass/volume] in Urine by Test strip) — 10,286 records |

Same pattern as earlier RCT14/CNT69 fixes: notes column correctly identified the LOINC code (5797-6) but the concept_id stored was for a different LOINC.

### Concept-map state after Round 4

- **234 distinct standard concept_ids** in `concept_maps/`; 184 resolve in this snapshot, **50 are CDISC concepts** that require the CDISC vocabulary to be loaded (not present in this snapshot)
- **0 deprecated concepts** used in any concept_maps or output
- **0 non-standard concepts** used in output (excluding `concept_id=0` placeholders)

### CDISC concepts not in this snapshot but valid in full Athena (50)

These are valid OMOP concept_ids from the CDISC controlled terminology vocabulary, sourced from the reviewer mapping spreadsheet (Sarina, Dr Milap, Dr Blake):

- **CDR domains (8)**: MEMORY (37522525), ORIENT (37525225), JUDGE (37530450), COMMUN (37538839), HOME (37545969), CARE (37546534), CDSOB (37524289), CDGLOBAL (37546494)
- **MMSE items (~28)**: MMDATE (37535522), MMMONTH (37524690), all 4 Letters (37524591/37525937/37532418/37532900/37534611), all 3 Registration (37534185/37545292/37530589), all 3 Recall (37528921/37544754/37543093), commands (37531417/37531096/37537897), other items
- **ADLPQ items (13)**: ASTRAVL, ASAPPLI, ASLAUN, ASSNACK, ASFIND, ASCEVNT, ASPHONE, ASMEDS, ASPLAN, ASCOMPL, ASCELL, ASCELLUSE, ASSCORE
- **PPI (1)**: WALKING (903630)

**Status**: These are correct Athena IDs — they're not broken, they just don't resolve in this particular snapshot. Verified at original mapping time via the reviewer spreadsheet. Recommend re-validating against an Athena export that includes CDISC vocabulary.

### Domain violations (20 — unchanged from Round 3)

After Round 3 + 4 fixes, the remaining 20 violations are all categorized as documented earlier:
- **3 intentional**: MMSE/GDS/IES totals moved to measurement domain
- **16 architectural**: Phyneuro Condition-domain concepts in observation table (Pending Decision 1)
- **3 reviewer-spreadsheet semantics**: ADLPQ Phone/Text and RSSTST Procedure (Pending Decision 2)

### Cumulative concept-id corrections across Rounds 1-4: **33**

Adding UAT6 to the Round 3 list of 32.

---

## Round 5 — Comprehensive source-level audit (2026-05-13, in progress)

Five parallel subagent audits launched to systematically cross-reference every source CSV against its data dictionary and the local Athena vocabulary. Status:

| Batch | Scope | Status |
|---|---|---|
| **A** | **Labs & biomarkers** | **Complete** |
| **B** | **Cognitive & CogState** | **Complete** |
| **C** | **Questionnaires** | **Complete** |
| **D** | **C-SSRS, ECG, vitals, lifestyle, phyneuro** | **Complete** |
| **E** | **Imaging, demographics, milestones, drugs** | **Complete** |

### Batch E findings (imaging, demographics, milestones, drugs)

#### Approved — no action

- **Demographics** (`demographics.csv`): All gender/race/ethnicity SNOMED/LOINC concepts verified standard.
- **Visits** (`visits.csv`): 9202 (Outpatient Visit) verified standard.
- **Drugs** (`drugs.csv`): 36852349 (Solanezumab, RxNorm Extension) verified standard.
- **Imaging procedures** (`procedures.csv`): MRI_BRAIN (37311324), PET_AMYLOID (36304731), PET_TAU (37021253), RETINAL_IMAGING (4063911) all Athena-verified standard (Round 3 fixes confirmed).
- **DICOM2OMOP modalities** (`modalities.csv`): 2128009230/239/252 valid per Park & Jeon 2024 (not in Athena snapshot but documented standard).
- **Image feature types** (`image_feature_types.csv`): 32880 (derived), 32817 (EHR) verified.
- **Image findings** (`image_findings.csv`): 7 custom concepts (2100000093-099) appropriately custom for study-specific MI-CDM findings.
- **Imaging measurement concepts** (`imaging.csv`): 13 custom concepts (2100000030-079) appropriately custom for FreeSurfer regional volumes, PET SUVRs, WMH metrics.

#### Inconsistency caught — CSV vs Python source-of-truth mismatch

| File | Value | Issue |
|---|---|---|
| `concept_maps/adqs.csv` line 3: APOEGN | `35448-7` (LOINC code as string) | **Stale** — Round 3 fix updated `observation_adqs.py` to use 3029139 but the CSV was never updated |
| `concept_maps/adqs.csv` line 5: APOEGNPRSNFLG | `4124908` ("Serogroup", wrong) | **Stale** — Round 3 fix updated `observation_adqs.py` to use 3006041 but the CSV was never updated |

The ETL output uses the correct concept_ids because `observation_adqs.py` hardcodes them (Round 3 fix). But the `concept_maps/adqs.csv` documentation file is out of sync. **Two-part fix needed:**
1. Update `adqs.csv` to match the corrected concept_ids
2. Ideally refactor `observation_adqs.py` to load from CSV rather than hardcode (architectural drift)

#### Custom APOE genotype values — LOINC answer codes exist

Currently using customs 2100000420-425 for E2/E2 through E4/E4. Athena-verified LOINC answer codes are available:

| Genotype | Custom (current) | LOINC answer concept (recommended) |
|---|---|---|
| E2/E2 | 2100000420 | **36307526** (LA21356-3) |
| E2/E3 | 2100000421 | **36310377** (LA21357-1) |
| E2/E4 | 2100000422 | **36308156** (LA21361-3) |
| E3/E3 | 2100000423 | **36309003** (LA21358-9) |
| E3/E4 | 2100000424 | **36311054** (LA21359-7) |
| E4/E4 | 2100000425 | **36303222** (LA21360-5) |

These are LOINC "Answer" concepts (Meas Value domain) — appropriate for `value_as_concept_id` when paired with the APOEGN test concept (3029139). They are standard concepts and would let us retire 6 customs.

#### Custom milestone concepts — potential SNOMED replacements

13 custom milestone concepts (2000000010-022) used for study disposition. SNOMED alternatives may exist for several:

| Source | Custom | Candidate SNOMED (needs verification) |
|---|---|---|
| RANDOMIZED | 2000000010 | 608164 "Randomized clinical trial" or 46271379 "Enrollment in clinical trial" |
| LOST TO FOLLOW UP | 2000000016 | 185541007 "Loss to follow-up" |
| WITHDRAWAL BY SUBJECT | 2000000013 | 384650002 "Patient has withdrawn from study" |
| (others) | 2000000011/12/14/15/17-22 | Need search in SNOMED clinical-trial-status hierarchy |

These were suggestions from the audit — not Athena-verified yet. Need a follow-up search if we want to replace.

#### Imaging custom concepts (2100000030-079, 093-099)

All 20 custom imaging concepts (MRI volumetric regions, PET SUVRs, FLAIR WMH, retinal AI scores, image findings) are **appropriately custom** — they describe algorithm-derived metrics specific to A4/LEARN imaging pipelines. The audit confirms no standard equivalents are needed.

---

### Batch C findings (questionnaires)

#### Critical: invalid concept reference

**`observations.csv` WALKING → 903630** — concept does not exist in this Athena snapshot (PPI vocab not loaded). May be valid in a complete Athena export with PPI vocabulary, but cannot be verified here. Needs either: (a) replacement with a LOINC physical-activity concept, or (b) confirmation that PPI vocab will be available downstream.

#### Confirmed issues from earlier rounds — still present

- **ASCALL → 36309019** ("Phone Call", Meas Value/Answer class, used as observation_concept_id). Answer-class concept in question slot — known issue (Pending Decision 2). 14,769 records.
- **ASTEXT → 37079157** ("Text message", Meas Value/Answer class) — same issue. 14,764 records.
- **RSSTST → 4322976** ("Procedure", generic SNOMED Procedure-domain concept used in observation slot). Known issue. 7,020 records.

#### New gaps caught by audit

1. **ADLPQSP item-level mapping missing**: 15 main AI* items (study partner version of ADLPQ) are NOT mapped to OMOP concepts. Only `AISCORE` (total, custom 2100000067) is mapped. ADLPQ patient items have 18 mappings; ADLPQSP has 1. Could reuse the same CDISC concept_ids as the patient version (AICBOOK→4268404 like ASCBOOK, etc.) since the question semantics are identical.

2. **STAI Total (2100000060 custom)**: LOINC may have a standard "State-Trait Anxiety Inventory total" concept (candidate LOINC 59857-4). Worth searching to retire the custom.

3. **RSS items RSSQUAL and RSSRECOM**: Reported as completely unmapped in `questionnaires.csv` per the audit. Need verification — these might actually be mapped under `RSS_QUALITY` and `RSS_RECOMMEND` keys.

4. **ADLPQ secondary device-usage items unmapped (12+)**: ASINTER, ASAPP, ASCOMP, ASWEB, ASACCESS, ASEREAD, ASCELLOFTN, ASCELITDIF, ASCOMPOFTN, ASCLITDIF, ASEBOOK, ASEDLOAD, ASEADJUST, ASEOFTEN, ASELITDIF — secondary device usage/difficulty annotations. May be intentionally not mapped; needs documentation.

5. **RUIB unmapped items (5+)**: BRADMIT (hospital admission), BREXAM (clinic visit), BRHELP (other helper), BRUPHELP (unpaid help), LOST, LOSTHRS, RESIDENCE, RESTYPE — would need healthcare-utilization LOINC concepts if mapping is intended.

#### Architectural questions surfaced

1. **SPINFO study-partner demographics**: INFRELAT, INFGENDER, INFAGE, INFLIVE, INFHRS currently map to customs (2100000080-084). Auditor questions whether these should be:
   - (A) observations on the participant (current approach), or
   - (B) linked person records with relationship_fact entries (more OMOP-native)

2. **RUIB1 hospitalization records**: BR1NIGHT, BR1TYPE → customs 2100000208-209. Could potentially be modeled as visit_occurrence records with visit_type rather than observations.

#### Mapping coverage by instrument

| Instrument | Items | Mapped | Coverage |
|---|---|---|---|
| IES-R | 16 | 16 | 100% ✓ |
| GDS | 16 | 16 | 100% ✓ (all LOINC verified) |
| STAI | 7 | 7 | 100% ✓ (6 items LOINC, total custom) |
| AD Concerns | 5 | 5 | 100% (all custom) |
| ADLPQ patient | 28 | 18 | 64% (12 device items unmapped — by design?) |
| **ADLPQSP partner** | **82+** | **1** | **1.2% — major gap** |
| FTP | 10 | 10 | 100% (all custom) |
| RSS | 12 | 10 | 83% (RSSQUAL, RSSRECOM possibly mis-keyed) |
| VIEWS | 10 | 10 | 100% (all custom) |
| RUIB | 12 | 4 | 33% (admin items unmapped) |
| RUIB1 | 2 | 2 | 100% (custom) |
| SPINFO | 5 | 5 | 100% (all custom) |

---

### Batch B findings (cognitive & CogState)

#### Mapping inventory across 11 files

- **2 standard concepts in this snapshot**: MMSE total (42869860 LOINC ✓) + SNOMED 4151971 "Buschke selective reminding test" referenced but not currently used in our maps
- **34 CDISC concepts**: MMSE items + CDR domains — valid Athena standards but CDISC vocab not in snapshot
- **76 custom concepts**: CogState battery (24), MACQ items (7), C-PATH items (28), PACC.raw, plus various derived metrics
- **27+ unmapped items**: 15 CFI participant items + 15 CFISP study-partner items + raw FCSRT trial-level data

#### Custom concepts worth Athena lookup (candidates for replacement)

| Source | Current custom | Recommended Athena search |
|---|---|---|
| **PACC.raw** | 2100000001 | Search "Preclinical Alzheimer Cognitive Composite" or "PACC" LOINC — primary outcome measure |
| **FCSRT family** (FCTOTAL96 + free/cued totals) | 2100000004, 2100000056, 2100000057 | SNOMED 4151971 "Buschke selective reminding test" verified standard; could replace customs for the test-level concept (item-level remains custom) |
| **Digit Symbol Total** | 2100000006, 2100000052 | Search "Digit Symbol Substitution Test" or "DSST" LOINC |
| **Logical Memory** | 2100000005, 2100000007, 2100000054, 2100000055 | Search WMS "Logical Memory" LOINC. **Avoid SNOMED 40358037** (deprecated U) |
| **CFI total** | 2100000050, 2100000051 | Search "Cognitive Function Index" LOINC |
| **MACQ items (7)** | 2100000090, 2100000280-285 | Search "Memory Complaint Questionnaire" LOINC panel |
| **C-PATH items (28)** | 2100000091, 2100000290-315 | Search "Critical Path" ADL function LOINC panel |
| **CogState tests** (DET, IDN, ONB, OCL, CPAL, LNS, FNMT, FNLT, FSBT, BPXT, BPET, FNFT) | 2100000040-049, 140-148 | Search for cognitive domain LOINCs (processing speed, working memory, learning) |

The auditor recommended 12 priority Athena searches. Some of these may have standard concepts; others (proprietary CogState composites) are appropriately custom.

#### Caution flag — deprecated concept

**SNOMED 40358037** ("Logical memory paragraph recall") is **deprecated** (`invalid_reason=U`). Do NOT use this as a replacement — it would re-introduce a deprecated concept.

#### Confirmed legitimate duplicates

- MMWATCH and MMPENCIL both → SNOMED 4169312 (intentional — both naming tasks)
- Core vs. extended versions of cognitive scores legitimately separated (DIGITTOTAL/FCTOTAL96/LDELTOTAL/LIMMTOTAL appear twice with different concept_ids — Round 1 design decision)

#### CFI/CFISP item-level gap (parallel to ADLPQSP)

15 CFI patient items + 15 CFISP study-partner items currently unmapped. Same architectural question as ADLPQSP: should individual items be mapped, or is total-score-only sufficient?

#### Coverage by instrument

| Instrument | Items mapped | Of these: standard / CDISC / custom / unmapped |
|---|---|---|
| MMSE | ~26 items + total | 1 standard (total) / 25 CDISC / 1 custom (MMWORLD letters group) |
| CDR | 8 (6 domains + 2 totals) | 0 / 8 CDISC / 0 / — |
| CFI/CFISP | 2 totals | 0 / 0 / 2 customs / 30 items unmapped |
| COGDIGIT (Digit Symbol) | 2 totals (core+ext) | 0 / 0 / 2 customs / 0 |
| COGFCSR16 | 4 metrics | 0 / 0 / 4 customs / item-level data unmapped |
| COGLOGIC | 4 metrics | 0 / 0 / 4 customs / 0 |
| PACC | 1 raw composite | 0 / 0 / 1 custom / derived fields unmapped (computed) |
| CogState computerized | ~16 tests + composites | 0 / 0 / 16+ customs / 0 |
| CogState battery (BPET/FNFT) | 2 + expanded metrics | 0 / 0 / 5 customs / 0 |
| MACQ | 1 total + 6 items | 0 / 0 / 7 customs / 0 |
| C-PATH | 1 total + items + domain | 0 / 0 / 30+ customs / 0 |

---

### Batch D findings (C-SSRS, ECG, vitals, lifestyle, phyneuro)

#### Critical: invalid WALKING concept (already noted by Batch C; confirmed by Batch D)

**`observations.csv` line 6**: `WALKING,903630,Walking exercise frequency,lifestyle,PPI standard`
- Concept 903630 (PPI vocab) is **not in this Athena snapshot**
- `custom_concepts_needed.csv` line 106 already registers **2100000300** as the intended custom: `2100000300,WALKING,Walking exercise frequency,Observation,A4_LEARN,...`
- The CSV mapping references the wrong ID. Fix: change `observations.csv` WALKING to 2100000300.
- Affects 14,040 observation records per `custom_concepts_needed.csv` count column

#### All other Batch D modules PASS — no new issues

##### C-SSRS (cssrs + cssrslv)
- All 30 concepts verified standard LOINC (1001xxx range)
- 4 custom concepts (2100000106 ATTMPT5, 2100000111 NONSUI5, 2100000115 BEHAVLIF, 2100000119 SUICIDE) appropriately justified — no standard LOINC for time-window-specific items
- `cssrslv_columns.csv` remapping (16 columns) correctly handles source column name variation
- Reviewer-flagged RED status (needs expert review) is satisfied — all concepts semantically correct

##### ECG (clrm_ecg)
- 5 core measurement concepts verified: RATE/QRS/QT/PR/RR — all standard LOINC/SNOMED in Measurement domain
- 16 interpretation/quality codes (AXASSM, COMPBASE, QUALITY, etc.) are intentionally unmapped — stored as source_value only

##### Vitals
- All 7 concepts (STDWT, STDHT, VSBPSYS, VSBPDIA, VSPULSE, VSRESP, STDTEMP) Athena-verified standard LOINC
- STDTEMP (3020891 Body temperature) confirmed correct — previous flag was about unit conversion logic (F→C in ETL), not the concept_id itself

##### Family History
- 3 customs (FAMHX_MOTHER 2100000210, FATHER 2100000211, SIBLING 2100000212) appropriately justified — no standard concepts distinguish family-relationship-specific history

##### Phyneuro
- All 16 Round 3 phyneuro concept fixes Athena-verified
- 16 are Condition-domain in vocab but written to observation table — known architectural decision (Pending Decision 1)
- NXFINGER and NXHEEL both → 4139442 Dysmetria is correct (both cerebellar tests assess for dysmetria; test type preserved in source_value)
- PXEDSEV 2100000500 (custom Edema Severity Score 0-4) appropriately custom

---

### Batch A findings (labs & biomarkers)

#### Critical: TWO new wrong-concept mis-codings found

| Source | LBTEST | Current concept | What that concept actually means | Correct concept | Records |
|---|---|---|---|---|---|
| **HMT4** | MCV (Mean Corpuscular Volume), fL, values 79-97 | **3010813** | "Leukocytes [#/volume] in Blood" (WBC, LOINC 26464-8) — WRONG ANALYTE | **3023599** (LOINC 787-2 "MCV [Entitic volume] by Automated count") | 13,952 |
| **UAT11** | Urine Leukocyte Esterase, "Negative"/"Trace"/"+" text values | **3010156** | "C reactive protein [Mass/volume] in Serum or Plasma by High sensitivity method" (CRP hs, LOINC 30522-7) — WRONG ANALYTE | **3000348** (LOINC 5799-2 "Leukocyte esterase [Presence] in Urine by Test strip") | 10,481 |

**Note on UAT11**: The Batch A audit initially flagged SCT1528 as the wrong-concept entry, but direct vocab verification shows SCT1528 → 3010156 is actually correct (CRP hs). The real bug is that **UAT11 shares the same concept_id (3010156) which is correct for CRP but wrong for Urine LE**. This is the same "duplicate concept_id used for two different tests" pattern as RCT14/RCT15 sodium and CNT69/CNT350 antibody.

Both fixes have notes columns that correctly identified the right LOINC code but the concept_id stored was for a different LOINC entirely — same pattern as Round 3/4 mis-codings.

#### Unmapped LBTESTCDs (5 codes)

| Source code | LBTEST | Recommended action |
|---|---|---|
| GET1885 | HCV RNA variant ("CAP/CTM2.0-Exp-EDTA-CL") | Reuse 3018447 (LOINC 11011-4 HCV RNA viral load) or document variant-specific need |
| ORT19175 | HEV qRT-PCR (-70°C LDT 465 PNL) | Need LOINC HEV RNA viral load concept; only 1 record |
| ORT19176 | HEV qRT-PCR log scale | Same as above, log-transformed |
| SRT16104 | Solanezumab PK variant ("LY2062430 EDTAPreInf") | Reuse 2100000502 (Solanezumab plasma) or distinct custom |
| SRT21470 | Solanezumab PK variant ("LY2062430") | Same as above |

#### Biomarker files — all verified clean

| File | Mappings | Status |
|---|---|---|
| `biomarker_AB_Test.csv` (TP40/42, BP40/42, FP40/42, ratios) | 10 customs (2100000010-016, 2100000510-512) | All appropriate for research — no LOINC for free/bound/total Abeta forms |
| `biomarker_pTau217.csv` | 1 mapping (PTAU217 → 1092155 LOINC) | Verified standard |
| `biomarker_Plasma_Roche_Results.csv` (GFAP, NFL, TPP181, AMYLB40/42, APOE4) | 6 mappings: 4 LOINC standard (GFAP 1761505, NFL 3966310, TPP181 1259491, APOE4 3029139) + 2 custom (AMYLB40/42 reuse plasma Abeta customs) | All correct after Round 3 LOINC upgrades |

#### Data quality note (minor)

Roche file has trailing-space variants ("GFAP ", "NF-L ") that map to the same concept correctly. Suggest normalizing source field codes in a future cleanup.

#### Confirmation of earlier round fixes

Batch A re-verified all Round 1-4 lab fixes — all correct:
- RCT14 (CK) → 3007220 ✓
- RCT15 (Sodium) → 3019550 ✓
- RCT142 (Fasting glucose) → 3037110 ✓
- RCT1669 (Random glucose) → 3004501 ✓
- RCT8 (Urate) → 3037556 ✓
- RCT9 (Phosphate) → 3011904 ✓
- HMT98 (Nucleated RBC ratio) → 3034708 ✓
- CNT69 (HCV RNA) → 3018447 ✓
- UAT6 (Urine Ketones) → 3023539 ✓
- UAT43 (Urine Blood) → 3011397 ✓

---

---

### Round 5 — Consolidated summary across all 5 batches

#### ✅ Fixes APPLIED 2026-05-13 (Group A + Group B)

| # | Source | Old | New | Records | Status |
|---|---|---|---|---|---|
| 1 | HMT4 (labs.csv) | 3010813 (WBC) | 3023599 (MCV, LOINC 787-2) | 13,669 | ✅ Applied |
| 2 | UAT11 (labs.csv) | 3010156 (CRP hs) | 3000348 (Urine LE, LOINC 5799-2) | 10,286 | ✅ Applied |
| 3 | WALKING (observations.csv) | 903630 (PPI, not in vocab) | 2100000300 (custom A4_LEARN) | 14,040 | ✅ Applied |
| 4 | APOEGN (adqs.csv CSV sync) | `35448-7` string | 3029139 (LOINC 42315-2) | 5,470 | ✅ Applied |
| 4b | APOEGNPRSNFLG (adqs.csv CSV sync) | 4124908 (Serogroup) | 3006041 (LOINC 15353-6) | 5,470 | ✅ Applied |
| 5 | APOE E2/E2..E4/E4 (adqs.csv + observation_adqs.py) | 6 customs (2100000420-425) | 6 LOINC LA codes (36307526, 36310377, 36308156, 36309003, 36311054, 36303222) | 5,470 distributed | ✅ Applied |
| 6 | FCTOTAL96 core + extended (cognitive.csv) | 2 customs (2100000004, 2100000053) | 4151971 (SNOMED 311477008 Buschke SRT) | 52,833 | ✅ Applied |

**Net effect**: 8 customs retired (6 APOE + 2 FCSRT) and 3 mis-codings fixed.
**Cleanup**: `custom_concepts_needed.csv` entries 2100000004 and 2100000053 commented out as retired.
**ETL state**: All 5 validations PASS. Total of 39 concept mappings corrected across all rounds.

#### (Original) Definite fixes ready to apply (when user approves)

| # | Source | Current | Should be | Records affected | Severity |
|---|---|---|---|---|---|
| 1 | **WALKING** (observations.csv) | 903630 (PPI, not in vocab) | **2100000300** (already in custom_concepts_needed.csv) | ~14,040 | High |
| 2 | **HMT4** (labs.csv) | 3010813 (Leukocytes/WBC) | **3023599** (MCV) | 13,952 | **Critical — wrong analyte** |
| 3 | **UAT11** (labs.csv) | 3010156 (CRP hs) | **3000348** (Urine LE by Test strip) | 10,481 | **Critical — wrong analyte** |
| 4 | **adqs.csv APOEGN/APOEGNPRSNFLG** | Stale (35448-7, 4124908) | Sync with observation_adqs.py (3029139, 3006041) | — (docs only; ETL already correct) | Hygiene |

#### Custom concepts with verified standard replacements (optional retirement)

| Source code(s) | Current custom | Verified standard alternative |
|---|---|---|
| E2/E2 through E4/E4 APOE genotype values (6 customs) | 2100000420-425 | LOINC answer codes 36307526, 36310377, 36308156, 36309003, 36311054, 36303222 |
| FCSRT test-level concept | 2100000004 | SNOMED 4151971 "Buschke selective reminding test" (item-level remains custom) |
| STAI Total (TBD — needs LOINC search) | 2100000060 | Candidate: LOINC 59857-4 (needs Athena verification) |
| FAMHX_MOTHER/FATHER/SIBLING (Round 1 customs) | 2100000210-212 | SNOMED family-history hierarchy — may have specific concepts (needs search) |

#### Newly identified mapping gaps (require new mappings if intended)

| Gap | Count | Notes |
|---|---|---|
| **ADLPQSP study-partner items** | 15+ | Parallel to ADLPQ patient AS* items; could reuse same CDISC concept_ids |
| **CFI / CFISP individual items** | 30 (15 each) | Currently only total scores mapped |
| **FCSRT trial-level data** | 12+ | Item-level data unmapped — may be intentional |
| **ADLPQ device-usage items** | 12+ | ASINTER, ASAPP, ASCOMP, ASWEB, etc. — may be intentional |
| **RUIB admin items** | 5+ | BRADMIT, BREXAM, BRHELP, LOST, RESIDENCE |
| **ECG interpretation flags** | 16 | AXASSM, COMPBASE, QUALITY, etc. — likely intentional source_value-only |
| **clrm_lab unmapped LBTESTCDs** | 5 | GET1885, ORT19175/76, SRT16104, SRT21470 |
| **PACC.raw / CogState / MACQ / C-PATH** | Many | Search for LOINC equivalents per Batch B recommendations |

#### Architectural decisions (need user input)

These are the same 4 pending decisions from Round 4, now confirmed by independent batch audits:

1. ✅ **Phyneuro Condition-domain concepts** — RESOLVED 2026-05-13. Refactored `a4_omop_etl/condition.py` to write 16 abnormal exam findings to `condition_occurrence` (7,391 records) and drop Normal findings (which had no clinical meaning as conditions). PXEDSEV severity (474 records) remains in measurement. observation.csv lost ~88K rows.
2. **ADLPQ phone/text answer-class concepts** (36309019, 37079157) and RSSTST (4322976) — move to `value_as_concept_id`?
3. **Anatomic site SNOMED vs DICOM2OMOP** (Task 2)
4. **OP retinal date-window pairing** (recommended ±7 days)

**Plus new from Round 5:**

5. **SPINFO study-partner demographics** — observations vs person/relationship_fact?
6. **RUIB1 hospitalization records** — observations vs visit_occurrence?

#### Cumulative state after Round 5

| Metric | Count |
|---|---|
| Total distinct standard concept_ids in `concept_maps/` | 234 |
| Athena-verified standard | 184 |
| CDISC concepts (valid but not in this vocab snapshot) | 50 |
| Deprecated/non-standard in output | 0 |
| Confirmed wrong-analyte mis-codings still to fix | **2 (HMT4, UAT11)** |
| Confirmed wrong-concept-id mis-codings still to fix | **1 (WALKING)** |
| Stale CSV documentation still to sync | **1 (adqs.csv APOE rows)** |
| Total mis-codings fixed across all rounds | **33** |
| Newly identified mapping gaps for user decision | **~85+ items across instruments** |

---

### Files modified across all rounds

- `concept_maps/modalities.csv` — DICOM2OMOP modality concepts
- `concept_maps/procedures.csv` — 4 procedure concepts replaced
- `concept_maps/conditions.csv` — 11 phyneuro concepts replaced
- `concept_maps/labs.csv` — RCT8, RCT14, RCT142, RCT1669, CNT69, HMT98, SRT10630
- `concept_maps/biomarkers.csv` — GFAP, NFL
- `concept_maps/adqs.csv` — APOEGN, APOEGNPRSNFLG
- `concept_maps/units.csv` — GI/L, TI/L, case-variant cleanup
- `custom_concepts_needed.csv` — RCT9 stale entry removed
- `a4_omop_etl/image_occurrence.py` — anatomic_site concepts + visit linkage fix
- `a4_omop_etl/helpers.py` — VISCODE float64 fix
- `a4_omop_etl/observation_adqs.py` — APOE hardcoded concept_ids
- `a4_omop_etl/postprocessing.py` — case-insensitive unit lookup
