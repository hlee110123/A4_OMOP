# A4/LEARN OMOP ETL Pipeline

Transform clinical trial data from the A4 (Anti-Amyloid Treatment in Asymptomatic Alzheimer's Disease) and LEARN (Longitudinal Evaluation of Amyloid Risk and Neurodegeneration) studies into OMOP CDM v5.4 format.

## Overview

| Study | Description |
|-------|-------------|
| **A4** | Randomized, double-blind, placebo-controlled trial of Solanezumab in cognitively normal adults with preclinical Alzheimer's disease |
| **LEARN** | Longitudinal observational cohort of amyloid-negative participants |

**Population**: 6,945 cognitively normal adults aged 65-85 with preclinical Alzheimer's disease markers

## Quick Start

```bash
# Requirements: Python 3.x with pandas
pip install pandas

# Run the ETL
python run_etl.py
# or
python -m a4_omop_etl
```

**Output**: 10 core OMOP CSV files in `OMOP_Output/` plus 2 MI-CDM extension CSVs in `OMOP_Output/mi_cdm/`

## Output Files

| File | OMOP Table | Records | Description |
|------|-----------|--------:|-------------|
| `person.csv` | PERSON | 6,945 | Subject demographics |
| `visit_occurrence.csv` | VISIT_OCCURRENCE | 99,795 | Clinical site visits |
| `observation_period.csv` | OBSERVATION_PERIOD | 6,945 | Per-subject enrollment windows |
| `drug_exposure.csv` | DRUG_EXPOSURE | 74,776 | Solanezumab and placebo infusion records |
| `measurement.csv` | MEASUREMENT | 4,451,784 | Labs, vitals, cognitive tests, biomarkers, imaging |
| `observation.csv` | OBSERVATION | 1,545,309 | Lifestyle, family history, questionnaires, treatment arm |
| `condition_occurrence.csv` | CONDITION_OCCURRENCE | 14,925 | Abnormal exam findings |
| `procedure_occurrence.csv` | PROCEDURE_OCCURRENCE | 20,783 | Imaging procedures (MRI, PET, retinal) |
| `cdm_source.csv` | CDM_SOURCE | 1 | Source and vocabulary metadata |
| `date_anchor.csv` | _(utility)_ | 6,945 | De-identification offset reference |

### MI-CDM Extension Tables (Park et al. 2025)

The extension adds two tables. `procedure_occurrence` is a standard CDM table and is listed above.

| File | MI-CDM Table | Records | Description |
|------|-----------|--------:|-------------|
| `mi_cdm/image_occurrence.csv` | IMAGE_OCCURRENCE | 23,898 | One row per DICOM series equivalent |
| `mi_cdm/image_feature.csv` | IMAGE_FEATURE | 639,716 | Polymorphic bridge: image_occurrence ↔ measurement |

## Data Domains

### Measurements (4.5M records)
- **Clinical**: Vitals, labs (96 test types), ECG parameters
- **Cognitive**: PACC composite, MMSE, CDR, CFI, digit span, logical memory
- **Biomarkers**: Amyloid-beta, p-tau217, GFAP, NfL (Roche panel)
- **Imaging**: Volumetric MRI, amyloid PET SUVR, tau PET SUVR, retinal imaging, plus the MI-CDM image occurrence and image feature tables
- **CogState**: Computerized cognitive battery, MACQ, C-PATH

### Observations (1.5M records)
- **ADQS**: APOE genotype, APOE4 carrier status, randomized treatment assignment
- **Questionnaires**: GDS, STAI, ADL-PQ, AD Concerns, IES, FTP, RSS
- **Lifestyle**: Smoking, alcohol, exercise, sleep habits
- **Family History**: Parental and sibling dementia history
- **C-SSRS**: Columbia Suicide Severity Rating Scale (baseline lifetime + since last visit)
- **Milestones**: Study disposition events (randomization, completion, discontinuation)

## Project Structure

```
├── run_etl.py                    # Entry point
├── a4_omop_etl/                  # Python package (25 modules)
│   ├── config.py                 # File manifest, paths
│   ├── pipeline.py               # Main orchestration
│   ├── person.py                 # Demographics
│   ├── visit.py                  # Visits, observation periods
│   ├── drug_exposure.py          # Solanezumab dosing
│   ├── measurement_*.py          # Clinical, cognitive, imaging, biomarkers
│   ├── observation*.py           # Lifestyle, ADQS, questionnaires
│   ├── condition.py              # Physical/neuro exam findings
│   ├── procedure_occurrence.py   # Imaging procedures
│   ├── image_occurrence.py       # MI-CDM: DICOM series (Park 2025)
│   ├── image_feature.py          # MI-CDM: measurement bridge (Park 2025)
│   └── postprocessing.py         # Unit mapping, observation period expansion
│
├── concept_maps/                 # OMOP concept mappings (22 CSVs)
│   ├── demographics.csv          # Gender, race, ethnicity
│   ├── labs.csv                  # 96 lab test mappings
│   ├── cognitive.csv             # Cognitive assessment concepts
│   ├── biomarkers.csv            # AD biomarker concepts
│   ├── imaging.csv               # MRI/PET imaging concepts
│   ├── procedures.csv            # MI-CDM: imaging procedure concepts
│   ├── modalities.csv            # MI-CDM: DICOM modality concepts
│   ├── image_findings.csv        # MI-CDM: finding grouping concepts
│   ├── adqs.csv                  # APOE genotype, treatment arm
│   └── ...                       # See docs/Concept_Mappings.md
│
├── docs/                         # Detailed documentation
│   ├── ETL_Architecture.md       # Pipeline phases, data flow
│   ├── Concept_Mappings.md       # All concept mapping tables
│   ├── Data_Lineage.md           # Field-level audit trail
│   ├── Output_Schema.md          # Output file specifications
│   └── Extension_Guide.md        # Adding new data domains
│
├── Raw Data/                     # Source CSVs (not in repo)
├── Derived Data/                 # Processed CSVs (not in repo)
├── External Data/                # Lab/imaging CSVs (not in repo)
└── OMOP_Output/                  # Generated output (not in repo)
    └── mi_cdm/                   # MI-CDM extension tables
```

## Key Features

### Privacy-Preserving Date Handling
All dates are synthetic. The ETL:
1. Generates deterministic offset per subject (MD5 hash of BID mod 365)
2. Applies offset to baseline date (2020-01-01)
3. Converts relative days to absolute dates

**Within-subject temporal intervals are preserved exactly.**

### Concept Mapping
- 22 CSV mapping files reviewable in Excel
- Standard OMOP concepts where available (LOINC, SNOMED)
- Custom concepts (2100000xxx) for study-specific measures
- Easy to modify without Python changes

### Post-Processing
- **Unit mapping**: 37.9% of measurements carry a UCUM unit concept; the remainder are
  unitless by nature (scores, z-scores, ratios)
- **Visit linkage**: exact match on `BID` + `VISCODE`, no day-window matching.
  92.6% of measurements and 98.0% of observations link to a visit
- **Observation period expansion**: widens both bounds to cover all clinical events
- **Undated rows**: dropped and reported rather than emitted with a substitute date,
  since the CDM date columns are NOT NULL

## Validation

The ETL performs 5 validation checks:
1. Person count matches source (6,945)
2. Visit count within tolerance
3. No orphan visits (referential integrity)
4. All persons have observation periods
5. Drug exposure count matches source (dosed records with a resolvable date)

## Documentation

| Document | Description |
|----------|-------------|
| [ETL Architecture](docs/ETL_Architecture.md) | Pipeline phases, module dependencies, data flow |
| [Concept Mappings](docs/Concept_Mappings.md) | All 22 concept CSVs with mapping tables |
| [Data Lineage](docs/Data_Lineage.md) | Field-level source → transform → output |
| [Output Schema](docs/Output_Schema.md) | Column schemas, value distributions, join patterns |
| [Extension Guide](docs/Extension_Guide.md) | Step-by-step guide for adding new domains |

## Loading into an OMOP CDM

The ETL writes CSVs; loading them requires the standard vocabulary plus two
vocabularies shipped here.

1. **Standard vocabulary** — download from [athena.ohdsi.org](https://athena.ohdsi.org)
   and load into your CDM instance. This ETL was built against `v5.0 27-FEB-25`
   (recorded in `cdm_source.vocabulary_version`).

2. **Study-specific concepts** — `custom_vocabulary/CONCEPT.csv` defines the 182
   `A4_LEARN` concepts used for measures with no standard equivalent (CogState
   subscales, questionnaire items, imaging finding categories). Load it into
   `CONCEPT` alongside the standard vocabulary, and `custom_vocabulary/VOCABULARY.csv`
   into `VOCABULARY`.

3. **DICOM vocabulary** — the MI-CDM `image_occurrence.modality_concept_id` values
   are DICOM concepts (`2128009230` MR, `2128009252` PT, `2128009239` OP). Load a
   DICOM vocabulary to resolve them. Note these are non-standard concepts, which is
   what the MI-CDM extension specifies for that field.

4. **Load the tables** — `load_omop.py` loads the CSVs into an existing schema.
   It matches **by column name, not position**: several exported tables do not follow
   CDM column order, so a positional `COPY` would put values in the wrong columns and
   still succeed.

   ```bash
   cp .env.example .env      # fill in connection settings
   python load_omop.py
   ```

`custom_concepts_needed.csv` is the working registry behind
`custom_vocabulary/CONCEPT.csv`, carrying source codes, row counts and mapping notes.

### Known gaps

- 49 concept IDs attributed to CDISC do not resolve unless the CDISC vocabulary is
  loaded; they cover MMSE items, CDR domains and ADL-PQ items.
- `measurement` omits `unit_source_concept_id`; `observation` omits `value_source_value`,
  `observation_event_id` and `obs_event_field_concept_id`.
- Nullable foreign keys are written in float form (`5.0`), and `drug_exposure.stop_reason`
  exceeds its CDM width. Load by column name and cast, as `load_omop.py` does.

## Requirements

- Python 3.8+

```bash
pip install -r requirements.txt
```

## License

[Add license information]

## Citation

If you use this ETL pipeline, please cite:

```
A4/LEARN OMOP ETL Pipeline
https://github.com/hlee110123/A4_OMOP
```

## Contact

[Add contact information]
