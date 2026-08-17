# ETL Field Mapping Reference

Complete field-level mapping from A4/LEARN source data to OMOP CDM v5.4.

Each section corresponds to one ETL module function. Cross-reference with CSVs in `concept_maps/` for the authoritative concept definitions.

---

## MEASUREMENT — Vitals (`measurement_clinical.py` : `create_measurement_vitals`)

**Source**: vitals.csv | **Filter**: DONE=1 | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/vitals.csv`

| Source Field | Concept ID | Concept Name | Unit | Unit Concept ID |
|---|---|---|---|---|
| STDWT | 3025315 | Body weight | kg | 9529 |
| STDHT | 3036277 | Body height | cm | 8582 |
| VSBPSYS | 3004249 | Systolic BP | mmHg | 8876 |
| VSBPDIA | 3012888 | Diastolic BP | mmHg | 8876 |
| VSPULSE | 3027018 | Heart rate | beats/min | 8541 |
| VSRESP | 3024171 | Respiratory rate | breaths/min | 8541 |
| STDTEMP | 3020891 | Body temperature | Cel | 586323 |

---

## MEASUREMENT — Labs (`measurement_clinical.py` : `create_measurement_labs`)

**Source**: clrm_lab.csv | **Filter**: LBSTAT != 'NOT DONE' | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/labs.csv`

Lookup: LBTESTCD -> concept_id. `value_as_number` = LBORRES (numeric) or LBSTRESN.

### Hematology

| Source Code | Concept ID | Concept Name | Notes |
|---|---|---|---|
| HMT1 | 3000963 | Hemoglobin | LOINC 718-7 |
| HMT2 | 3009542 | Hematocrit | LOINC 4544-3 |
| HMT3 | 3020416 | RBC | LOINC 789-8 |
| HMT4 / HMT7 | 3010813 | WBC | LOINC 6690-2 |
| HMT13 | 3024929 | Platelets | LOINC 777-3 |
| HMT40 | 3000963 | Hemoglobin | duplicate code |
| HMT102 | 3009744 | MCHC | LOINC 786-4 |
| HMT8 | 3017732 | Neutrophils | LOINC 751-8 |
| HMT9 | 3004327 | Lymphocytes | LOINC 731-0 |
| HMT10 | 3001604 | Monocytes | LOINC 742-7 |
| HMT11 | 3013115 | Eosinophils | LOINC 711-2 |
| HMT12 | 3006315 | Basophils | LOINC 704-7 |
| HMT20 | 3004809 | Band neutrophils | LOINC 764-1 |
| HMT71 (+ _1-_5) | 40761509 | RBC Morphology | LOINC 58408-6 |
| HMT95 | 3013498 | Atypical/Variant lymphocytes | LOINC 733-6 |
| HMT98 | 37173288 | Nucleated RBC count | SNOMED |
| HMT370 | 3004410 | Hemoglobin A1c | LOINC 4548-4 |

### Chemistry

| Source Code | Concept ID | Concept Name | Notes |
|---|---|---|---|
| RCT1 | 3024128 | Total Bilirubin | LOINC 1975-2 |
| RCT3 | 3004077 | GGT | LOINC 2324-2 |
| RCT5 | 3013721 | AST | LOINC 1920-8 |
| RCT6 | 3013682 | BUN | LOINC 3094-0 |
| RCT14 | 3019550 | CK | LOINC 2157-6 |
| RCT183 | 3006906 | Calcium | LOINC 17861-6 |
| RCT392 | 3016723 | Creatinine | LOINC 2160-0 |
| RCT4 | 3006923 | ALT/SGPT | LOINC 1742-6 |
| RCT8 | 3037556 | Uric Acid/Urate | LOINC 3084-1 |
| RCT9 | 3011904 | Phosphorus | LOINC 2777-1 |
| RCT12 | 3020630 | Total Protein | LOINC 2885-2 |
| RCT13 | 3024561 | Albumin | LOINC 1751-7 |
| RCT15 | 3019550 | Sodium | LOINC 2951-2 |
| RCT16 | 3023103 | Potassium | LOINC 2823-3 |
| RCT18 | 3014576 | Chloride | LOINC 2075-0 |
| RCT20 | 3027114 | Cholesterol | LOINC 2093-3 |
| RCT29 | 3027597 | Direct Bilirubin | LOINC 1968-7 |
| RCT142 | 3004501 | Fasting Glucose | LOINC 2345-7 |
| RCT1407 | 3035995 | Alkaline Phosphatase | LOINC 6768-6 |
| RCT1669 | 3004501 | Random Glucose | LOINC 2345-7 |

### Urinalysis

| Source Code | Concept ID | Concept Name | Notes |
|---|---|---|---|
| UAT1 | 3027162 | Urine Color | LOINC 5778-6 |
| UAT2 | 3033543 | Urine Specific Gravity | LOINC 5811-5 |
| UAT3 | 3015736 | Urine pH | LOINC 5803-2 |
| UAT5 | 3009261 | Urine Glucose | LOINC 5792-7 |
| UAT6 | 3016436 | Urine Ketones | LOINC 5797-6 |
| UAT11 | 3010156 | Urine Leukocyte Esterase | LOINC 5799-2 |
| UAT13 | 3007876 | Urine Clarity/Appearance | LOINC 5767-9 |
| UAT43 | 3011397 | Urine Blood | LOINC 5794-3 |
| UAT49 | 3014051 | Urine Protein | LOINC 5804-0 |

### Coagulation

| Source Code | Concept ID | Concept Name | Notes |
|---|---|---|---|
| CGT283 | 3034426 | Prothrombin Time PT | LOINC 5902-2 |
| CGT564 | 3022217 | INR | LOINC 6301-6 |

### Special Chemistry / Immunology

| Source Code | Concept ID | Concept Name | Notes |
|---|---|---|---|
| SCT1528 | 3010156 | CRP high sensitivity | LOINC 30522-7 |
| SCT2356 | 3012336 | Haptoglobin | LOINC 4542-7 |
| CNT63 | 4014007 | Hepatitis B Surface Antigen | SNOMED |
| CNT68 | 42537336 | Hepatitis B Core Antibody | SNOMED |
| CNT69 | 4196134 | Hepatitis C Antibody | SNOMED |
| CNT70 | 37394378 | Hepatitis A IgM Antibody | SNOMED |
| CNT73 | 37392817 | Hepatitis A Total Antibody | SNOMED |
| CNT350 | 4196134 | Hepatitis C Antibody | duplicate |
| CNT353 | 4278658 | Hepatitis B Surface Antibody | SNOMED |
| CNT550 | 4014007 | Hepatitis B Surface Antigen II | duplicate |
| ORT7923 | 4295162 | Hepatitis E IgG | SNOMED |
| ORT7924 | 4268445 | Hepatitis E IgM | SNOMED |
| ORT11357 | 4295162 | Hepatitis E IgG | duplicate |
| ORT11358 | 4268445 | Hepatitis E IgM | duplicate |
| IMT1669 (+ _1-_3) | 37173542 | ANA | SNOMED |
| IMT1754 | 4217559 | Anti-Smooth Muscle Antibody IgG | SNOMED |
| CLT1878 | 3029139 | APOE genotype | LOINC 33327-0 |

### Drug-Related / Biomarker Panel Labs

| Source Code | Concept ID | Concept Name | Notes |
|---|---|---|---|
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
| SRT10630 | 745753 | CSF total Tau | CPT4 84394 |
| SRT18142 | 2100000524 | CSF free Abeta-40 | Custom |
| SRT18047 | 2100000525 | CSF free Abeta-42 | Custom |
| ORT11360 (+ _1-_5) | 2100000530 | Hep E IgG/IgM interpretation | Custom |
| GET1881 | 2100000531 | HCV RNA viral load | Custom |

---

## MEASUREMENT — ECG (`measurement_clinical.py` : `create_measurement_ecg`)

**Source**: clrm_ecg.csv | **Filter**: DONE=1 | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/ecg.csv`

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| RATE | 3027018 | Heart rate | beats/min |
| QT | 4116637 | QT interval duration | ms |
| QRS | 3022022 | QRS duration | ms |
| PR | 4092020 | PR interval duration | ms |
| RR | 3013078 | R-R interval by EKG | ms |

---

## MEASUREMENT — Cognitive Core (`measurement_cognitive.py` : `create_measurement_cognitive`)

Combines three sub-functions: PACC, MMSE, CDR.

### PACC (`create_measurement_pacc`)

**Source**: pacc.csv | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/cognitive.csv` (group=core)

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| PACC.raw | 2100000001 | PACC Raw Composite Score | score |
| FCTOTAL96 | 2100000004 | FCSRT-96 Total | score |
| LDELTOTAL | 2100000005 | Logical Memory Delayed | score |
| DIGITTOTAL | 2100000006 | Digit Symbol Total | score |

Also maps: `MMSCORE` (42869860, MMSE Total Score) from PACC dataset.

### MMSE (`create_measurement_mmse`)

**Source**: mmse.csv | **Filter**: DONE=1 | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/cognitive.csv` (group=core, mmse_item, mmse_letter)

**Total Score:**

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| MMSCORE | 42869860 | MMSE Total Score | score |

**Item Scores (26 items):**

| Source Field | Concept ID | Concept Name |
|---|---|---|
| MMDATE | 37535522 | MMSE Orientation Date |
| MMYEAR | 37530054 | MMSE Orientation Year |
| MMMONTH | 37524690 | MMSE Orientation Month |
| MMDAY | 37543352 | MMSE Orientation Day |
| MMSEASON | 37544881 | MMSE Orientation Season |
| MMHOSPIT | 37525797 | MMSE Orientation Hospital |
| MMFLOOR | 37530368 | MMSE Orientation Floor |
| MMCITY | 37528823 | MMSE Orientation City |
| MMAREA | 37534195 | MMSE Orientation Area |
| MMSTATE | 37538536 | MMSE Orientation State |
| MMBALL | 37545292 | MMSE Registration Ball |
| MMFLAG | 37534185 | MMSE Registration Flag |
| MMTREE | 37530589 | MMSE Registration Tree |
| MMWORLD | 2100000163 | MMSE Attention WORLD |
| MMBALLDL | 37544754 | MMSE Recall Ball |
| MMFLAGDL | 37528921 | MMSE Recall Flag |
| MMTREEDL | 37543093 | MMSE Recall Tree |
| MMWATCH | 4169312 | MMSE Naming Watch |
| MMPENCIL | 4169312 | MMSE Naming Pencil |
| MMREPEAT | 37527809 | MMSE Repetition |
| MMHAND | 37531096 | MMSE Command Take Paper |
| MMFOLD | 37531417 | MMSE Command Fold Paper |
| MMONFLR | 37537897 | MMSE Command Put on Floor |
| MMREAD | 37529583 | MMSE Reading |
| MMWRITE | 37539887 | MMSE Writing |
| MMDRAW | 37541207 | MMSE Drawing |

**DLROW Letter Positions (5 items):**

| Source Field | Concept ID | Concept Name | Note |
|---|---|---|---|
| MMDLTR | 37532418 | MMSE Attention Letter D Position | text value |
| MMLLTR | 37524591 | MMSE Attention Letter L Position | text value |
| MMRLTR | 37532900 | MMSE Attention Letter R Position | text value |
| MMOLTR | 37525937 | MMSE Attention Letter O Position | text value |
| MMWLTR | 37534611 | MMSE Attention Letter W Position | text value |

### CDR (`create_measurement_cdr`)

**Source**: cdr.csv | **Filter**: DONE=1 | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/cognitive.csv` (group=core, cdr_domain)

**Core Scores:**

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| CDGLOBAL | 37546494 | CDR Global Score | score |
| CDSOB | 37524289 | CDR Sum of Boxes | score |

**Domain Scores (7 domains):**

| Source Field | Concept ID | Concept Name |
|---|---|---|
| MEMORY | 37522525 | CDR Memory Domain |
| ORIENT | 37525225 | CDR Orientation Domain |
| JUDGE | 37530450 | CDR Judgment Domain |
| COMMUN | 37538839 | CDR Community Affairs Domain |
| HOME | 37545969 | CDR Home and Hobbies Domain |
| CARE | 37546534 | CDR Personal Care Domain |
| CDRSB | 2100000187 | CDR Sum of Boxes Revised |

---

## MEASUREMENT — Cognitive Extended (`measurement_cognitive.py` : `create_measurement_cognitive_extended`)

**Sources**: cfi.csv, cfisp.csv, cogdigit.csv, cogfcsr.csv, coglogic.csv | **Filter**: DONE=1 | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/cognitive.csv` (group=extended)

| Source Field | Source File | Concept ID | Concept Name |
|---|---|---|---|
| CFIPTTOTAL | cfi.csv | 2100000050 | CFI Patient Total |
| CFSPTTOTAL | cfisp.csv | 2100000051 | CFI Study Partner Total |
| DIGITTOTAL | cogdigit.csv | 2100000052 | Digit Symbol Total |
| FCTOTAL96 | cogfcsr.csv | 2100000053 | FCSR Total 96 |
| FCTOTF | cogfcsr.csv | 2100000056 | FCSR Free Recall Total |
| FCTOTC | cogfcsr.csv | 2100000057 | FCSR Cued Recall Total |
| LIMMTOTAL | coglogic.csv | 2100000054 | Logical Memory Immediate |
| LDELTOTAL | coglogic.csv | 2100000055 | Logical Memory Delayed |

---

## MEASUREMENT — Biomarkers (`measurement_biomarkers.py` : `create_measurement_biomarkers`)

**Concept CSV**: `concept_maps/biomarkers.csv`

### Amyloid Beta (ab_test.csv)

**Source**: biomarker_ab.csv | **Filter**: LBSTAT != 'NOT DONE' | **Date**: visit_start_date | **Visits**: linked

Lookup: LBTESTCD -> concept_id.

| Source Code | Concept ID | Concept Name | Unit |
|---|---|---|---|
| TP40 | 2100000011 | Total Plasma Abeta-40 | pg/mL |
| TP42 | 2100000012 | Total Plasma Abeta-42 | pg/mL |
| BP40 | 2100000013 | Bound Plasma Abeta-40 | pg/mL |
| BP42 | 2100000014 | Bound Plasma Abeta-42 | pg/mL |
| FP40 | 2100000015 | Free Plasma Abeta-40 | pg/mL |
| FP42 | 2100000016 | Free Plasma Abeta-42 | pg/mL |
| TP42/TP40 | 2100000010 | Amyloid-beta 42/40 Ratio | ratio |

### pTau-217 (ptau217.csv)

**Source**: biomarker_ptau.csv | **Date**: COLLECTION_DATE_DAYS_CONSENT | **Visits**: not linked

Handles `<LLOQ` values: extracted as value_as_number with `<` qualifier in value_source_value.

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| PTAU217 (from ORRES/ORRESRAW) | 1092155 | Phosphorylated Tau-217 | U/mL |

### Roche Panel (roche.csv)

**Source**: biomarker_roche.csv | **Filter**: LBSTAT != 'NOT DONE' | **Date**: LABD_DAYS_CONSENT | **Visits**: not linked

Lookup: LBTESTCD -> concept_id.

| Source Code | Concept ID | Concept Name | Unit |
|---|---|---|---|
| GFAP | 1761505 | Glial fibrillary acidic protein [Mass/volume] in Serum by Immunoassay (LOINC 100435-7) | pg/mL |
| NFL / NF-L | 3966310 | Neurofilament light chain [Mass/volume] in Serum or Plasma by Immunoassay (LOINC 101281-4) | pg/mL |
| TPP181 | 1259491 | Phosphorylated tau 181 [Mass/volume] in Plasma by Immunoassay (LOINC 103675-5) | pg/mL |
| AMYLB40 | 2100000011 | Total Plasma Abeta-40 (custom, research-specific) | pg/mL |
| AMYLB42 | 2100000012 | Total Plasma Abeta-42 (custom, research-specific) | pg/mL |

---

## MEASUREMENT — Imaging Core (`measurement_imaging.py` : `create_measurement_imaging`)

**Concept CSV**: `concept_maps/imaging.csv` (group=core)

### MRI Volumes

**Source**: imaging_mri.csv | **Date**: EXAMD_DAYS_CONSENT | **Visits**: not linked

Dynamic ROI columns: each numeric column ending in volume-like pattern becomes a measurement with MRI_VOLUME concept and ROI name in source_value.

| Concept ID | Concept Name | Unit | Notes |
|---|---|---|---|
| 2100000030 | Brain Region Volume | mL | One row per ROI column |

### Amyloid PET

**Source**: imaging_amyloid.csv | **Date**: EXAMD_DAYS_CONSENT | **Visits**: not linked

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| SUVR (composite) | 2100000031 | Amyloid PET SUVR | ratio |

### Tau PET

**Source**: imaging_tau.csv | **Date**: EXAMD_DAYS_CONSENT | **Visits**: not linked

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| SUVR (per region) | 2100000032 | Tau PET SUVR | ratio |

---

## MEASUREMENT — Imaging Extended (`measurement_imaging.py` : `create_measurement_imaging_extended`)

**Sources**: imaging_mri_reads.csv, imaging_flair.csv, imaging_retinal.csv, imaging_pet_va.csv, tau_petsurfer.csv, tau_stanford.csv | **Concept CSV**: `concept_maps/imaging.csv` (group=extended)

| Source File | Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|---|
| mri_reads | MCH | 2100000070 | Microhemorrhage Count | count |
| mri_reads | LOBAR | 2100000075 | Lobar Microhemorrhage | binary |
| mri_reads | DEEP | 2100000076 | Deep Microhemorrhage | binary |
| flair | WMH_VOL | 2100000071 | White Matter Hyperintensity Volume | mL |
| flair | WMH_CORRECTED | 2100000072 | WMH Corrected for ICV | % |
| flair | ICV | 2100000077 | Intracranial Volume | mL |
| retinal | RETINAL_AI | 2100000073 | Retinal AI Score | score |
| pet_va | PET_VA_SUVR | 2100000074 | PET Visual Assessment SUVR | ratio |
| tau_petsurfer | (per region) | 2100000078 | Tau PET SUVR PetSurfer | SUVR |
| tau_stanford | (per region) | 2100000079 | Tau PET SUVR Stanford | SUVR |

---

## MEASUREMENT — CogState Computerized (`measurement_cogstate.py` : `create_measurement_cogstate`)

**Source**: cogstate.csv | **Filter**: AVISIT mapped to VISCODE | **Date**: visit_start_date | **Visits**: linked via AVISIT->VISCODE mapping | **Concept CSV**: `concept_maps/cogstate.csv` (group=test, composite)

### Individual Tests

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
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

### Composite Scores

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| COGSTATE_COMPOSITE | 2100000046 | CogState Composite Score | z-score |
| C3Comp | 2100000141 | CogState C3 Composite | z-score |
| C3AbrComp | 2100000142 | CogState C3 Abbreviated Composite | z-score |
| AttnComp | 2100000143 | CogState Attention Composite | z-score |
| LearnWMComp | 2100000144 | CogState Learning/Working Memory Composite | z-score |
| OCLONBComp | 2100000145 | CogState OCL-ONB Composite | z-score |
| PsychAttnComp | 2100000146 | CogState Psychomotor/Attention Composite | z-score |

---

## MEASUREMENT — CogState Battery (`measurement_cogstate.py` : `create_measurement_cogstate_battery`)

**Source**: cogstate_battery.csv | **Filter**: AVISIT mapped | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/cogstate.csv` (group=battery, battery_metric)

### Battery Accuracy

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| BPET | 2100000147 | CogState Brief Psychomotor Exam | arcsine(sqrt(proportion)) |
| FNFT | 2100000148 | CogState Face-Name Feature Test | arcsine(sqrt(proportion)) |

### Battery Expanded Metrics

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| BPET_lmn | 2100000270 | CogState BPET Log Mean RT | log10(ms) |
| BPET_cor | 2100000271 | CogState BPET Correct Responses | count |
| BPET_err | 2100000272 | CogState BPET Errors | count |
| BPET_percor | 2100000273 | CogState BPET Percent Correct | % |
| FNFT_lmn | 2100000274 | CogState FNFT Log Mean RT | log10(ms) |
| FNFT_cor | 2100000275 | CogState FNFT Correct Responses | count |
| FNFT_err | 2100000276 | CogState FNFT Errors | count |
| FNFT_percor | 2100000277 | CogState FNFT Percent Correct | % |

---

## MEASUREMENT — CogState Questionnaires (`measurement_cogstate.py` : `create_measurement_cogstate_questionnaires`)

**Sources**: cogstate_macq.csv, cogstate_cpath.csv | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/cogstate.csv` (group=questionnaire, macq_item, cpath_item, cpath_domain)

### MACQ (Memory Complaint Questionnaire)

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| MCQT_TOTAL | 2100000090 | MACQ Memory Complaint Total | score |
| MACQ_Q1 (by row order) | 2100000280 | MACQ Q1 Remember Things | score |
| MACQ_Q2 | 2100000281 | MACQ Q2 Where Placed Things | score |
| MACQ_Q3 | 2100000282 | MACQ Q3 Remember Names | score |
| MACQ_Q4 | 2100000283 | MACQ Q4 Remember Phone Numbers | score |
| MACQ_Q5 | 2100000284 | MACQ Q5 Remember What Read | score |
| MACQ_Q6 | 2100000285 | MACQ Q6 Remember Experiences | score |

### C-PATH (Cognitive Function Patient Assessment)

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| CPATH_TOTAL | 2100000091 | C-PATH Total Score | score |
| CPATH_Q1 through Q26 | 2100000290-2100000315 | C-PATH Q1-Q26 | score |
| CPATH_CADL | 2100000316 | C-PATH Complex ADL Domain | score |
| CPATH_IF | 2100000317 | C-PATH Interpersonal Functioning Domain | score |

---

## MEASUREMENT — Questionnaire Scores (`measurement_questionnaire_scores.py`)

**Concept CSVs**: `concept_maps/questionnaires.csv` (group=measurement), `concept_maps/observations.csv` (group=measurement)

Numeric total scores moved from OBSERVATION to MEASUREMENT per OMOP CDM alignment.

| Source File | Source Field | Concept ID | Concept Name | Unit | Date Source |
|---|---|---|---|---|---|
| psychwell | GDTOTAL | 3051694 | Geriatric Depression Scale total | score | visit_start_date |
| psychwell | STAITOTAL | 2100000060 | STAI Total Score | score | visit_start_date |
| adlpq | ASSCORE | 37525066 | ADL01-Total ADCS-ADL Score (CDISC) | score | visit_start_date |
| adlpqsp | AISCORE | 2100000067 | ADL-PQ Study Partner Total Score | score | visit_start_date |
| ies | IESCORE | 1761510 | Impact of Event Scale-Revised total | score | IEDATE_DAYS_CONSENT |
| ruib1 | BR1NIGHT | 2100000208 | Hospital Overnight Stay Nights | nights | visit_start_date |
| spinfo | INFHRS | 2100000081 | Study Partner Contact Hours | hours/week | visit_start_date |

---

## MEASUREMENT — APOE Genotype (`observation_adqs.py` : `create_measurement_apoe`)

**Source**: adqs.csv (subject-level) | **Date**: synthetic_consent_date | **Visits**: not linked | **Concept CSV**: `concept_maps/adqs.csv`

| Source Field | Concept ID | Concept Name | Value Handling |
|---|---|---|---|
| APOEGN | 3029139 | APOE gene alleles e2/e3/e4 [Identifier] (LOINC 42315-2) | value_as_concept_id from genotype map (see below) |
| APOEGNPRSNFLG | 3006041 | Apolipoprotein E4 [Presence] in Blood (LOINC 15353-6) | value_as_number=0/1, value_as_concept_id=4188539 (positive) / 4188540 (negative) |

**APOE Genotype Value Concepts (LOINC answer codes):**

| Genotype | Value Concept ID | LOINC Answer |
|---|---|---|
| E2/E2 | 36307526 | LA21356-3 |
| E2/E3 | 36310377 | LA21357-1 |
| E2/E4 | 36308156 | LA21361-3 |
| E3/E3 | 36309003 | LA21358-9 |
| E3/E4 | 36311054 | LA21359-7 |
| E4/E4 | 36303222 | LA21360-5 |

---

## MEASUREMENT — Physical/Neuro Exam (`condition.py` : `create_phyneuro_observations_and_measurements`)

**Source**: phyneuro.csv | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/conditions.csv` (group=measurement)

| Source Field | Concept ID | Concept Name | Unit |
|---|---|---|---|
| PXEDSEV | 2100000500 | Edema Severity Score | ordinal 0-4 |

---

## OBSERVATION — Lifestyle (`observation.py` : `create_observation`)

**Source**: habits.csv | **Filter**: DONE=1 | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/observations.csv` (group=lifestyle)

| Source Field | Concept ID | Concept Name |
|---|---|---|
| SMOKE | 43054909 | Tobacco smoking status |
| ALCOHOL | 4238768 | Details of alcohol drinking behavior |
| CAFFEINE | 37153131 | Caffeine intake |
| AEROBIC | 4312325 | Active physical exercise |
| WALKING | 903630 | Walking exercise frequency |
| SLEEP | 40768255 | Sleep duration hours |

---

## OBSERVATION — Family History (`observation.py` : `create_observation`)

**Sources**: famhxpar.csv (parents), famhxsib.csv (siblings) | **Date**: synthetic_consent_date | **Concept CSV**: `concept_maps/observations.csv` (group=family_history)

One record per condition per family member. All use concept_id 4167217 (Family history of clinical finding) with condition detail in observation_source_value.

| Source File | Source Field | Concept ID | Notes |
|---|---|---|---|
| famhxpar | mother conditions | 4167217 | FAMHX_MOTHER prefix |
| famhxpar | father conditions | 4167217 | FAMHX_FATHER prefix |
| famhxsib | sibling conditions | 4167217 | FAMHX_SIBLING prefix |

---

## OBSERVATION — Milestones (`observation.py` : `create_observation_milestones`)

**Source**: ds.csv (disposition) | **Date**: DS_DAYS_CONSENT | **Concept CSV**: `concept_maps/milestones.csv`

Lookup: DSDECOD -> concept_id.

| Source Code | Concept ID | Concept Name |
|---|---|---|
| INFORMED CONSENT OBTAINED | 3018196 | Informed consent obtained |
| RANDOMIZED | 2000000010 | Study randomization |
| COMPLETED | 2000000011 | Study completion |
| SCREEN FAILURE | 2000000012 | Screen failure |
| WITHDRAWAL BY SUBJECT | 2000000013 | Withdrawal by subject |
| STUDY TERMINATED BY SPONSOR | 2000000014 | Study termination by sponsor |
| ADVERSE EVENT | 2000000015 | Discontinuation due to adverse event |
| DEATH | 4306655 | Death |
| LOST TO FOLLOW UP | 2000000016 | Lost to follow-up |
| OTHER | 2000000017 | Discontinuation for other reason |
| WITHDRAWAL BY PARENT/GUARDIAN | 2000000018 | Withdrawal by parent/guardian |
| LACK OF EFFICACY | 2000000019 | Discontinuation due to lack of efficacy |
| SAFETY RISK | 2000000020 | Discontinuation due to safety risk |
| PHYSICIAN DECISION | 2000000021 | Discontinuation by physician decision |
| PROTOCOL DEVIATION | 2000000022 | Discontinuation due to protocol deviation |

---

## OBSERVATION — C-SSRS (`observation.py` : `create_observation_cssrs`)

**Sources**: cssrs.csv (current visit), cssrslv.csv (lifetime) | **Date**: synthetic_consent_date (lifetime) or visit-linked | **Concept CSV**: `concept_maps/cssrs.csv`, `concept_maps/cssrslv_columns.csv`

### Current Visit (cssrs.csv)

Fields mapped per visit with VISCODE.

### Lifetime (cssrslv.csv)

Column remapping via `cssrslv_columns.csv` then same concept lookup.

| Source Code | Concept ID | Concept Name | Category |
|---|---|---|---|
| WISHLIFE | 1001715 | Wish to be dead Lifetime | ideation |
| ACTLIFE | 1001533 | Non-specific active suicidal thoughts Lifetime | ideation |
| METHOD | 1002307 | Active suicidal ideation with methods | ideation |
| INTENT | 1002212 | Active suicidal ideation with intent | ideation |
| PLAN | 1001538 | Active suicidal ideation with plan and intent | ideation |
| ATTMPT | 1002181 | Actual suicide attempt Lifetime | attempt |
| ATTMPT5 | 2100000106 | C-SSRS Attempt Past 5 Years | attempt |
| ATTMPTN | 1001884 | Actual suicide attempts # Lifetime | attempt |
| NONSUI | 1002148 | Non-suicidal self-injurious behavior Lifetime | self_injury |
| NONSUI5 | 2100000111 | C-SSRS NSSI Past 5 Years | self_injury |
| INTER | 1001743 | Interrupted suicide attempt Lifetime | behavior |
| INTERN | 1002459 | Interrupted suicide attempts # Lifetime | behavior |
| ABORT | 1002340 | Aborted suicide attempt Lifetime | behavior |
| ABORTN | 1002016 | Aborted suicide attempts # Lifetime | behavior |
| PREP | 1002213 | Preparatory acts or suicidal behavior | behavior |
| BEHAVLIF | 2100000115 | C-SSRS Suicidal Behavior Lifetime | behavior |
| SEVLIFE | 1001656 | Most severe suicidal ideation Lifetime | severity |
| FREQLIF | 1001804 | Frequency of most severe ideation | intensity |
| DURATLIF | 1001899 | Duration of most severe ideation | intensity |
| CONTROLLIF | 1002299 | Controllability of most severe ideation | intensity |
| DETERLIF | 1002010 | Deterrents of most severe ideation | intensity |
| REASONLIF | 1001750 | Reasons for most severe ideation | intensity |
| RECENTDAM | 1001783 | Actual lethality most recent attempt | lethality |
| RECENTPOT | 1001955 | Potential lethality most recent attempt | lethality |
| LETHALDAM | 1001730 | Actual lethality most lethal attempt | lethality |
| LETHALPOT | 1002243 | Potential lethality most lethal attempt | lethality |
| FIRSTDAM | 1001754 | Actual lethality first attempt | lethality |
| FIRSTPOT | 1001649 | Potential lethality first attempt | lethality |
| SUICIDE | 2100000119 | C-SSRS Suicide Completion | outcome |

---

## OBSERVATION — Study Partner (`observation.py` : `create_observation_study_partner`)

**Source**: spinfo.csv | **Date**: synthetic_consent_date | **Concept CSV**: `concept_maps/observations.csv` (group=study_partner)

| Source Field | Concept ID | Concept Name |
|---|---|---|
| RELATIONSHIP | 2100000080 | Study Partner Relationship |
| COHABITATION | 2100000082 | Study Partner Cohabitation |
| SP_AGE | 2100000083 | Study Partner Age |
| SP_GENDER | 2100000084 | Study Partner Gender |

---

## OBSERVATION — Secondary Questionnaires (`observation.py` : `create_observation_secondary_questionnaires`)

**Sources**: ies.csv, ftpscale.csv, rss.csv, views.csv, ruib.csv, ruib1.csv | **Concept CSV**: `concept_maps/questionnaires.csv` (group=secondary)

### IES Items (Impact of Events Scale)

| Source Field | Concept ID | Concept Name |
|---|---|---|
| IETHINK | 1761742 | Thought about adverse event unintentionally |
| IEAVOID | 1761406 | Avoided getting upset when thought about event |
| IEREMOVE | 1761453 | Tried to remove adverse event from memory |
| IESLEEP | 1761776 | Trouble falling asleep |
| IEWAVES | 1761777 | Waves of strong feelings about event |
| IEDREAMS | 1761687 | Had dreams about adverse event |
| IEAWAY | 1761804 | Avoided reminders of adverse event |
| IEREAL | 1761537 | Felt as if adverse event did not happen |
| IETALK | 1761343 | Tried not to talk about adverse event |
| IEMIND | 1761420 | Experienced mental images of adverse event |
| IETHINGS | 1761360 | Other things triggered thoughts about event |
| IEDEAL | 1761884 | Aware of feelings but did not address them |
| IENOTTHNK | 1761403 | Tried to not think of adverse event |
| IEREMIND | 1761881 | Reminders brought back feelings about event |
| IENUMB | 1761666 | Feelings about adverse event were numb |

### Other Secondary Questionnaires

| Source File | Source Field | Concept ID | Concept Name |
|---|---|---|---|
| ftpscale | FTP_METHOD | 2100000201 | Future Time Perspective Method |
| rss | RSS_QUALITY | 2100000202 | Research Satisfaction Quality |
| rss | RSS_RECOMMEND | 2100000203 | Research Satisfaction Recommend |
| views | VIEWS_SEEK | 2100000204 | Views Seek Knowledge |
| ruib | RUIB_ADMIT | 2100000205 | Resource Use Hospital Admission |
| ruib | RUIB_VOLUNTEER | 2100000206 | Resource Use Volunteer Work |
| ruib | RUIB_EMPLOY | 2100000207 | Resource Use Employment |
| ruib1 | RUIB1_TYPE | 2100000209 | Hospital Stay Type |

---

## OBSERVATION — Treatment Arm (`observation_adqs.py` : `create_observation_treatment_arm`)

**Source**: adqs.csv (subject-level) | **Date**: synthetic_consent_date | **Concept CSV**: `concept_maps/adqs.csv`

| Source Field | Concept ID | Concept Name | Value Handling |
|---|---|---|---|
| TX | 2100000400 | Treatment assignment | value_as_string=Placebo/Solanezumab, value_as_concept_id from map |

**Treatment Value Concepts:**

| Value | Value Concept ID |
|---|---|
| Placebo | 2100000401 |
| Solanezumab | 2100000402 |

---

## OBSERVATION — AD Concerns (`observation_questionnaires.py` : `create_observation_questionnaires`)

**Source**: concerns.csv | **Filter**: DONE=1 | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/questionnaires.csv` (group=primary)

| Source Field | Concept ID | Concept Name |
|---|---|---|
| CADDVLP | 2100000062 | AD Concern Development |
| CADKNOW | 2100000063 | AD Concern Knowledge |
| CADBLIEV | 2100000064 | AD Concern Belief |
| CADWRST | 2100000065 | AD Concern Worry |
| CADCNCRN | 2100000066 | AD Concern Total |

---

## OBSERVATION — GDS Items (`observation_questionnaires.py` : `create_observation_questionnaires`)

**Source**: psychwell.csv | **Filter**: DONE=1 | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/questionnaires.csv` (group=primary)

| Source Field | Concept ID | Concept Name |
|---|---|---|
| GDSATIS | 3048479 | Are you basically satisfied with your life [GDS] |
| GDDROP | 3049765 | Have you dropped many activities [GDS] |
| GDEMPTY | 3052362 | Do you feel your life is empty [GDS] |
| GDBORED | 3048797 | Do you often get bored [GDS] |
| GDSPIRIT | 3049130 | Are you in good spirits most of the time [GDS] |
| GDAFRAID | 3052621 | Are you afraid something bad will happen [GDS] |
| GDHAPPY | 3048472 | Do you feel happy most of the time [GDS] |
| GDHELP | 3051362 | Do you often feel helpless [GDS] |
| GDHOME | 3049156 | Do you prefer to stay at home [GDS] |
| GDMEMORY | 3052630 | Do you have more problems with memory [GDS] |
| GDALIVE | 3051716 | Do you think its wonderful to be alive [GDS] |
| GDWORTH | 3051419 | Do you feel pretty worthless [GDS] |
| GDENERGY | 3050101 | Do you feel full of energy [GDS] |
| GDHOPE | 3048841 | Do you feel your situation is hopeless [GDS] |
| GDBETTER | 3053256 | Do you think most people are better off [GDS] |

---

## OBSERVATION — Physical/Neuro Exam Findings (`condition.py` : `create_phyneuro_observations_and_measurements`)

**Source**: phyneuro.csv | **Date**: visit_start_date | **Visits**: linked | **Concept CSV**: `concept_maps/conditions.csv` (group=observation)

Each exam field is recorded as Normal (value_as_concept_id=4069590) or Abnormal (value_as_concept_id=4135493).

### Physical Exam Fields

| Source Field | Concept ID | Concept Name |
|---|---|---|
| PXHEADEY | 4090425 | Head and neck examination finding |
| PXCARD | 4103183 | Cardiac finding |
| PXPULM | 4024567 | Respiratory finding |
| PXABDOM | 441840 | Clinical finding of abdomen |
| PXMUSCUL | 135930 | Musculoskeletal finding |
| PXEDEMA | 4158343 | Peripheral edema finding |
| PXSKIN | 141960 | Skin finding |
| PXOTHER | 4134586 | Other physical finding |

### Neurological Exam Fields

| Source Field | Concept ID | Concept Name |
|---|---|---|
| NXGAIT | 4203631 | Gait finding |
| NXMOTOR | 4116942 | Motor function finding |
| NXSENSOR | 4161682 | Sensory finding |
| NXTREMOR | 4169095 | Tremor finding |
| NXFINGER | 4300528 | Finger-to-nose test finding |
| NXHEEL | 4301597 | Heel-to-shin test finding |
| NXNERVE | 4027384 | Cranial nerve finding |
| NXOTHER | 4135493 | Other neurological finding |

---

## Non-Domain Tables

### PERSON (`person.py` : `create_person_table`)

**Sources**: SUBJINFO.csv, ptdemog.csv | **Concept CSV**: `concept_maps/demographics.csv`

### VISIT_OCCURRENCE (`visit.py` : `create_visit_occurrence`)

**Source**: SV.csv | **Concept CSV**: `concept_maps/visits.csv`

### OBSERVATION_PERIOD (`visit.py` : `create_observation_period`)

**Source**: SUBJINFO.csv, SV.csv | Expanded by `postprocessing.expand_observation_periods()`

### DRUG_EXPOSURE (`drug_exposure.py` : `create_drug_exposure`)

**Source**: dose.csv | **Filter**: DONE='Yes' | **Concept CSV**: `concept_maps/drugs.csv`

| Source Code | Concept ID | Concept Name |
|---|---|---|
| Solanezumab 400mg | 2000000001 | Solanezumab 400mg IV |
| Placebo | 2000000002 | Placebo IV infusion |
| Solanezumab (generic) | 2000000003 | Solanezumab IV (generic) |

### Post-Processing

- **Unit mapping** (`postprocessing.map_unit_concepts`): Maps unit_source_value to unit_concept_id via `concept_maps/units.csv` (45 entries)
- **Observation period expansion** (`postprocessing.expand_observation_periods`): Extends end dates to cover all measurement/observation/drug_exposure dates

---

## PROCEDURE_OCCURRENCE — Imaging (`procedure_occurrence.py` : `create_procedure_occurrence`)

**Source**: imaging_mri, imaging_amyloid, imaging_tau, imaging_mri_reads, imaging_flair, imaging_retinal, imaging_pet_va, tau_petsurfer, tau_stanford | **Filter**: scan_analyzed='Yes' for PET | **Date**: *_DAYS_CONSENT → anchored | **Visits**: linked | **Concept CSV**: `concept_maps/procedures.csv`

| Source File | procedure_source_value | concept_id | concept_name |
|-------------|----------------------|-----------|-------------|
| imaging_mri, imaging_mri_reads, imaging_flair | MRI_BRAIN | 2100000080 | MRI Brain |
| imaging_amyloid, imaging_pet_va | PET_AMYLOID | 2100000081 | PET Amyloid |
| imaging_tau, tau_petsurfer, tau_stanford | PET_TAU | 2100000082 | PET Tau |
| imaging_retinal | RETINAL_IMAGING | 2100000083 | Retinal Imaging |

---

## IMAGE_OCCURRENCE — MI-CDM (`image_occurrence.py` : `create_image_occurrence`)

**Source**: Same imaging sources as PROCEDURE_OCCURRENCE | **Granularity**: (person, series_type, date) | **Concept CSVs**: `concept_maps/procedures.csv`, `concept_maps/modalities.csv`

| Series Type | Modality | modality_concept_id | anatomic_site_concept_id |
|-------------|----------|--------------------:|-------------------------:|
| T1_VOLUMETRIC | MR | 2128009230 | 4007117 (Brain) |
| SWI_READS | MR | 2128009230 | 4007117 (Brain) |
| FLAIR | MR | 2128009230 | 4007117 (Brain) |
| AMYLOID_PET | PT | 2128009252 | 4007117 (Brain) |
| TAU_PET | PT | 2128009252 | 4007117 (Brain) |
| RETINAL | OP | 2128009239 | 4103720 (Eye) |

---

## IMAGE_FEATURE — MI-CDM (`image_feature.py` : `create_image_feature`)

**Source**: measurement table (MI-CDM annotated rows) + image_occurrence | **Concept CSVs**: `concept_maps/image_findings.csv`, `concept_maps/image_feature_types.csv`

| Pipeline Annotation | alg_system | image_finding_concept_id | Finding |
|---------------------|-----------|-------------------------:|---------|
| VOLUMETRIC_MRI | urn:a4:pipeline:volumetric_mri | 2100000093 | Brain volumetric measurement |
| SUVR_AMYLOID | urn:a4:pipeline:suvr_amyloid | 2100000094 | Amyloid PET SUVR |
| SUVR_TAU | urn:a4:pipeline:suvr_tau | 2100000095 | Tau PET SUVR |
| TAU_PETSURFER | urn:a4:pipeline:petsurfer | 2100000095 | Tau PET SUVR |
| TAU_STANFORD | urn:a4:pipeline:stanford | 2100000095 | Tau PET SUVR |
| MRI_READS | urn:a4:pipeline:mri_reads | 2100000096 | MRI radiological read |
| FLAIR_WMH | urn:a4:pipeline:flair_wmh | 2100000097 | FLAIR lesion volume |
| RETINAL_AI | urn:a4:pipeline:retinal_ai | 2100000098 | Retinal imaging measurement |
| PET_VA | urn:a4:pipeline:pet_visual_assessment | 2100000099 | PET visual assessment |

**Polymorphic event**: `image_feature_event_field_concept_id` = 1147330 (measurement.measurement_id), `image_feature_event_id` = actual measurement_id value.
