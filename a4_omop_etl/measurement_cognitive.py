import pandas as pd

from . import concepts
from .helpers import prepare_source_df, calc_days_to_date, finalize_measurement_df, safe_float, concat_and_assign_ids


def create_measurement_pacc(
    pacc_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from PACC.csv.

    Source: pacc.csv | Date: visit_start_date

    Field Mappings (concept_maps/cognitive.csv, group=core):
        PACC.raw    -> PACC Raw Composite Score (2100000001)
        FCTOTAL96   -> FCSRT-96 Total (2100000004)
        LDELTOTAL   -> Logical Memory Delayed (2100000005)
        DIGITTOTAL  -> Digit Symbol Total (2100000006)
        MMSCORE     -> MMSE Total Score (42869860)
    """
    COGNITIVE_CONCEPTS = concepts.load_cognitive_concepts()

    pacc_filtered = pacc_df.copy()
    print(f"  PACC: {len(pacc_filtered)} records")

    pacc_filtered = prepare_source_df(pacc_filtered, person_df, date_anchor_df,
                                       visit_occurrence_df, visit_extra_cols=['visit_start_date'])

    # Core scores (MMSCORE excluded — emitted by MMSE processing)
    # PACC.raw is the raw composite; PACC (change-from-baseline) is derived and skipped
    core_cols = ['PACC.raw', 'FCTOTAL96', 'LDELTOTAL', 'DIGITTOTAL']

    measurements = []
    core_count = 0

    for _, row in pacc_filtered.iterrows():
        meas_date = row.get('visit_start_date')

        # Core component scores
        for col in core_cols:
            if pd.notna(row.get(col)):
                concept = COGNITIVE_CONCEPTS.get(col, {})
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': concept.get('concept_id', 0),
                    'measurement_date': meas_date,
                    'value_as_number': float(row[col]),
                    'unit_source_value': concept.get('unit', ''),
                    'visit_occurrence_id': row.get('visit_occurrence_id'),
                    'measurement_source_value': f'PACC:{col}',
                })
                core_count += 1

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"  Created {len(measurement_df)} PACC measurements (core: {core_count})")
    return measurement_df


def create_measurement_mmse(
    mmse_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from mmse.csv.

    Source: mmse.csv | Filter: DONE='Yes' | Date: visit_start_date

    Field Mappings (concept_maps/cognitive.csv):
        MMSCORE           -> MMSE Total Score (42869860)
        26 item fields    -> mmse_item group (37xxxxxx CDISC codes)
        5 DLROW letters   -> mmse_letter group (text values)
    """
    COGNITIVE_CONCEPTS = concepts.load_cognitive_concepts()
    MMSE_ITEM_CONCEPTS = concepts.load_cognitive_mmse_items()
    MMSE_LETTER_CONCEPTS = concepts.load_cognitive_mmse_letters()

    # Filter to completed assessments
    mmse_filtered = mmse_df[mmse_df['DONE'] == 'Yes'].copy()
    print(f"  MMSE: {len(mmse_df)} total -> {len(mmse_filtered)} (DONE='Yes')")

    mmse_filtered = prepare_source_df(mmse_filtered, person_df, date_anchor_df,
                                       visit_occurrence_df, visit_extra_cols=['visit_start_date'])

    # Individual MMSE item fields to extract
    mmse_item_fields = list(MMSE_ITEM_CONCEPTS.keys())
    # WORLD backwards letter position fields (text values)
    mmse_letter_fields = list(MMSE_LETTER_CONCEPTS.keys())

    measurements = []
    total_count = 0
    item_count = 0
    letter_count = 0

    for _, row in mmse_filtered.iterrows():
        meas_date = row.get('visit_start_date')

        # MMSCORE total
        if pd.notna(row.get('MMSCORE')):
            concept = COGNITIVE_CONCEPTS['MMSCORE']
            measurements.append({
                'person_id': row['person_id'],
                'measurement_concept_id': concept['concept_id'],
                'measurement_date': meas_date,
                'value_as_number': float(row['MMSCORE']),
                'unit_source_value': 'score',
                'visit_occurrence_id': row.get('visit_occurrence_id'),
                'measurement_source_value': 'MMSE:MMSCORE',
            })
            total_count += 1

        # Individual MMSE items
        for field in mmse_item_fields:
            val = row.get(field)
            if val is not None and pd.notna(val):
                # Convert Correct/Incorrect to 1/0
                if isinstance(val, str):
                    if val == 'Correct':
                        numeric_val = 1.0
                    elif val == 'Incorrect':
                        numeric_val = 0.0
                    else:
                        numeric_val = safe_float(val)
                        if numeric_val is None:
                            continue
                else:
                    numeric_val = safe_float(val)
                    if numeric_val is None:
                        continue
                concept = MMSE_ITEM_CONCEPTS[field]
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': concept['concept_id'],
                    'measurement_date': meas_date,
                    'value_as_number': numeric_val,
                    'unit_source_value': 'score',
                    'visit_occurrence_id': row.get('visit_occurrence_id'),
                    'measurement_source_value': f'MMSE:{field}',
                    'value_source_value': str(val),
                })
                item_count += 1

        # WORLD backwards letter positions (text values, not numeric)
        for field in mmse_letter_fields:
            val = row.get(field)
            if val is not None and pd.notna(val):
                letter_text = str(val).strip()
                if letter_text:
                    concept = MMSE_LETTER_CONCEPTS[field]
                    measurements.append({
                        'person_id': row['person_id'],
                        'measurement_concept_id': concept['concept_id'],
                        'measurement_date': meas_date,
                        'value_as_number': None,
                        'unit_source_value': None,
                        'visit_occurrence_id': row.get('visit_occurrence_id'),
                        'measurement_source_value': f'MMSE:{field}',
                        'value_source_value': letter_text,
                    })
                    letter_count += 1

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"  Created {len(measurement_df)} MMSE measurements (totals: {total_count}, items: {item_count}, letters: {letter_count})")
    return measurement_df


def create_measurement_cdr(
    cdr_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from cdr.csv.

    Source: cdr.csv | Filter: DONE='Yes' | Date: visit_start_date

    Field Mappings (concept_maps/cognitive.csv):
        CDGLOBAL -> CDR Global Score (37546494)
        CDSOB    -> CDR Sum of Boxes (37524289)
        7 domain fields (MEMORY, ORIENT, JUDGE, COMMUN, HOME, CARE, CDRSB)
                 -> cdr_domain group
    """
    COGNITIVE_CONCEPTS = concepts.load_cognitive_concepts()
    CDR_DOMAIN_CONCEPTS = concepts.load_cognitive_cdr_domains()

    # Filter to completed assessments
    cdr_filtered = cdr_df[cdr_df['DONE'] == 'Yes'].copy()
    print(f"  CDR: {len(cdr_df)} total -> {len(cdr_filtered)} (DONE='Yes')")

    cdr_filtered = prepare_source_df(cdr_filtered, person_df, date_anchor_df, visit_occurrence_df)
    cdr_filtered['measurement_date'] = cdr_filtered.apply(
        calc_days_to_date, args=('CDADTC_DAYS_CONSENT',), axis=1
    )

    # Core scores + domain scores
    core_cols = ['CDGLOBAL', 'CDSOB']
    domain_cols = list(CDR_DOMAIN_CONCEPTS.keys())

    measurements = []
    core_count = 0
    domain_count = 0

    for _, row in cdr_filtered.iterrows():
        meas_date = row.get('measurement_date')

        # Build metadata suffix for source_value context
        metadata_parts = []
        if pd.notna(row.get('CDSPVERS')):
            metadata_parts.append(f"v{row['CDSPVERS']}")
        if pd.notna(row.get('BPID')):
            metadata_parts.append(f"SP={row['BPID']}")
        if pd.notna(row.get('CDPTSRCE')):
            metadata_parts.append(f"pt={row['CDPTSRCE']}")
        metadata_suffix = '|' + '|'.join(metadata_parts) if metadata_parts else ''

        # Core scores (CDGLOBAL, CDSOB)
        for col in core_cols:
            if pd.notna(row.get(col)):
                concept = COGNITIVE_CONCEPTS.get(col, {})
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': concept.get('concept_id', 0),
                    'measurement_date': meas_date,
                    'value_as_number': float(row[col]),
                    'unit_source_value': concept.get('unit', 'score'),
                    'visit_occurrence_id': row.get('visit_occurrence_id'),
                    'measurement_source_value': f'CDR:{col}{metadata_suffix}',
                })
                core_count += 1

        # Domain scores (MEMORY, ORIENT, JUDGE, COMMUN, HOME, CARE, CDRSB)
        for col in domain_cols:
            val = row.get(col)
            if val is not None and pd.notna(val):
                concept = CDR_DOMAIN_CONCEPTS[col]
                measurements.append({
                    'person_id': row['person_id'],
                    'measurement_concept_id': concept['concept_id'],
                    'measurement_date': meas_date,
                    'value_as_number': float(val),
                    'unit_source_value': concept.get('unit', 'score'),
                    'visit_occurrence_id': row.get('visit_occurrence_id'),
                    'measurement_source_value': f'CDR:{col}{metadata_suffix}',
                })
                domain_count += 1

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"  Created {len(measurement_df)} CDR measurements (core: {core_count}, domains: {domain_count})")
    return measurement_df


def create_measurement_cognitive(
    pacc_df: pd.DataFrame,
    mmse_df: pd.DataFrame,
    cdr_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create combined OMOP MEASUREMENT table from cognitive assessment sources.

    Combines PACC, MMSE, and CDR into cognitive measurements.
    """
    # Create each measurement type
    pacc_meas = create_measurement_pacc(
        pacc_df, person_df, visit_occurrence_df, date_anchor_df
    )

    mmse_meas = create_measurement_mmse(
        mmse_df, person_df, visit_occurrence_df, date_anchor_df
    )

    cdr_meas = create_measurement_cdr(
        cdr_df, person_df, visit_occurrence_df, date_anchor_df
    )

    # Combine all cognitive measurements
    cognitive_meas = concat_and_assign_ids([pacc_meas, mmse_meas, cdr_meas], 'measurement_id')

    print(f"Created cognitive MEASUREMENT with {len(cognitive_meas)} total records")
    print(f"  - PACC: {len(pacc_meas)}, MMSE: {len(mmse_meas)}, CDR: {len(cdr_meas)}")

    return cognitive_meas


def create_measurement_cognitive_extended(
    cfi_df: pd.DataFrame,
    cfisp_df: pd.DataFrame,
    cogdigit_df: pd.DataFrame,
    cogfcsr_df: pd.DataFrame,
    coglogic_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Create OMOP MEASUREMENT records from extended cognitive test files.

    Sources & Field Mappings (concept_maps/cognitive.csv, group=extended):
        cfi.csv      -> CFIPTTOTAL  (2100000050, CFI Patient Total)
        cfisp.csv    -> CFSPTTOTAL  (2100000051, CFI Study Partner Total)
        cogdigit.csv -> DIGITTOTAL  (2100000052, Digit Symbol)
        cogfcsr.csv  -> FCTOTAL96   (2100000053), FCTOTF (2100000056), FCTOTC (2100000057)
        coglogic.csv -> LIMMTOTAL   (2100000054), LDELTOTAL (2100000055)
    """
    COGNITIVE_EXTENDED = concepts.load_cognitive_extended()

    measurements = []

    def process_cognitive_file(df, score_fields, file_name, done_filter='Yes'):
        """Process a cognitive test file and extract measurements."""
        nonlocal measurements

        # Filter for completed records
        if 'DONE' in df.columns:
            filtered = df[df['DONE'] == done_filter].copy()
        else:
            filtered = df.copy()
        print(f"  {file_name}: {len(df)} total -> {len(filtered)} valid")

        merged = prepare_source_df(filtered, person_df, date_anchor_df, visit_occurrence_df,
                                    visit_extra_cols=['visit_start_date'])

        count = 0
        for _, row in merged.iterrows():
            for field in score_fields:
                if field in row and pd.notna(row[field]):
                    concept = COGNITIVE_EXTENDED.get(field, {'concept_id': 0, 'name': field, 'unit': 'score'})
                    # Use visit_start_date when available, fall back to synthetic_consent_date
                    meas_date = row.get('visit_start_date') if pd.notna(row.get('visit_start_date')) else row['synthetic_consent_date']
                    measurements.append({
                        'person_id': row['person_id'],
                        'measurement_concept_id': concept['concept_id'],
                        'measurement_date': meas_date,
                        'value_as_number': float(row[field]),
                        'unit_source_value': concept['unit'],
                        'visit_occurrence_id': row.get('visit_occurrence_id'),
                        'measurement_source_value': f"{file_name}:{field}",
                    })
                    count += 1
        return count

    # Process each file
    cfi_count = process_cognitive_file(cfi_df, ['CFIPTTOTAL'], 'CFI')
    cfisp_count = process_cognitive_file(cfisp_df, ['CFSPTTOTAL'], 'CFISP')
    digit_count = process_cognitive_file(cogdigit_df, ['DIGITTOTAL'], 'COGDIGIT')
    fcsr_count = process_cognitive_file(cogfcsr_df, ['FCTOTAL96', 'FCTOTF', 'FCTOTC'], 'COGFCSR')
    logic_count = process_cognitive_file(coglogic_df, ['LIMMTOTAL', 'LDELTOTAL'], 'COGLOGIC')

    measurement_df = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    measurement_df = finalize_measurement_df(measurement_df)

    print(f"Created extended cognitive MEASUREMENT with {len(measurement_df)} records")
    print(f"  CFI: {cfi_count}, CFISP: {cfisp_count}, Digit: {digit_count}, FCSR: {fcsr_count}, Logic: {logic_count}")
    return measurement_df
