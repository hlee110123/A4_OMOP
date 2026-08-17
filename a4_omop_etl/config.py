"""
Paths, output directory, and source file manifest.

All source file paths are defined here so the pipeline has a single
place to update when file locations change.
"""

from pathlib import Path

BASE_DIR = Path("/Users/robertbarrett/Downloads/Clinical")
OUTPUT_DIR = BASE_DIR / "OMOP_Output"
CONCEPT_DIR = BASE_DIR / "concept_maps"

# MI-CDM extension output subdirectory
MI_CDM_OUTPUT_DIR = OUTPUT_DIR / "mi_cdm"

# Source file manifest: (variable_name, subdirectory, filename)
# Grouped by pipeline phase for readability.
SOURCE_FILES = [
    # Core demographics and visits
    ('subjinfo',        'Derived Data',  'SUBJINFO.csv'),
    ('sv',              'Derived Data',  'SV.csv'),
    ('ptdemog',         'Raw Data',      'ptdemog.csv'),
    ('adqs',            'Derived Data',  'ADQS.csv'),

    # Drug exposure
    ('dose',            'Raw Data',      'dose.csv'),

    # Clinical measurements
    ('vitals',          'Raw Data',      'vitals.csv'),
    ('clrm_lab',        'External Data', 'clrm_lab.csv'),
    ('clrm_ecg',        'External Data', 'clrm_ecg.csv'),

    # Cognitive assessments
    ('pacc',            'Derived Data',  'PACC.csv'),
    ('mmse',            'Raw Data',      'mmse.csv'),
    ('cdr',             'Raw Data',      'cdr.csv'),

    # Biomarkers
    ('biomarker_ab',    'External Data', 'biomarker_AB_Test.csv'),
    ('biomarker_ptau',  'External Data', 'biomarker_pTau217.csv'),
    ('biomarker_roche', 'External Data', 'biomarker_Plasma_Roche_Results.csv'),

    # Imaging
    ('imaging_mri',     'External Data', 'imaging_volumetric_mri.csv'),
    ('imaging_amyloid', 'External Data', 'imaging_SUVR_amyloid.csv'),
    ('imaging_tau',     'External Data', 'imaging_SUVR_tau.csv'),

    # CogState
    ('cogstate',        'Derived Data',  'COGSTATE_COMPUTERIZED.csv'),
    ('cogstate_battery','External Data', 'cogstate_battery.csv'),
    ('cogstate_macq',   'External Data', 'cogstate_macq.csv'),
    ('cogstate_cpath',  'External Data', 'cogstate_cpath.csv'),

    # Lifestyle and family history
    ('habits',          'Raw Data',      'habits.csv'),
    ('famhxpar',        'Raw Data',      'famhxpar.csv'),
    ('famhxsib',        'Raw Data',      'famhxsib.csv'),

    # Condition occurrence
    ('phyneuro',        'Raw Data',      'phyneuro.csv'),

    # Milestones / disposition
    ('ds',              'Derived Data',  'DS.csv'),

    # Extended cognitive tests
    ('cfi',             'Raw Data',      'cfi.csv'),
    ('cfisp',           'Raw Data',      'cfisp.csv'),
    ('cogdigit',        'Raw Data',      'cogdigit.csv'),
    ('cogfcsr',         'Raw Data',      'cogfcsr16.csv'),
    ('coglogic',        'Raw Data',      'coglogic.csv'),

    # Questionnaires
    ('psychwell',       'Raw Data',      'psychwell.csv'),
    ('adlpq',           'Raw Data',      'adlpq.csv'),
    ('adlpqsp',         'Raw Data',      'adlpqsp.csv'),
    ('concerns',        'Raw Data',      'concerns.csv'),
    ('cssrs',           'Raw Data',      'cssrs.csv'),
    ('cssrslv',         'Raw Data',      'cssrslv.csv'),

    # Extended imaging
    ('imaging_mri_reads',  'External Data', 'imaging_MRI_reads.csv'),
    ('imaging_flair',      'External Data', 'imaging_FLAIR_WMH_QC.csv'),
    ('imaging_retinal',    'External Data', 'imaging_retinal.csv'),
    ('imaging_pet_va',     'External Data', 'imaging_PET_VA.csv'),
    ('tau_petsurfer',      'External Data', 'imaging_Tau_PET_PetSurfer.csv'),
    ('tau_stanford',       'External Data', 'imaging_Tau_PET_Stanford.csv'),

    # Study partner
    ('spinfo',          'Raw Data',      'spinfo.csv'),

    # Secondary questionnaires
    ('ies',             'Raw Data',      'ies.csv'),
    ('ftpscale',        'Raw Data',      'ftpscale.csv'),
    ('rss',             'Raw Data',      'rss.csv'),
    ('views',           'Raw Data',      'views.csv'),
    ('ruib',            'Raw Data',      'ruib.csv'),
    ('ruib1',           'Raw Data',      'ruib1.csv'),
]


def load_all_sources() -> dict:
    """Load all source CSVs into a dict keyed by variable name."""
    import pandas as pd

    sources = {}
    print("\n--- Loading Source Data ---")
    for name, subdir, filename in SOURCE_FILES:
        path = BASE_DIR / subdir / filename
        df = pd.read_csv(path)
        sources[name] = df
        print(f"Loaded {filename}: {len(df)} rows")
    return sources
