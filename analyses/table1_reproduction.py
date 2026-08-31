#!/usr/bin/env python3
"""Reproduce Table 1 of the A4 manuscript (Sperling et al., NEJM 2023;
NEJMoa2305032 — analyses/results/NEJMoa2305032.pdf) from the OMOP CDM in
PostgreSQL, and print it side-by-side with the published values.

Connection comes from .env at the repo root (same keys as load_omop.py).

Known, understood differences from the published table:
- Population: these columns are the full randomized cohort (578/591) split by
  the trial-arm observation (SNOMED 618771). The paper reports the mITT subset
  (564/583, >=1 post-baseline PACC); that ADaM analysis flag was deliberately
  excluded from the CDM, and the ~14 extra people per arm move no statistic
  beyond rounding.
- Age: OMOP stores year_of_birth only, so age computes at year precision and
  runs ~0.2-0.3 yr below the paper's fractional ages.
- Baseline selection: scores are taken at the visit CLOSEST TO RANDOMIZATION,
  not the earliest record — the earliest is the screening administration, and
  the screening->baseline practice effect is real (~+1.1 LMDR points).
- Centiloids are derived via the documented A4 formula
  (183.07 x SUVR - 177.26); the precomputed ADQS column is not loaded.

Run:  python3 analyses/table1_reproduction.py
"""

import os
import warnings
from pathlib import Path

import pandas as pd
import psycopg2

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent.parent

# Concept ids (see concept_maps/ and docs/Reviewer_Decision_Packet.md)
TRIAL_ARM = 618771          # SNOMED Clinical trial arm; values Placebo/Solanezumab
EDUCATION = 1015298         # Years of education (LOINC, non-standard; documented)
FAMHX = (2100000210, 2100000211, 2100000212)  # mother/father/sibling dementia
APOE_GENO = 3029139         # APOE gene alleles [Identifier]; ADQS source rows
APOE_CARRIER = 3006041      # ApoE4 [Presence]
AMYLOID_SUVR = 2100000031   # regional+composite; filter Composite_Summary
PACC_RAW = 2100000001
LMDR = 2100000055           # Logical Memory delayed (coglogic)
MMSE_TOTAL = 42869860       # OBSERVATION (Observation-domain concept)
CFI_PT, CFI_SP = 2100000050, 2100000051
ADL_SP = 2100000067
CDR_SB = 37524289           # CDISC
YES = 4188539

# Published Table 1 values (Solanezumab N=564, Placebo N=583)
PUBLISHED = {
    'N': ('564', '583'), 'Age — yr': ('72.0±4.7', '71.9±5.0'),
    'Female — no. (%)': ('329 (58.3)', '352 (60.4)'),
    'Education — yr': ('16.6±2.7', '16.6±2.9'),
    'White': ('531 (94.1)', '549 (94.2)'), 'Black': ('12 (2.1)', '15 (2.6)'),
    'Asian': ('11 (2.0)', '13 (2.2)'), 'Other or missing': ('10 (1.8)', '6 (1.0)'),
    'Not Hispanic or Latino': ('542 (96.1)', '560 (96.1)'),
    'Hispanic or Latino': ('16 (2.8)', '18 (3.1)'),
    'Ethnicity unknown': ('6 (1.1)', '5 (0.9)'),
    'Family history of dementia': ('411 (72.9)', '449 (77.0)'),
    'ApoE e2/e2': ('1 (0.2)', '0'), 'ApoE e2/e3': ('28 (5.0)', '33 (5.7)'),
    'ApoE e2/e4': ('13 (2.3)', '22 (3.8)'), 'ApoE e3/e3': ('202 (35.8)', '208 (35.7)'),
    'ApoE e3/e4': ('273 (48.4)', '273 (46.8)'), 'ApoE e4/e4': ('47 (8.3)', '47 (8.1)'),
    'ApoE e4 carrier': ('333 (59.0)', '342 (58.7)'),
    'Amyloid SUVR': ('1.3±0.2', '1.3±0.2'), 'Centiloids': ('66.2±33.5', '65.9±32.1'),
    'PACC score': ('0.0±2.8', '0.0±2.6'), 'LMDR score': ('12.6±3.8', '12.7±3.5'),
    'MMSE score': ('28.8±1.3', '28.8±1.2'), 'CFI combined score': ('4.0±3.6', '3.6±3.3'),
    'ADL partner score': ('43.4±2.7', '43.5±2.6'), 'CDR-SB score': ('0.1±0.2', '0.0±0.2'),
}


def connect():
    for line in (BASE / '.env').read_text().splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())
    return psycopg2.connect(
        host=os.environ['PGHOST'], port=int(os.environ.get('PGPORT', '5432')),
        dbname=os.environ.get('PGTARGET_DB', 'a4'), user=os.environ['PGUSER'],
        password=os.environ['PGPASSWORD'], sslmode='require')


def build(conn):
    q = lambda sql, **kw: pd.read_sql(sql, conn, params=kw or None)

    arm = q(f"""select person_id, value_as_string as arm, observation_date::date as rand_date
                from dbo.observation where observation_concept_id = {TRIAL_ARM}""")
    df = arm.merge(q("""select person_id, year_of_birth, gender_concept_id,
                               race_concept_id, ethnicity_concept_id from dbo.person"""),
                   on='person_id')
    df['age'] = pd.to_datetime(df.rand_date).dt.year - df.year_of_birth
    df['female'] = df.gender_concept_id.eq(8532)

    def one_per_person(sql, label):
        d = q(sql)
        return d.rename(columns={d.columns[1]: label})

    def at_baseline(concept, table, label):
        """Value at the visit closest to randomization (paper's baseline)."""
        f = 'measurement' if table == 'measurement' else 'observation'
        d = q(f"""select t.person_id, t.{f}_date::date as d, t.value_as_number as val
                  from dbo.{table} t where t.{f}_concept_id = {concept}""")
        d = d.merge(arm[['person_id', 'rand_date']], on='person_id')
        d['gap'] = (pd.to_datetime(d.d) - pd.to_datetime(d.rand_date)).abs().dt.days
        d = d.sort_values('gap').drop_duplicates('person_id')
        return d[['person_id', 'val']].rename(columns={'val': label})

    subject_level = [
        (f"""select distinct on (person_id) person_id, value_as_number
             from dbo.observation where observation_concept_id = {EDUCATION}
             order by person_id""", 'edu'),
        (f"""select person_id, bool_or(value_as_concept_id = {YES})
             from dbo.observation
             where observation_concept_id in {FAMHX} group by person_id""", 'fh'),
        # ADQS source filter: the central lab also reports 3029139 per-visit
        (f"""select distinct on (person_id) person_id, value_source_value
             from dbo.measurement
             where measurement_concept_id = {APOE_GENO}
               and measurement_source_value like 'ADQS:%%'
             order by person_id""", 'geno'),
        (f"""select distinct on (person_id) person_id, value_as_concept_id = {YES}
             from dbo.measurement where measurement_concept_id = {APOE_CARRIER}
             order by person_id""", 'carrier'),
        # Screening composite SUVR (earliest Composite_Summary row)
        (f"""select distinct on (person_id) person_id, value_as_number
             from dbo.measurement
             where measurement_concept_id = {AMYLOID_SUVR}
               and measurement_source_value like '%%Composite_Summary%%'
             order by person_id, measurement_date""", 'suvr'),
    ]
    for sql, label in subject_level:
        df = df.merge(one_per_person(sql, label), on='person_id', how='left')

    for concept, table, label in [
            (PACC_RAW, 'measurement', 'pacc'), (LMDR, 'measurement', 'lmdr'),
            (MMSE_TOTAL, 'observation', 'mmse'), (CFI_PT, 'measurement', 'cfi_pt'),
            (CFI_SP, 'measurement', 'cfi_sp'), (ADL_SP, 'measurement', 'adl_sp'),
            (CDR_SB, 'measurement', 'cdrsb')]:
        df = df.merge(at_baseline(concept, table, label), on='person_id', how='left')

    df['centiloid'] = 183.07 * df.suvr - 177.26
    df['cfi_comb'] = df.cfi_pt + df.cfi_sp
    return df


def summarize(df):
    def ms(s, d=1):
        return f"{s.mean():.{d}f}±{s.std():.{d}f}"

    def np_(mask, n):
        k = int(mask.sum())
        return f"{k} ({100 * k / n:.1f})"

    cols = {}
    for a in ['Solanezumab', 'Placebo']:
        g = df[df.arm == a]
        n = len(g)
        r = {'N': str(n), 'Age — yr': ms(g.age), 'Female — no. (%)': np_(g.female, n),
             'Education — yr': ms(g.edu),
             'White': np_(g.race_concept_id.eq(8527), n),
             'Black': np_(g.race_concept_id.eq(8516), n),
             'Asian': np_(g.race_concept_id.eq(8515), n),
             'Other or missing': np_(~g.race_concept_id.isin([8527, 8516, 8515]), n),
             'Not Hispanic or Latino': np_(g.ethnicity_concept_id.eq(38003564), n),
             'Hispanic or Latino': np_(g.ethnicity_concept_id.eq(38003563), n),
             'Ethnicity unknown': np_(g.ethnicity_concept_id.eq(0), n),
             'Family history of dementia': np_(g.fh.fillna(False).astype(bool), n)}
        for gg in ['E2/E2', 'E2/E3', 'E2/E4', 'E3/E3', 'E3/E4', 'E4/E4']:
            r[f'ApoE {gg.lower().replace("E", "e", 2)}'] = np_(g.geno.eq(gg), n)
        r['ApoE e4 carrier'] = np_(g.carrier.fillna(False).astype(bool), n)
        r['Amyloid SUVR'] = ms(g.suvr)
        r['Centiloids'] = ms(g.centiloid)
        r['PACC score'] = ms(g.pacc)
        r['LMDR score'] = ms(g.lmdr)
        r['MMSE score'] = ms(g.mmse)
        r['CFI combined score'] = ms(g.cfi_comb)
        r['ADL partner score'] = ms(g.adl_sp)
        r['CDR-SB score'] = ms(g.cdrsb)
        cols[a] = r
    return cols


def main():
    conn = connect()
    try:
        df = build(conn)
    finally:
        conn.close()
    cols = summarize(df)
    out = pd.DataFrame({
        'OMOP: Solanezumab': pd.Series(cols['Solanezumab']),
        'Published: Sola': pd.Series({k: v[0] for k, v in PUBLISHED.items()}),
        'OMOP: Placebo': pd.Series(cols['Placebo']),
        'Published: Placebo': pd.Series({k: v[1] for k, v in PUBLISHED.items()}),
    })
    print("Table 1 reproduction — A4 (NEJMoa2305032) vs OMOP CDM (a4.dbo)")
    print("OMOP columns are the full randomized cohort; published are mITT.\n")
    print(out.to_string())
    out.to_csv(BASE / 'analyses' / 'results' / 'table1_reproduction.csv')
    print("\nWritten: analyses/results/table1_reproduction.csv")


if __name__ == '__main__':
    main()
