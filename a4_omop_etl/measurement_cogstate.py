import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date, finalize_measurement_df, safe_float


def create_measurement_cogstate(
    cogstate_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from COGSTATE_COMPUTERIZED.csv.

    Source: cogstate.csv | Filter: VALUE not null | Date: TESTDATE_DAYS_CONSENT (consent-date fallback)
    Visit linking: VISIT -> visit_occurrence

    Field Mappings (concept_maps/cogstate.csv, group=test,composite):
        DET, IDN, ONB, OCL, CPAL, LNS, FNMT, FNLT, FSBT, BPXT -> individual tests
        COGSTATE_COMPOSITE, C3Comp, C3AbrComp, AttnComp,
        LearnWMComp, OCLONBComp, PsychAttnComp -> composite z-scores
    """
    COGSTATE_CONCEPTS = concepts.load_cogstate_concepts()

    measurements = []

    # Filter for valid test data
    cogstate_filtered = cogstate_df[cogstate_df['VALUE'].notna()].copy()
    print(f"  CogState: {len(cogstate_df)} total -> {len(cogstate_filtered)} with valid VALUE")

    # VISIT holds the numeric visit code and links to visit_occurrence directly.
    # AVISIT is also numeric here, not a visit name.
    cogstate_filtered = cogstate_filtered.copy()
    cogstate_filtered['VISCODE'] = cogstate_filtered['VISIT']
    cogstate_merged = prepare_source_df(
        cogstate_filtered, person_df, date_anchor_df, visit_occurrence_df
    )

    linked = cogstate_merged['visit_occurrence_id'].notna().mean()
    print(f"  CogState visit linkage: {linked:.2%}")
    if linked < 0.90:
        print(f"  WARNING: CogState visit linkage only {linked:.1%}; check VISIT codes")

    # Calculate test date
    cogstate_merged['measurement_date'] = cogstate_merged.apply(
        lambda row: (calc_days_to_date(row, 'TESTDATE_DAYS_CONSENT') or row['synthetic_consent_date']),
        axis=1
    )

    # Get unique test codes
    test_codes = cogstate_merged['TESTCD'].unique()
    print(f"  Found {len(test_codes)} unique test codes: {test_codes[:10]}...")

    for _, row in cogstate_merged.iterrows():
        test_code = row['TESTCD']
        concept_info = COGSTATE_CONCEPTS.get(test_code, {'concept_id': 0, 'name': f'CogState {test_code}', 'unit': 'score'})

        measurements.append({
            'person_id': row['person_id'],
            'measurement_concept_id': concept_info['concept_id'],
            'measurement_date': row['measurement_date'],
            'value_as_number': float(row['VALUE']) if pd.notna(row['VALUE']) else None,
            'unit_source_value': concept_info['unit'],
            'visit_occurrence_id': row.get('visit_occurrence_id'),
            'measurement_source_value': f"COGSTATE:{test_code}:{row.get('TRIAL', '')}",
        })

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"Created CogState MEASUREMENT with {len(measurement_df)} records")
    return measurement_df


def create_measurement_cogstate_battery(
    battery_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from cogstate_battery.csv for BPET/FNFT tests.

    Source: cogstate_battery.csv | Filter: TCode in (BPET, FNFT) + QC | Date: TDate_DAYS_CONSENT (no fallback)

    Field Mappings (concept_maps/cogstate.csv, group=battery,battery_metric):
        BPET/FNFT acc    -> 2100000147/2100000148 (arcsine(sqrt(proportion)))
        BPET/FNFT lmn    -> 2100000270/2100000274 (log10(ms))
        BPET/FNFT cor    -> 2100000271/2100000275 (count)
        BPET/FNFT err    -> 2100000272/2100000276 (count)
    """
    COGSTATE_CONCEPTS = concepts.load_cogstate_battery_concepts()
    BATTERY_METRIC_CONCEPTS = concepts.load_cogstate_battery_metric_concepts()

    # Filter to only BPET and FNFT (not in COGSTATE_COMPUTERIZED)
    battery_filtered = battery_df[battery_df['TCode'].isin(['BPET', 'FNFT'])].copy()

    # QC per the external data dictionary: ExcludeData=1 means exclude,
    # Completion/SessionCompletion 1 means fail (0 = pass). NaN flags pass.
    qc_fail = (
        (battery_filtered['ExcludeData'] == 1)
        | (battery_filtered['Completion'] == 1)
        | (battery_filtered['SessionCompletion'] == 1)
    )
    battery_filtered = battery_filtered[~qc_fail]
    print(f"  CogState Battery: {len(battery_df)} total -> {len(battery_filtered)} "
          f"BPET/FNFT rows passing QC ({int(qc_fail.sum())} failed-QC rows dropped)")

    merged = prepare_source_df(battery_filtered, person_df, date_anchor_df, visit_occurrence_df)

    # No fallback: an undated row is dropped downstream rather than misdated.
    merged['measurement_date'] = merged.apply(
        calc_days_to_date, args=('TDate_DAYS_CONSENT',), axis=1
    )

    measurements = []
    acc_count = 0
    metric_count = 0

    for _, row in merged.iterrows():
        test_code = row['TCode']
        meas_date = row['measurement_date']
        concept_info = COGSTATE_CONCEPTS.get(test_code, {'concept_id': 0, 'name': f'CogState {test_code}', 'unit': 'score'})

        # Primary metric: accuracy (acc)
        if pd.notna(row.get('acc')):
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept_info['concept_id'],
                'measurement_date': meas_date,
                'value_as_number': float(row['acc']),
                'unit_source_value': concept_info.get('unit', 'score'),
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"COGSTATE_BAT:{test_code}:acc",
            })
            acc_count += 1

        # Expanded metrics: lmn, cor, err (percor exists in the source but is
        # entirely null for BPET/FNFT and has no concept mapped)
        for metric in ['lmn', 'cor', 'err']:
            val = row.get(metric)
            if val is not None and pd.notna(val):
                concept_key = f"{test_code}_{metric}"
                metric_concept = BATTERY_METRIC_CONCEPTS.get(concept_key)
                if metric_concept:
                    measurements.append({
                        'person_id': row['person_id'],
                        'measurement_concept_id': metric_concept['concept_id'],
                        'measurement_date': meas_date,
                        'value_as_number': float(val),
                        'unit_source_value': metric_concept.get('unit', 'score'),
                        'visit_occurrence_id': row.get('visit_occurrence_id'),
                        'measurement_source_value': f"COGSTATE_BAT:{test_code}:{metric}",
                    })
                    metric_count += 1

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"Created CogState Battery MEASUREMENT with {len(measurement_df)} records (acc: {acc_count}, expanded: {metric_count})")
    return measurement_df


def create_measurement_cogstate_questionnaires(
    cogstate_macq_df: pd.DataFrame,
    cogstate_cpath_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create MEASUREMENT records from CogState questionnaire files.

    Sources & Field Mappings (concept_maps/cogstate.csv):
        MACQ   -> MCQT_TOTAL (2100000090) + Q1-Q6 items (2100000280-285)
                  | group=questionnaire,macq_item
        C-PATH -> CPATH_TOTAL (2100000091) + Q1-Q26 items (2100000290-315)
                  + CADL/IF domain scores (2100000316-317)
                  | group=questionnaire,cpath_item,cpath_domain
    """
    COGSTATE_QUESTIONNAIRE_CONCEPTS = concepts.load_cogstate_questionnaire_concepts()
    MACQ_ITEM_CONCEPTS = concepts.load_cogstate_macq_item_concepts()
    CPATH_ITEM_CONCEPTS = concepts.load_cogstate_cpath_item_concepts()

    measurements = []

    # ========== MACQ Processing ==========
    print(f"  MACQ: {len(cogstate_macq_df)} total rows")

    # MACQ Total Scores
    macq_totals = cogstate_macq_df[cogstate_macq_df['Question'] == 'MCQT Total'].copy()
    macq_totals_merged = prepare_source_df(macq_totals, person_df, date_anchor_df, visit_df)
    macq_totals_merged['measurement_date'] = macq_totals_merged.apply(
        lambda row: calc_days_to_date(row, 'Date_DAYS_CONSENT') or row['synthetic_consent_date'], axis=1
    )

    macq_total_count = 0
    for _, row in macq_totals_merged.iterrows():
        value = safe_float(row.get('Score'))
        if value is not None:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': COGSTATE_QUESTIONNAIRE_CONCEPTS['MCQT_TOTAL']['concept_id'],
                'measurement_date': row['measurement_date'],
                'value_as_number': value,
                'unit_source_value': 'score',
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"cogstate_macq:MCQT_Total:{row.get('Session_ID', 'NA')}",
            })
            macq_total_count += 1

    # MACQ Individual Items (Q1-Q6)
    macq_items = cogstate_macq_df[cogstate_macq_df['Question'] != 'MCQT Total'].copy()
    macq_items_merged = prepare_source_df(macq_items, person_df, date_anchor_df, visit_df)
    macq_items_merged['measurement_date'] = macq_items_merged.apply(
        lambda row: calc_days_to_date(row, 'Date_DAYS_CONSENT') or row['synthetic_consent_date'], axis=1
    )

    # Items are keyed on the question text: the file has no question-number
    # column (per the external data dictionary), and text is the identity.
    # The numbering follows the canonical MAC-Q order, which is also the
    # verified presentation order in every session.
    MACQ_QUESTION_NUMBERS = {
        'Remembering the name of a person just introduced to you?': 1,
        'Recalling telephone numbers or postcodes that you use on a daily or weekly basis?': 2,
        'Recalling where you have put objects (such as keys) in your home or office?': 3,
        'Remembering specific facts from a magazine or a newspaper article you have just finished reading?': 4,
        'Remembering the item(s) you intended to buy when you arrive at the grocery store or pharmacy?': 5,
        'In general, how would you describe your memory as compared to when you were in high school?': 6,
    }

    macq_item_count = 0
    macq_unrecognized = 0
    for _, row in macq_items_merged.iterrows():
        q_num = MACQ_QUESTION_NUMBERS.get(str(row.get('Question', '')).strip())
        if q_num is None:
            macq_unrecognized += 1
            continue
        value = safe_float(row.get('Score'))
        if value is not None:
            item_concept = MACQ_ITEM_CONCEPTS.get(f"MACQ_Q{q_num}")
            if item_concept:
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': item_concept['concept_id'],
                    'measurement_date': row['measurement_date'],
                    'value_as_number': value,
                    'unit_source_value': 'score',
                    'visit_occurrence_id': row.get('visit_occurrence_id'),
                    'measurement_source_value': f"cogstate_macq:Q{q_num}:{row.get('Session_ID', 'NA')}",
                })
                macq_item_count += 1

    print(f"  MACQ measurements: totals={macq_total_count}, items={macq_item_count}"
          + (f" ({macq_unrecognized} unrecognized question texts skipped)" if macq_unrecognized else ""))

    # ========== C-PATH Processing ==========
    print(f"  C-PATH: {len(cogstate_cpath_df)} total rows")

    # Filter to valid question rows
    cpath_questions = cogstate_cpath_df[
        cogstate_cpath_df['Question Number'].notna() &
        (cogstate_cpath_df['Question Number'] != 'NA')
    ].copy()
    cpath_questions['Question Number'] = pd.to_numeric(cpath_questions['Question Number'], errors='coerce')
    cpath_questions = cpath_questions[cpath_questions['Question Number'] > 0]
    print(f"  C-PATH valid questions: {len(cpath_questions)} rows")

    cpath_merged = prepare_source_df(cpath_questions, person_df, date_anchor_df, visit_df)
    cpath_merged['measurement_date'] = cpath_merged.apply(
        lambda row: calc_days_to_date(row, 'Date_DAYS_CONSENT') or row['synthetic_consent_date'], axis=1
    )

    # C-PATH Individual Items (Q1-Q26)
    cpath_item_count = 0
    for _, row in cpath_merged.iterrows():
        q_num = int(row['Question Number'])
        value = safe_float(row.get('Score'))
        if value is not None and 1 <= q_num <= 26:
            concept_key = f"CPATH_Q{q_num}"
            item_concept = CPATH_ITEM_CONCEPTS.get(concept_key)
            if item_concept:
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': item_concept['concept_id'],
                    'measurement_date': row['measurement_date'],
                    'value_as_number': value,
                    'unit_source_value': 'score',
                    'visit_occurrence_id': row.get('visit_occurrence_id'),
                    'measurement_source_value': f"cogstate_cpath:Q{q_num}:{row.get('Session_ID', 'NA')}",
                })
                cpath_item_count += 1

    # C-PATH Total Score (aggregate by session)
    cpath_totals = cpath_questions.groupby(['BID', 'VISCODE', 'Session_ID']).agg({
        'Score': 'sum',
        'Date_DAYS_CONSENT': 'first'
    }).reset_index()

    cpath_totals_merged = prepare_source_df(cpath_totals, person_df, date_anchor_df, visit_df)
    cpath_totals_merged['measurement_date'] = cpath_totals_merged.apply(
        lambda row: calc_days_to_date(row, 'Date_DAYS_CONSENT') or row['synthetic_consent_date'], axis=1
    )

    cpath_total_count = 0
    for _, row in cpath_totals_merged.iterrows():
        value = safe_float(row.get('Score'))
        if value is not None:
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': COGSTATE_QUESTIONNAIRE_CONCEPTS['CPATH_TOTAL']['concept_id'],
                'measurement_date': row['measurement_date'],
                'value_as_number': value,
                'unit_source_value': 'score',
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': f"cogstate_cpath:Total:{row.get('Session_ID', 'NA')}",
            })
            cpath_total_count += 1

    print(f"  C-PATH measurements: totals={cpath_total_count}, items={cpath_item_count}")

    # ========== Build final DataFrame ==========
    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    if len(measurement_df) > 0:
        measurement_df['measurement_event_id'] = None
        measurement_df['meas_event_field_concept_id'] = None

    print(f"Created CogState questionnaire MEASUREMENT with {len(measurement_df)} records")
    print(f"  MACQ: {macq_total_count} totals + {macq_item_count} items, C-PATH: {cpath_total_count} totals + {cpath_item_count} items")
    return measurement_df
