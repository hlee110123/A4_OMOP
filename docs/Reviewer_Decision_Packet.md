# Concept Review Packet — A4/LEARN OMOP ETL

**For:** Sarina, Dr Milap, Dr Blake (concept-mapping reviewers)
**From:** Robert Barrett
**Date:** 2026-08-20
**Status:** decisions requested; the ETL regenerates in ~15 minutes, so any decision here is cheap to apply.

Since the last review cycle, a full audit of the ETL was run against the source data,
the data dictionaries, the methods PDFs, and the OMOP vocabulary (local Athena snapshot
plus live Athena for CDISC/PPI/UK Biobank). Fifteen of your previously suggested
mappings were adopted (Part C). This packet contains everything that needs a reviewer
decision, grouped as: **Part A** — open modeling decisions (D1–D8); **Part B** — six
existing mappings we believe are wrong, with evidence (P1–P6); **Part C** — what was
already adopted from your review, for the record.

Every count and claim below was verified against the current pipeline output and the
source files; where a claim of ours was overturned during verification, we say so.

---

## Summary of decisions requested

| # | Topic | Recommendation |
|---|-------|----------------|
| D1 | CDISC non-standard concepts (~1M+ rows) | Keep as documented deviation; require CDISC vocabulary load |
| D2 | NXGAIT domain; education concept | Pick a Condition-domain gait concept (or ratify Observation routing); ratify non-standard education |
| D3 | SUVR granularity (5 sub-decisions) | Separate composites; quarantine reference/non-tissue rows; emit both tau references; pick one Stanford laterality; disclose dual atlas |
| D4 | Qualitative lab/ECG results | Approve value-concept mapping scope (~108K labs; ~180K ECG reads currently excluded) |
| D5 | Family history modeling | Standard FH concepts + relative qualifier; extract the AD-diagnosis fields |
| D6 | Borderline standard-concept candidates | Per-item calls (table) |
| D7 | Ratifications of implemented items | PET_VA read concepts; arm values; SMOKE ×20; edema kept custom |
| D8 | Term + Qualifier flattening rule | Adopt: concept = the item, answer = the value |
| P1–P6 | Mapping corrections | Remap six items (evidence in Part B) |

---

## Part A — Decisions

### D1. CDISC non-standard concepts

The CDR domain scores, MMSE items, and ADL-PQ items map to real CDISC-vocabulary
concepts (added to Athena 2023-12; verified live: e.g. 37524289 "CDR01-Sum of Boxes",
37535522 "MMS1-What Is the Date", 37539747 "ADL03-Drive Car"). All are
**Non-standard** and **Observation-domain**, and they sit in the standard-concept
fields of MEASUREMENT/OBSERVATION. At audit time they carried ~1.06M rows; the count
has since grown because the ADLPQSP study-partner items reuse the same concepts.
OHDSI DQD will flag every row, and any target CDM must load the CDISC vocabulary or
the concept FK fails (the ETL's validation now surfaces this on every run).

**Options:** (a) keep, as a documented deviation — no standard equivalents exist for
instrument items, and CDISC ids preserve exact item semantics; (b) move CDISC ids to
`*_source_concept_id` and mint A4_LEARN customs for the main field.

**Recommendation: (a).** Either way, "load CDISC (and PPI, UK Biobank)" becomes a
stated deployment requirement.

### D2. Remaining domain-routing items

A complete domain sweep of all standard concepts in the output found 8 violations;
3 were fixed by moving the MMSE/GDS/IES-R totals to OBSERVATION (their LOINC concepts
are Observation-domain), and 3 belong to Part B remaps. Two remain:

- **NXGAIT → 437643 "Abnormal gait"** (1,297 rows): the concept is Observation-domain
  but the rows sit in CONDITION_OCCURRENCE with the other 15 phyneuro findings (which
  are all Condition-domain SNOMED). **Decide:** substitute a Condition-domain gait
  concept, or ratify routing these rows to OBSERVATION.
- **EDCCNTU → 1015298 "Years of education"** (6,856 rows): non-standard LOINC, correct
  domain. The audit confirmed no standard equivalent exists (the CDISC alternative
  37546597 is equally non-standard). **Decide:** ratify the documented deviation.

### D3. SUVR granularity — five sub-decisions

All claims verified against the source files, the imaging methods PDFs, and the
current output. One of our earlier claims was **wrong** and is corrected in (d).

**(a) Separate the composites.** Amyloid concept 2100000031 currently carries 8
regions × 5,741 scans in equal parts: the `Composite_Summary` (the trial's headline
value), six cortical ROIs, and the whole-cerebellum reference `blcere_all` (SUVR
median exactly 1.000 — it is the reference; the methods PDF confirms whole cerebellum
as the reference for all scans). A naive mean over the concept is diluted 8:1. Tau has
composite analogues too: `MUBADA Mask` (AVID's discriminant target meta-ROI — the tau
endpoint region) and `DELTA_Z 50PCT N141`. **Decide:** dedicated composite concepts
(recommended) vs. status quo + documentation.

**(b) Reference-row fate.** Verified reference rows: amyloid `blcere_all` (≡1.000),
tau `WMref` (≡1.00 under PERSI), tau `cerebellum_crus_AVID` (≡1.00 under crus),
Stanford/PetSurfer `bi_Cerebellum.Cortex` (≡1.0; methods PDF confirms gray-matter
cerebellum reference). Also non-tissue ROIs: `PVC_AirCavity` (median 0.54), `PVC_CSF`
(0.40), `CSF/Head.ExtraCerebral`, `Mean.CSF`, vessels, ventricles. **Decide:** a
distinct "reference-region SUVR" concept (your sheets marked suvr_persi/suvr_crus
"custom concept to be created") vs. dropping these rows.

**(c) Tau reference transparency.** Tau values are `suvr_persi` (PERSI white-matter
reference); nothing in the row says so, and `suvr_crus` (conventional cerebellar-crus
reference; fully populated, 295,296 rows, median 1.11) is discarded. PERSI and crus
values are not comparable. **Decide:** append `ref=PERSI` to the source value
(recommended regardless) and whether to also emit the crus-referenced values under a
second concept — zero extraction cost.

**(d) Stanford/PetSurfer representation — prior claim corrected.** We previously
reported the Stanford `Mean.*` columns as "mean intensities mislabeled as SUVR", and
your sheets mapped them to UK Biobank mean-intensity concepts. Verification proves
both wrong: `bi_Amygdala` reconstructs **exactly** (max diff 0.000000 across 447
scans) as the volume-weighted average of `Mean.Left/Right.Amygdala`, and the tau
methods PDF states the csv values are normalized to a gray-matter cerebellum
reference, with `bi_*` defined as the volume-weighted bilateral rollup. So `Mean.*`
**are SUVRs** — we suggest withdrawing the UK Biobank mapping. The real issues:
each bilateral structure appears ~3× under one concept (left, right, and an exactly
derivable bilateral), and laterality lives only in the source value. PetSurfer's
`PVC_*` columns are partial-volume-corrected SUVRs (corr 0.966 with `bi_*` at the
same scale), with 2 small negatives (ordinary PVC artifact — filter). **Decide:**
keep per-hemisphere `Mean.*` and drop the derivable `bi_*`, or the reverse.

**(e) Dual atlas disclosure.** The tau file's 188 anatomical regions span two
parcellation schemes under one concept (`Amygdala_lh_VOI` and `Amygdala_L` both
exist). **Decide:** split by atlas, or document.

Also mechanical once D3 lands: `HOC` (hippocampal occupancy, a 0–0.904 ratio;
dictionary-confirmed) moves out of "Brain Region Volume (mL)" to its own ratio
concept.

### D4. Qualitative results

~108K central-lab rows whose result is text (top values: Negative 37K, Normal 10K,
Yellow 9.5K, Not Detected 8.3K, genotypes, Trace) carry no `value_as_concept_id`, so
they are invisible to concept-based queries. ~180K qualitative ECG interpretation rows
(overall normal/abnormal 13,938; rhythm; conduction, e.g. RBBB) are excluded from the
CDM entirely. Standard answer concepts exist for most (e.g. 45880296 "Not detected",
9191/9189 Positive/Negative). **Decide:** the scope — map the common lab answers;
whether ECG interpretations enter (as measurements with value concepts or
observations); who owns the long tail.

### D5. Family history

Current modeling uses custom concepts (2100000210–212) recording only *whether* a
parent/sibling had dementia; the stronger signal — "did this relative receive a
diagnosis of Alzheimer's disease" (MOTHDIAG 1,614 Yes; FATHDIAG 657 Yes; SIBDIAG) —
is never extracted, and the customs are invisible to standard family-history queries.
Standard concepts exist: 4216175 "FH: Alzheimer's disease", 4326002 "Family history
of dementia" (both SNOMED, standard). **Recommendation:** standard FH concepts with
the relative in `qualifier_source_value` (the pattern already used for study-partner
responses), and extract the diagnosis fields. **Decide:** approve the remodel.

### D6. Borderline standard-concept candidates

From the systematic custom-vs-standard audit (which also produced the 15 adoptions in
Part C). Each needs a quick call:

| Item | Candidate | Caveat |
|------|-----------|--------|
| BEHAVLIF (lifetime suicidal-behavior composite) | LOINC 1002261 "Suicidal behavior [C-SSRS]" | Timeframe stretch — the LOINC item has no lifetime qualifier |
| MRI radiological read concept | SNOMED 4086692 "Imaging interpretation" | Loses MRI-specificity (modality stays in source value) |
| CSF *modified* Abeta-40/42 pair | 42868555 / 3042810 (plain CSF standards) | Only if "modified" is sample pre-treatment, not a different analyte — needs an assay-methods read |
| Study-partner relationship | LOINC 85432-3 "Contact relationship to patient" | "Contact" ≈ "study partner"; answer lists differ |
| Study-partner cohabitation | LOINC 46468-5 "Current living arrangement" | Subject-of-record is the participant, not the dyad |
| RUIB hospital admissions | none suitable | All standard concepts have the wrong recall window (6mo/90d vs 1yr) — keep custom |
| ARIA-H | SNOMED 37161555 (standard Condition) | Proposal: emit as co-occurring condition_occurrence when microhemorrhage count > 0 |
| Duplicate custom pairs | — | Consolidate: Logical Memory 2100000005/55, Digit Symbol 2100000006/52, imaging 2100000030-32 vs 93-95 |

### D7. Ratifications (implemented, pending your blessing)

- **PET_VA visual reads** (reader 1/2, consensus, overall eligibility): now extracted
  as categorical measurements under customs 2100000570–573 with Positive/Negative
  value concepts (9191/9189) — 9,422 rows; previously captured nowhere. Supply
  preferred concepts if you have them.
- **Treatment-arm values**: SNOMED 44804245 "Placebo" / RxNorm Extension 36852349
  solanezumab as `value_as_concept_id` (the pair is stylistically asymmetric — a
  Drug-domain concept as an answer — but both are standard).
- **SMOKE** → UK Biobank 35810373 "cigarettes smoked daily" with the dictionary's
  20-cigarettes/pack conversion (source records packs/day; original preserved).
- **Edema severity (PXEDSEV)**: kept custom; the SNOMED 4313204 "Grade of edema"
  alternative and its caveats (no standard "Trace" value; domain shift) are
  documented in `concept_maps/conditions.csv`.

### D8. A flattening rule to prevent recurring errors

Your mapping sheets record a **Term + Qualifier** pair per item. Several errors in
Part B arose from collapsing that pair the wrong way (the answer concept became the
question concept). Proposed standing rule for all future mappings:

> **concept = the item asked; answer = `value_as_concept_id`.**
> Meas Value / Answer-class concepts never appear in `*_concept_id` fields.

---

## Part B — Mapping corrections requested (with evidence)

| # | Current mapping | Evidence | Proposed |
|---|-----------------|----------|----------|
| P1 | RSSTST → 4322976 | This is the bare SNOMED hierarchy root "Procedure" (and the noted alternative 4048365 is the root "Measurement") — semantically empty | Real satisfaction-item concept or custom |
| P2 | ASCALL → 36309019 "Phone Call"; ASTEXT → 37079157 "Text message"; NXOTHER → 36309562 | All are LOINC **answer** concepts (Meas Value domain) used as the observed-entity concept; 29.5K rows each for the ADL items | Item concept (CDISC siblings exist); answers to value fields |
| P3 | MMSE letters → SNOMED 4224585/4224228/4122853/4106482 ("D","L","R","O") | Literal letter answer values (Meas Value), not items; the CDISC position items the ETL uses are semantically correct | Keep ETL's CDISC items |
| P4 | VSRESP → 4117286 "Finding of rate of respiration" | Condition-domain; the ETL's LOINC 3024171 (standard, Measurement) is the conventional choice | Keep ETL's LOINC |
| P5 | Phyneuro → "Examination of X" concepts | Procedure-domain concepts describe the act of examining, erasing the normal/abnormal distinction the ETL encodes as conditions-when-abnormal | Keep ETL's abnormal-finding modeling |
| P6 | CogState composites → 3655544 "CogState Brief Battery" | One instrument concept for six different composites — lossy | Keep per-composite customs |

Also withdrawn from your suggestions after verification: the UK Biobank
mean-intensity mapping for Stanford `Mean.*` columns (see D3d — they are SUVRs).

---

## Part C — Adopted from your review (for the record)

Live in the current build, sourced from your sheets:

- **C-SSRS intensity/count/lethality items** — full standard LOINC set (FREQLIF
  1001804, DURATLIF 1001899, CONTROLLIF 1002299, DETERLIF 1002010, REASONLIF 1001750,
  FIRSTDAM/FIRSTPOT, counts), ~6,750 previously unextracted values now loaded.
- **WALKING → PPI 903630** (standard; exact minutes-per-day match) — also resolved a
  custom-ID collision.
- **Definite superficial siderosis → SNOMED 37116474** — 25 condition rows (ARIA-H
  relevant).
- **STAI → 40219573 "STAI: STATE score"** (A4 uses the 6-item state form — verified
  against the dictionary items).
- **SMOKE → 35810373** with ×20 conversion (D7 ratification).
- Independent audit adoptions in the same spirit: plasma Abeta-40/42 → LOINC
  42868556/3043102 (both assay streams unified, units harmonized); milestones
  COMPLETED/SCREEN FAILURE/WITHDRAWAL/LOST-TO-FOLLOW-UP → standard SNOMED; treatment
  arm → SNOMED 618771 "Clinical trial arm"; Hep E interpretation → LOINC 95240-8;
  HCV RNA → LOINC 11011-4; QTcB → LOINC 46235174; GGT transcription error fixed
  (3004077 → 3026910).

The custom vocabulary now regenerates from the concept maps (`generate_custom_vocabulary.py`),
and every ETL run validates concept existence, custom-ID uniqueness, duplicates, and
date ranges, so decisions made here propagate mechanically and stay consistent.
