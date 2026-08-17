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

**Output**: 8 core OMOP CSV files in `OMOP_Output/` plus 3 MI-CDM extension CSVs in `OMOP_Output/mi_cdm/`

## Output Files

| File | OMOP Table | Records | Description |
|------|-----------|--------:|-------------|
| `person.csv` | PERSON | 6,945 | Subject demographics |
| `visit_occurrence.csv` | VISIT_OCCURRENCE | 99,795 | Clinical site visits |
| `observation_period.csv` | OBSERVATION_PERIOD | 6,945 | Per-subject enrollment windows |
| `drug_exposure.csv` | DRUG_EXPOSURE | 74,777 | Solanezumab infusion records |
| `measurement.csv` | MEASUREMENT | 2,413,202 | Labs, vitals, cognitive tests, biomarkers, imaging |
| `observation.csv` | OBSERVATION | 580,076 | Lifestyle, family history, APOE, questionnaires |
| `condition_occurrence.csv` | CONDITION_OCCURRENCE | 5,262 | Abnormal exam findings |
| `date_anchor.csv` | _(utility)_ | 6,945 | De-identification offset reference |

### MI-CDM Extension Tables (Park et al. 2025)

| File | MI-CDM Table | Records | Description |
|------|-----------|--------:|-------------|
| `mi_cdm/procedure_occurrence.csv` | PROCEDURE_OCCURRENCE | 20,307 | Imaging procedures (MRI, PET, retinal) |
| `mi_cdm/image_occurrence.csv` | IMAGE_OCCURRENCE | 23,898 | One row per DICOM series equivalent |
| `mi_cdm/image_feature.csv` | IMAGE_FEATURE | 675,690 | Polymorphic bridge: image_occurrence ↔ measurement |

## Data Domains

### Measurements (2.4M records)
- **Clinical**: Vitals, labs (96 test types), ECG parameters
- **Cognitive**: PACC composite, MMSE, CDR, CFI, digit span, logical memory
- **Biomarkers**: Amyloid-beta, p-tau217, GFAP, NfL (Roche panel)
- **Imaging**: Volumetric MRI, amyloid PET SUVR, tau PET SUVR, retinal imaging + MI-CDM extension with procedure, image occurrence, and image feature tables
- **CogState**: Computerized cognitive battery, MACQ, C-PATH

### Observations (580K records)
- **ADQS**: APOE genotype, APOE4 carrier status, treatment assignment, population flags
- **Questionnaires**: GDS, STAI, ADL-PQ, AD Concerns, IES, FTP, RSS
- **Lifestyle**: Smoking, alcohol, exercise, sleep habits
- **Family History**: Parental and sibling dementia history
- **C-SSRS**: Columbia Suicide Severity Rating Scale (current + lifetime)
- **Milestones**: Study disposition events (randomization, completion, discontinuation)

## Project Structure

```
├── run_etl.py                    # Entry point
├── a4_omop_etl/                  # Python package (21 modules)
│   ├── config.py                 # File manifest, paths
│   ├── pipeline.py               # Main orchestration
│   ├── person.py                 # Demographics
│   ├── visit.py                  # Visits, observation periods
│   ├── drug_exposure.py          # Solanezumab dosing
│   ├── measurement_*.py          # Clinical, cognitive, imaging, biomarkers
│   ├── observation*.py           # Lifestyle, ADQS, questionnaires
│   ├── condition.py              # Physical/neuro exam findings
│   ├── procedure_occurrence.py   # MI-CDM: imaging procedures
│   ├── image_occurrence.py       # MI-CDM: DICOM series (Park 2025)
│   ├── image_feature.py          # MI-CDM: measurement bridge (Park 2025)
│   └── postprocessing.py         # Unit mapping, visit linkage
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
│   ├── adqs.csv                  # APOE, treatment, population flags
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
- **Unit mapping**: 54.8% of measurements mapped to UCUM concepts
- **Fuzzy visit linkage**: ±7 day window recovers 92.2% visit links
- **Observation period expansion**: Extends to cover all clinical events

## Validation

The ETL performs 5 validation checks:
1. Person count matches source (6,945)
2. Visit count within tolerance
3. No orphan visits (referential integrity)
4. All persons have observation periods
5. Drug exposure count matches source

## Documentation

| Document | Description |
|----------|-------------|
| [ETL Architecture](docs/ETL_Architecture.md) | Pipeline phases, module dependencies, data flow |
| [Concept Mappings](docs/Concept_Mappings.md) | All 22 concept CSVs with mapping tables |
| [Data Lineage](docs/Data_Lineage.md) | Field-level source → transform → output |
| [Output Schema](docs/Output_Schema.md) | Column schemas, value distributions, join patterns |
| [Extension Guide](docs/Extension_Guide.md) | Step-by-step guide for adding new domains |

## Requirements

- Python 3.8+
- pandas

```bash
pip install pandas
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
