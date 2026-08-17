"""
Observation domain ETL functions for the A4/LEARN OMOP pipeline.

Creates OMOP OBSERVATION records from lifestyle habits, family history,
study milestones, C-SSRS assessments, study partner info, and secondary
research questionnaires.
"""

import pandas as pd

from . import concepts
from .helpers import (
    prepare_source_df, calc_days_to_date,
    build_observation_record, finalize_observation_df,
    safe_float, concat_and_assign_ids,
)


def create_observation_lifestyle(
    habits_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION records from habits.csv.

    Source: habits.csv | Filter: DONE=1 | Date: visit_start_date

    Field Mappings (concept_maps/observations.csv, group=lifestyle):
        SMOKE    -> Tobacco smoking status (43054909)
        ALCOHOL  -> Alcoholic drinks per day (44786671)
        CAFFEINE -> Caffeinated beverages per day (40767275)
        AEROBIC  -> Active physical exercise (4312325)
        WALKING  -> Walking exercise frequency (2100000300)
        SLEEP    -> Sleep duration (40768255)
        SLEEPDAY -> Daytime nap duration (40768262)
        SUBUSE   -> Substance use behavior (37162238)
    """
    OBSERVATION_CONCEPTS = concepts.load_observation_concepts()

    habits_filtered = habits_df[habits_df['DONE'] == 1].copy()
    print(f"  Habits: {len(habits_df)} total -> {len(habits_filtered)} (DONE=1)")

    habits_filtered = _with_visit_dates(habits_filtered, person_df, date_anchor_df,
                                        visit_occurrence_df, 'habits')

    lifestyle_cols = ['SMOKE', 'ALCOHOL', 'CAFFEINE', 'AEROBIC', 'WALKING', 'SLEEP', 'SLEEPDAY', 'SUBUSE']
    observations = []

    for _, row in habits_filtered.iterrows():
        for col in lifestyle_cols:
            if pd.notna(row.get(col)):
                concept = OBSERVATION_CONCEPTS.get(col, {})
                # Units are per-field and come from concept_maps/observations.csv:
                # SLEEP is hours, SLEEPDAY and WALKING are minutes.
                unit_concept_id = concept.get('unit_concept_id', 0)
                unit_source_value = concept.get('unit')
                observations.append(build_observation_record(
                    person_id=row['person_id'],
                    observation_concept_id=concept.get('concept_id', 0),
                    observation_date=row.get('visit_start_date'),
                    value_as_number=float(row[col]),
                    visit_occurrence_id=row.get('visit_occurrence_id'),
                    observation_source_value=f'HABITS:{col}',
                    unit_source_value=unit_source_value,
                    unit_concept_id=unit_concept_id,
                ))

    observation_df = pd.DataFrame(observations)
    observation_df = finalize_observation_df(observation_df)

    print(f"  Created {len(observation_df)} lifestyle observations")
    return observation_df


def _with_visit_dates(df, person_df, date_anchor_df, visit_occurrence_df, label):
    """Merge person, date anchor and visit, keeping only rows with a visit date.

    Most of these source files carry no date column of their own, only VISCODE, so the
    assessment date comes from visit_occurrence via (BID, VISCODE). observation_date is
    NOT NULL in OMOP CDM; rows whose visit cannot be resolved are dropped and counted
    rather than given a substitute date.
    """
    merged = prepare_source_df(df, person_df, date_anchor_df, visit_occurrence_df,
                               visit_extra_cols=['visit_start_date'])
    total = len(merged)
    resolved = merged[merged['visit_start_date'].notna()].copy()
    dropped = total - len(resolved)
    if dropped:
        print(f"  {label}: dropped {dropped:,} of {total:,} rows with no resolvable visit date")
    return resolved


def create_observation_family_history(
    famhxpar_df: pd.DataFrame,
    famhxsib_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION records from family history files.

    Sources: famhxpar.csv (parents), famhxsib.csv (siblings) | Date: visit_start_date

    Field Mappings (concept_maps/observations.csv, group=family_history):
        All use concept_id 4167217 (Family history of clinical finding)
        with condition detail in observation_source_value.
    """
    OBSERVATION_CONCEPTS = concepts.load_observation_concepts()

    observations = []

    # ---- Parental history ----
    fampar = _with_visit_dates(famhxpar_df.copy(), person_df, date_anchor_df, visit_occurrence_df, 'famhxpar')

    for _, row in fampar.iterrows():
        # Mother
        if row.get('MOTHER') in (0, 1):  # 1=Yes, 0=No
            concept = OBSERVATION_CONCEPTS['FAMHX_MOTHER']
            observations.append(build_observation_record(
                person_id=row['person_id'],
                observation_concept_id=concept['concept_id'],
                observation_date=row['visit_start_date'],
                visit_occurrence_id=row.get('visit_occurrence_id'),
                value_as_number=float(row['MOTHER']),
                value_as_string='Yes' if row['MOTHER'] == 1 else 'No',
                value_as_concept_id=4188539 if row['MOTHER'] == 1 else 4188540,
                observation_source_value='FAMHX:MOTHER',
            ))
        # Father
        if row.get('FATHER') in (0, 1):  # 1=Yes, 0=No
            concept = OBSERVATION_CONCEPTS['FAMHX_FATHER']
            observations.append(build_observation_record(
                person_id=row['person_id'],
                observation_concept_id=concept['concept_id'],
                observation_date=row['visit_start_date'],
                visit_occurrence_id=row.get('visit_occurrence_id'),
                value_as_number=float(row['FATHER']),
                value_as_string='Yes' if row['FATHER'] == 1 else 'No',
                value_as_concept_id=4188539 if row['FATHER'] == 1 else 4188540,
                observation_source_value='FAMHX:FATHER',
            ))

    parent_count = len(observations)
    print(f"  Parental history: {len(famhxpar_df)} rows -> {parent_count} observations")

    # ---- Sibling history ----
    famsib = _with_visit_dates(famhxsib_df.copy(), person_df, date_anchor_df, visit_occurrence_df, 'famhxsib')

    concept = OBSERVATION_CONCEPTS['FAMHX_SIBLING']
    for _, row in famsib.iterrows():
        # SIBDEMENT: 1=Yes, 0=No
        if row.get('SIBDEMENT') in (0, 1):
            observations.append(build_observation_record(
                person_id=row['person_id'],
                observation_concept_id=concept['concept_id'],
                observation_date=row['visit_start_date'],
                visit_occurrence_id=row.get('visit_occurrence_id'),
                value_as_number=float(row['SIBDEMENT']),
                value_as_string='Yes' if row['SIBDEMENT'] == 1 else 'No',
                value_as_concept_id=4188539 if row['SIBDEMENT'] == 1 else 4188540,
                observation_source_value=f"FAMHX:SIBLING_{row.get('RECNO', 'unknown')}",
            ))

    sibling_count = len(observations) - parent_count
    print(f"  Sibling history: {len(famhxsib_df)} rows -> {sibling_count} observations")

    observation_df = pd.DataFrame(observations)
    observation_df = finalize_observation_df(observation_df)

    print(f"Created family history OBSERVATION with {len(observation_df)} total records")
    return observation_df


def create_observation(
    habits_df: pd.DataFrame,
    famhxpar_df: pd.DataFrame,
    famhxsib_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Create combined OMOP OBSERVATION table.
    """
    lifestyle_obs = create_observation_lifestyle(
        habits_df, person_df, visit_occurrence_df, date_anchor_df
    )

    family_obs = create_observation_family_history(
        famhxpar_df, famhxsib_df, person_df, date_anchor_df, visit_occurrence_df
    )

    observation = concat_and_assign_ids([lifestyle_obs, family_obs], 'observation_id')

    print(f"Created OBSERVATION table with {len(observation)} total records")
    return observation


def create_observation_milestones(
    ds_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION records from DS.csv (Disposition).

    Source: ds.csv | Date: DS_DAYS_CONSENT

    Field Mappings (concept_maps/milestones.csv, 16 entries):
        DSDECOD lookup -> milestone concept_id
        (e.g. RANDOMIZED=2000000010, COMPLETED=2000000011, DEATH=4306655)
    """
    MILESTONE_CONCEPTS = concepts.load_milestone_concepts()

    observations = []

    ds_merged = prepare_source_df(ds_df, person_df, date_anchor_df)

    print(f"  DS milestones: {len(ds_df)} total -> {len(ds_merged)} matched to persons")

    # Track milestone counts
    milestone_counts = {}

    for _, row in ds_merged.iterrows():
        dsdecod = row.get('DSDECOD', '')
        if pd.isna(dsdecod):
            continue

        concept_info = MILESTONE_CONCEPTS.get(dsdecod, {'concept_id': 0, 'name': dsdecod})

        # Calculate observation date
        obs_date = calc_days_to_date(row, 'DSSTDTC_DAYS_CONSENT') or row['synthetic_consent_date']

        observations.append(build_observation_record(
            person_id=row['person_id'],
            observation_concept_id=concept_info['concept_id'],
            observation_date=obs_date,
            value_as_string=dsdecod,
            value_as_concept_id=0,
            observation_source_value=f"DS:{dsdecod}:{row.get('DSCAT', '')}:{row.get('EPOCH', '')}",
            qualifier_source_value=row.get('DSCAT', ''),
        ))

        milestone_counts[dsdecod] = milestone_counts.get(dsdecod, 0) + 1

    observation_df = pd.DataFrame(observations) if observations else pd.DataFrame()
    observation_df = finalize_observation_df(observation_df)

    # Print milestone summary
    print("  Milestone counts:")
    for milestone, count in sorted(milestone_counts.items(), key=lambda x: -x[1])[:8]:
        print(f"    {milestone}: {count}")

    print(f"Created milestone OBSERVATION with {len(observation_df)} records")
    return observation_df


def create_observation_cssrs(
    cssrs_df: pd.DataFrame,
    cssrslv_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION records from C-SSRS files (full detail).

    Sources: cssrs.csv (current visit), cssrslv.csv (lifetime)
    Date: visit_start_date

    Field Mappings (concept_maps/cssrs.csv, 30 entries):
        Ideation: WISHLIFE, ACTLIFE, METHOD, INTENT, PLAN
        Attempts: ATTMPT, ATTMPT5, ATTMPTN
        Behavior: INTER, ABORT, PREP, BEHAVLIF + counts
        Severity/Intensity: SEVLIFE, FREQLIF, DURATLIF, CONTROLLIF, etc.
        Lethality: RECENTDAM/POT, LETHALDAM/POT, FIRSTDAM/POT
    Column remapping for cssrslv via concept_maps/cssrslv_columns.csv
    """
    CSSRS_CONCEPTS = concepts.load_cssrs_concepts()
    CSSRSLV_COLUMN_MAP = concepts.load_cssrslv_column_map()

    observations = []

    # Items to extract from each file (using standard concept keys)
    cssrs_items = ['WISHLIFE', 'ACTLIFE', 'METHOD', 'INTENT', 'PLAN',
                   'ATTMPT', 'ATTMPT5', 'ATTMPTN', 'NONSUI', 'NONSUI5',
                   'INTER', 'ABORT', 'PREP', 'BEHAVLIF', 'SEVLIFE',
                   'RECENTDAM', 'RECENTPOT', 'LETHALDAM', 'LETHALPOT']

    # Items for lifetime file (subset - no ATTMPT5/NONSUI5/BEHAVLIF)
    cssrslv_items = ['WISHLIFE', 'ACTLIFE', 'METHOD', 'INTENT', 'PLAN',
                     'ATTMPT', 'ATTMPTN', 'NONSUI', 'INTER', 'ABORT',
                     'PREP', 'SEVLIFE', 'RECENTDAM', 'RECENTPOT', 'SUICIDE']

    def process_cssrs(df, file_name, items, col_map=None, qualifier_concept_id=None, qualifier_label=None):
        nonlocal observations
        merged = _with_visit_dates(df, person_df, date_anchor_df, visit_occurrence_df, file_name)
        print(f"  {file_name}: {len(df)} total -> {len(merged)} matched")

        count = 0
        for _, row in merged.iterrows():
            for concept_key in items:
                # Map concept key to actual column name in this file
                if col_map:
                    src_col = None
                    for src, tgt in col_map.items():
                        if tgt == concept_key:
                            src_col = src
                            break
                    if src_col is None:
                        continue
                else:
                    src_col = concept_key

                if src_col in row and pd.notna(row[src_col]):
                    concept = CSSRS_CONCEPTS.get(concept_key, {'concept_id': 0, 'name': f'C-SSRS {concept_key}'})
                    val = row[src_col]
                    observations.append(build_observation_record(
                        person_id=row['person_id'],
                        observation_concept_id=concept['concept_id'],
                        observation_date=row['visit_start_date'],
                        visit_occurrence_id=row.get('visit_occurrence_id'),
                        value_as_number=float(val) if not isinstance(val, str) else None,
                        value_as_string=str(val),
                        value_as_concept_id=4188539 if val == 1 else 4188540 if val == 0 else 0,
                        qualifier_concept_id=qualifier_concept_id,
                        observation_source_value=f"{file_name}:{concept_key}",
                        qualifier_source_value=qualifier_label,
                    ))
                    count += 1
        return count

    # cssrs.csv is the baseline form (VISCODE=1) and its items ask about the lifetime
    # (WISHLIFE, SEVLIFE, ...). cssrslv.csv is the follow-up form and covers the interval
    # since the last visit (WISHLV, SEVLV, ...).
    #
    # qualifier_concept_id is left NULL: OMOP has no qualifier concept for these recall
    # windows. LOINC encodes the window in the concept itself (...Lifetime, ...1 month)
    # and has no "since last visit" concept, so the two forms still share concept_ids.
    lifetime_count = process_cssrs(cssrs_df, 'CSSRS|Baseline', cssrs_items,
                                   qualifier_concept_id=None, qualifier_label='Lifetime')
    interval_count = process_cssrs(cssrslv_df, 'CSSRSLV|SinceLastVisit', cssrslv_items, col_map=CSSRSLV_COLUMN_MAP,
                                   qualifier_concept_id=None, qualifier_label='Since last visit')

    observation_df = pd.DataFrame(observations) if observations else pd.DataFrame()
    observation_df = finalize_observation_df(observation_df)

    print(f"Created C-SSRS OBSERVATION with {len(observation_df)} records (Lifetime: {lifetime_count}, Since last visit: {interval_count})")
    return observation_df


def create_observation_study_partner(
    spinfo_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Create OMOP OBSERVATION records from study partner information.

    Source: spinfo.csv | Date: visit_start_date

    Field Mappings (concept_maps/observations.csv, group=study_partner):
        RELATIONSHIP  -> Study Partner Relationship (2100000080)
        COHABITATION  -> Study Partner Cohabitation (2100000082)
        SP_AGE        -> Study Partner Age (2100000083)
        SP_GENDER     -> Study Partner Gender (2100000084)
    """
    STUDY_PARTNER_CONCEPTS = concepts.load_study_partner_concepts()

    observations = []

    merged = _with_visit_dates(spinfo_df, person_df, date_anchor_df, visit_occurrence_df, 'spinfo')
    print(f"  Study Partner Info: {len(spinfo_df)} total -> {len(merged)} matched")

    for _, row in merged.iterrows():
        # Relationship
        if pd.notna(row.get('INFRELAT')):
            observations.append(build_observation_record(
                person_id=row['person_id'],
                observation_concept_id=STUDY_PARTNER_CONCEPTS['RELATIONSHIP']['concept_id'],
                observation_date=row['visit_start_date'],
                visit_occurrence_id=row.get('visit_occurrence_id'),
                value_as_number=float(row['INFRELAT']),
                value_as_string=f"Relationship code {int(row['INFRELAT'])}",
                value_as_concept_id=0,
                observation_source_value=f"SPINFO:BPID={row.get('BPID', 'NA')}:INFRELAT",
            ))

        # Contact hours — moved to MEASUREMENT domain (numeric value)
        # See measurement_questionnaire_scores.py

        # Cohabitation
        if pd.notna(row.get('INFLIVE')):
            observations.append(build_observation_record(
                person_id=row['person_id'],
                observation_concept_id=STUDY_PARTNER_CONCEPTS['COHABITATION']['concept_id'],
                observation_date=row['visit_start_date'],
                visit_occurrence_id=row.get('visit_occurrence_id'),
                value_as_number=float(row['INFLIVE']),
                value_as_string='Lives with participant' if row['INFLIVE'] == 1 else 'Does not live with participant',
                value_as_concept_id=4188539 if row['INFLIVE'] == 1 else 4188540,
                observation_source_value=f"SPINFO:BPID={row.get('BPID', 'NA')}:INFLIVE",
            ))

    observation_df = pd.DataFrame(observations) if observations else pd.DataFrame()
    observation_df = finalize_observation_df(observation_df)

    print(f"Created study partner OBSERVATION with {len(observation_df)} records")
    return observation_df


def create_observation_secondary_questionnaires(
    ies_df: pd.DataFrame,
    ftpscale_df: pd.DataFrame,
    rss_df: pd.DataFrame,
    views_df: pd.DataFrame,
    ruib_df: pd.DataFrame,
    ruib1_df: pd.DataFrame,
    person_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Create OBSERVATION records from secondary research questionnaires.

    Sources: ies.csv, ftpscale.csv, rss.csv, views.csv, ruib.csv, ruib1.csv

    Field Mappings (concept_maps/questionnaires.csv, group=secondary):
        IES items (15) -> LOINC 1761xxx (individual item scores, NOT total)
        FTP (11 items) -> FTP_METHOD (2100000201) + 10 item-level (2100000217-226)
        RSS (12 items) -> RSS_QUALITY/RECOMMEND + RSSTST (4322976) + 9 custom (2100000227-235)
        VIEWS (10 items) -> VIEWS_SEEK (2100000204) + 9 item-level (2100000236-244)
        RUIB indicators -> RUIB_ADMIT, RUIB_VOLUNTEER (4074926), RUIB_EMPLOY (4235700)
        RUIB hours     -> EMPHRS/VOLHRS (44786817)
        RUIB1_TYPE     -> Hospital Stay Type (2100000209)

    Note: IESCORE total and BR1NIGHT count moved to measurement domain.
    """
    SECONDARY_QUESTIONNAIRE_CONCEPTS = concepts.load_secondary_questionnaire_concepts()

    observations = []

    # --- IES: Individual items as OBSERVATION, IESCORE total in MEASUREMENT ---
    print(f"  IES: {len(ies_df)} total rows")
    ies_done = ies_df[ies_df['DONE'] == 1].copy() if 'DONE' in ies_df.columns else ies_df.copy()
    ies_merged = _with_visit_dates(ies_done, person_df, date_anchor_df, visit_occurrence_df, 'ies')
    ies_fields = {
        'IETHINK': 'IETHINK', 'IEAVOID': 'IEAVOID', 'IEREMOVE': 'IEREMOVE',
        'IESLEEP': 'IESLEEP', 'IEWAVES': 'IEWAVES', 'IEDREAMS': 'IEDREAMS',
        'IEAWAY': 'IEAWAY', 'IEREAL': 'IEREAL', 'IETALK': 'IETALK',
        'IEMIND': 'IEMIND', 'IETHINGS': 'IETHINGS', 'IEDEAL': 'IEDEAL',
        'IENOTTHNK': 'IENOTTHNK', 'IEREMIND': 'IEREMIND', 'IENUMB': 'IENUMB',
    }
    ies_count = 0
    for _, row in ies_merged.iterrows():
        for src_col, concept_key in ies_fields.items():
            val = safe_float(row.get(src_col))
            if val is not None:
                concept = SECONDARY_QUESTIONNAIRE_CONCEPTS.get(concept_key)
                if concept:
                    observations.append(build_observation_record(
                        person_id=row['person_id'],
                        observation_concept_id=concept['concept_id'],
                        observation_date=row['visit_start_date'],
                        visit_occurrence_id=row.get('visit_occurrence_id'),
                        value_as_number=val,
                        observation_source_value=f"IES:{src_col}:{row.get('VISCODE', 'NA')}",
                        unit_source_value='scale',
                    ))
                    ies_count += 1

    # --- FTP: Future Time Perspective (all items) ---
    print(f"  FTP: {len(ftpscale_df)} total rows")
    ftp_done = ftpscale_df[ftpscale_df['DONE'] == 1].copy() if 'DONE' in ftpscale_df.columns else ftpscale_df.copy()
    ftp_merged = _with_visit_dates(ftp_done, person_df, date_anchor_df, visit_occurrence_df, 'ftp')
    ftp_fields = {
        'FTMETHOD': 'FTP_METHOD', 'FTOPPS': 'FTOPPS', 'FTGOAL': 'FTGOAL',
        'FTPOSSBL': 'FTPOSSBL', 'FTLIFE': 'FTLIFE', 'FTINFINIT': 'FTINFINIT',
        'FTANYTHNG': 'FTANYTHNG', 'FTNEW': 'FTNEW', 'FTRUNOUT': 'FTRUNOUT',
        'FTLIMIT': 'FTLIMIT', 'FTGETOLD': 'FTGETOLD',
    }
    ftp_count = 0
    for _, row in ftp_merged.iterrows():
        for src_col, concept_key in ftp_fields.items():
            val = safe_float(row.get(src_col))
            if val is not None:
                concept = SECONDARY_QUESTIONNAIRE_CONCEPTS.get(concept_key)
                if concept:
                    observations.append(build_observation_record(
                        person_id=row['person_id'],
                        observation_concept_id=concept['concept_id'],
                        observation_date=row['visit_start_date'],
                        visit_occurrence_id=row.get('visit_occurrence_id'),
                        value_as_number=val,
                        observation_source_value=f"FTP:{src_col}:{row.get('VISCODE', 'NA')}",
                        unit_source_value='scale',
                    ))
                    ftp_count += 1

    # --- RSS: Research Satisfaction Scale (all items) ---
    print(f"  RSS: {len(rss_df)} total rows")
    rss_done = rss_df[rss_df['DONE'] == 1].copy() if 'DONE' in rss_df.columns else rss_df.copy()
    rss_merged = _with_visit_dates(rss_done, person_df, date_anchor_df, visit_occurrence_df, 'rss')
    rss_fields = {
        'RSSQUAL': 'RSS_QUALITY', 'RSSRECOM': 'RSS_RECOMMEND',
        'RSSCOMP': 'RSSCOMP', 'RSSEXPECT': 'RSSEXPECT', 'RSSREDO': 'RSSREDO',
        'RSSBEST': 'RSSBEST', 'RSSLEAST': 'RSSLEAST', 'RSSMED': 'RSSMED',
        'RSSTST': 'RSSTST', 'RSSVIS': 'RSSVIS', 'RSSOTH': 'RSSOTH',
        'RSSIPAD': 'RSSIPAD',
    }
    rss_count = 0
    for _, row in rss_merged.iterrows():
        for src_col, concept_key in rss_fields.items():
            val = safe_float(row.get(src_col))
            if val is not None:
                concept = SECONDARY_QUESTIONNAIRE_CONCEPTS.get(concept_key)
                if concept:
                    observations.append(build_observation_record(
                        person_id=row['person_id'],
                        observation_concept_id=concept['concept_id'],
                        observation_date=row['visit_start_date'],
                        visit_occurrence_id=row.get('visit_occurrence_id'),
                        value_as_number=val,
                        observation_source_value=f"RSS:{src_col}:{row.get('VISCODE', 'NA')}",
                        unit_source_value='scale',
                    ))
                    rss_count += 1

    # --- VIEWS: Views on Research Participation (all items) ---
    print(f"  VIEWS: {len(views_df)} total rows")
    views_done = views_df[views_df['DONE'] == 1].copy() if 'DONE' in views_df.columns else views_df.copy()
    views_merged = _with_visit_dates(views_done, person_df, date_anchor_df, visit_occurrence_df, 'views')
    views_fields = {
        'VSEEK': 'VIEWS_SEEK', 'VEASE': 'VEASE', 'VRISK': 'VRISK',
        'VPART': 'VPART', 'VCNTRB': 'VCNTRB', 'VAFFAIR': 'VAFFAIR',
        'VCNFRM': 'VCNFRM', 'VPREP': 'VPREP', 'VCURIOUS': 'VCURIOUS',
        'VOTHER': 'VOTHER',
    }
    views_count = 0
    for _, row in views_merged.iterrows():
        for src_col, concept_key in views_fields.items():
            val = safe_float(row.get(src_col))
            if val is not None:
                concept = SECONDARY_QUESTIONNAIRE_CONCEPTS.get(concept_key)
                if concept:
                    observations.append(build_observation_record(
                        person_id=row['person_id'],
                        observation_concept_id=concept['concept_id'],
                        observation_date=row['visit_start_date'],
                        visit_occurrence_id=row.get('visit_occurrence_id'),
                        value_as_number=val,
                        observation_source_value=f"VIEWS:{src_col}:{row.get('VISCODE', 'NA')}",
                        unit_source_value='scale',
                    ))
                    views_count += 1

    # --- RUIB: Resource Utilization ---
    print(f"  RUIB: {len(ruib_df)} total rows")
    ruib_done = ruib_df[ruib_df['DONE'] == 1].copy() if 'DONE' in ruib_df.columns else ruib_df.copy()
    ruib_merged = _with_visit_dates(ruib_done, person_df, date_anchor_df, visit_occurrence_df, 'ruib')
    ruib_count = 0
    for _, row in ruib_merged.iterrows():
        # Hospital admission indicator
        val = safe_float(row.get('BRADMIT'))
        if val is not None:
            observations.append(build_observation_record(
                person_id=row['person_id'],
                observation_concept_id=SECONDARY_QUESTIONNAIRE_CONCEPTS['RUIB_ADMIT']['concept_id'],
                observation_date=row['visit_start_date'],
                visit_occurrence_id=row.get('visit_occurrence_id'),
                value_as_number=val,
                value_as_string='Yes' if val == 1 else 'No',
                value_as_concept_id=4188539 if val == 1 else 4188540,
                observation_source_value=f"RUIB:BRADMIT:{row.get('VISCODE', 'NA')}",
                unit_source_value='binary',
            ))
            ruib_count += 1

        # Volunteer work
        val = safe_float(row.get('VOLUNTEER'))
        if val is not None:
            observations.append(build_observation_record(
                person_id=row['person_id'],
                observation_concept_id=SECONDARY_QUESTIONNAIRE_CONCEPTS['RUIB_VOLUNTEER']['concept_id'],
                observation_date=row['visit_start_date'],
                visit_occurrence_id=row.get('visit_occurrence_id'),
                value_as_number=val,
                value_as_string='Yes' if val == 1 else 'No',
                value_as_concept_id=4188539 if val == 1 else 4188540,
                observation_source_value=f"RUIB:VOLUNTEER:{row.get('VISCODE', 'NA')}",
                unit_source_value='binary',
            ))
            ruib_count += 1

        # Employment
        val = safe_float(row.get('EMPLOY'))
        if val is not None:
            observations.append(build_observation_record(
                person_id=row['person_id'],
                observation_concept_id=SECONDARY_QUESTIONNAIRE_CONCEPTS['RUIB_EMPLOY']['concept_id'],
                observation_date=row['visit_start_date'],
                visit_occurrence_id=row.get('visit_occurrence_id'),
                value_as_number=val,
                value_as_string='Yes' if val == 1 else 'No',
                value_as_concept_id=4188539 if val == 1 else 4188540,
                observation_source_value=f"RUIB:EMPLOY:{row.get('VISCODE', 'NA')}",
                unit_source_value='binary',
            ))
            ruib_count += 1

        # Volunteer hours
        val = safe_float(row.get('VOLHRS'))
        if val is not None:
            concept = SECONDARY_QUESTIONNAIRE_CONCEPTS.get('VOLHRS')
            if concept:
                observations.append(build_observation_record(
                    person_id=row['person_id'],
                    observation_concept_id=concept['concept_id'],
                    observation_date=row['visit_start_date'],
                    visit_occurrence_id=row.get('visit_occurrence_id'),
                    value_as_number=val,
                    observation_source_value=f"RUIB:VOLHRS:{row.get('VISCODE', 'NA')}",
                    unit_source_value='hours',
                    unit_concept_id=8505,
                ))
                ruib_count += 1

        # Employment hours
        val = safe_float(row.get('EMPHRS'))
        if val is not None:
            concept = SECONDARY_QUESTIONNAIRE_CONCEPTS.get('EMPHRS')
            if concept:
                observations.append(build_observation_record(
                    person_id=row['person_id'],
                    observation_concept_id=concept['concept_id'],
                    observation_date=row['visit_start_date'],
                    visit_occurrence_id=row.get('visit_occurrence_id'),
                    value_as_number=val,
                    observation_source_value=f"RUIB:EMPHRS:{row.get('VISCODE', 'NA')}",
                    unit_source_value='hours',
                    unit_concept_id=8505,
                ))
                ruib_count += 1

    # --- RUIB1: Hospital Overnight Stays ---
    print(f"  RUIB1: {len(ruib1_df)} total rows")
    ruib1_merged = _with_visit_dates(ruib1_df, person_df, date_anchor_df, visit_occurrence_df, 'ruib1')
    ruib1_count = 0
    for _, row in ruib1_merged.iterrows():
        # BR1NIGHT (number of nights) — moved to MEASUREMENT domain
        # See measurement_questionnaire_scores.py

        # Type of stay
        val = safe_float(row.get('BR1TYPE'))
        if val is not None:
            observations.append(build_observation_record(
                person_id=row['person_id'],
                observation_concept_id=SECONDARY_QUESTIONNAIRE_CONCEPTS['RUIB1_TYPE']['concept_id'],
                observation_date=row['visit_start_date'],
                visit_occurrence_id=row.get('visit_occurrence_id'),
                value_as_number=val,
                value_as_string=str(int(val)),
                observation_source_value=f"RUIB1:BR1TYPE:{row.get('VISCODE', 'NA')}",
                unit_source_value='code',
            ))
            ruib1_count += 1

    observation_df = pd.DataFrame(observations) if observations else pd.DataFrame()
    observation_df = finalize_observation_df(observation_df)

    print(f"Created secondary questionnaire OBSERVATION with {len(observation_df)} records")
    print(f"  IES: {ies_count}, FTP: {ftp_count}, RSS: {rss_count}, VIEWS: {views_count}, RUIB: {ruib_count}, RUIB1: {ruib1_count}")
    return observation_df
