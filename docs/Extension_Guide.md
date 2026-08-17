# Extension Guide: Adding a New Data Domain

This guide walks through the six steps required to add a new data domain to the A4/LEARN OMOP ETL pipeline. Each step includes the exact file to edit, the pattern to follow, and the pitfalls to avoid.

## Prerequisites

- Python 3.x with pandas
- A source CSV in `Raw Data/`, `Derived Data/`, or `External Data/`
- A list of source codes to map to OMOP concept IDs

## Directory Overview

```
Clinical/
  a4_omop_etl/
    config.py          # Source file manifest
    concepts.py        # Concept CSV loaders
    pipeline.py        # Orchestration and concatenation
    helpers.py         # Shared utilities (date calc, visit linkage)
    measurement_*.py   # One module per measurement domain
    observation_*.py   # One module per observation domain
  concept_maps/        # Concept mapping CSVs
  OMOP_Output/         # Pipeline output
```

---

## Step 1: Register the Source File

**File:** `a4_omop_etl/config.py`

Add a tuple to the `SOURCE_FILES` list. The format is `(variable_name, subdirectory, filename)`.

```python
SOURCE_FILES = [
    ...
    ('new_source', 'Raw Data', 'new_source.csv'),
]
```

The `variable_name` becomes the key you use later to access the DataFrame: `src['new_source']`.

---

## Step 2: Create a Concept Map CSV

**Directory:** `concept_maps/`

Create a CSV that maps source codes to OMOP concept IDs. The standard columns are:

```
source_code,concept_id,concept_name,unit,group,notes
```

The `group` column is optional. Use it when a single CSV holds concepts for multiple sub-domains (see `cogstate.csv` or `cognitive.csv` for examples with group filters like `test`, `composite`, `core`, `extended`).

**Example** (`concept_maps/new_domain.csv`):

```csv
source_code,concept_id,concept_name,unit,notes
SCORE_TOTAL,2100000300,New Domain Total Score,score,Total composite score
SCORE_SUB1,2100000301,New Domain Sub-score 1,score,First sub-scale
```

**Choosing concept IDs:** Custom concepts use the `2100000xxx` range. Check the highest ID already in use across all CSVs in `concept_maps/` and start above that. Run this to find it:

```bash
awk -F',' 'NR>1 && $2+0 > max {max=$2+0} END {print max}' concept_maps/*.csv
```

---

## Step 3: Add a Concept Loader

**File:** `a4_omop_etl/concepts.py`

Add a loader function that calls the private `_load_dict_of_dicts` helper. This returns a dict keyed by `source_code`, where each value contains `concept_id`, `name`, and optionally `unit`.

```python
def load_new_domain_concepts() -> dict:
    return _load_dict_of_dicts('new_domain.csv')
```

If your CSV uses a `group` column to separate sub-domains, pass a filter:

```python
def load_new_domain_concepts() -> dict:
    return _load_dict_of_dicts('new_domain.csv', group_filter='primary')
```

The returned dict looks like this:

```python
{
    'SCORE_TOTAL': {'concept_id': 2100000300, 'name': 'New Domain Total Score', 'unit': 'score'},
    'SCORE_SUB1':  {'concept_id': 2100000301, 'name': 'New Domain Sub-score 1', 'unit': 'score'},
}
```

Note that the key for the concept name is `name`, not `concept_name`. This is set by `_load_dict_of_dicts`.

---

## Step 4: Create the Domain Module

**File:** `a4_omop_etl/measurement_new_domain.py`

Create a new module with a single public function. The function signature must accept four DataFrames and return a single DataFrame of OMOP measurement records.

```python
import pandas as pd
from datetime import timedelta

from . import concepts


def create_measurement_new_domain(
    source_df: pd.DataFrame,
    person_df: pd.DataFrame,
    visit_occurrence_df: pd.DataFrame,
    date_anchor_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create OMOP MEASUREMENT records from new_source.csv."""
    NEW_DOMAIN_CONCEPTS = concepts.load_new_domain_concepts()

    # ---- Lookups ----
    person_lookup = person_df[['person_id', 'person_source_value']].copy()
    visit_lookup = visit_occurrence_df[
        ['visit_occurrence_id', 'person_id', 'visit_source_value']
    ].copy()

    # ---- Filter valid rows ----
    filtered = source_df[source_df['VALUE'].notna()].copy()
    print(f"  New Domain: {len(source_df)} total -> {len(filtered)} valid")

    # ---- Link to person ----
    merged = filtered.merge(
        person_lookup, left_on='BID', right_on='person_source_value', how='inner'
    )
    merged = merged.merge(
        date_anchor_df[['BID', 'synthetic_consent_date']], on='BID', how='left'
    )

    # ---- Link to visit ----
    merged['visit_source_value'] = (
        merged['BID'] + '_' + merged['VISCODE'].astype(str).str.zfill(3)
    )
    merged = merged.merge(
        visit_lookup, on=['person_id', 'visit_source_value'], how='left'
    )

    # ---- Calculate date ----
    # Replace DATE_DAYS_CONSENT with the actual column name in your source file.
    days_col = 'DATE_DAYS_CONSENT'
    merged['measurement_date'] = merged.apply(
        lambda row: row['synthetic_consent_date'] + timedelta(days=int(row[days_col]))
        if pd.notna(row.get(days_col)) else row['synthetic_consent_date'],
        axis=1,
    )

    # ---- Build records ----
    measurements = []
    for _, row in merged.iterrows():
        code = row['TEST_CODE']  # Adjust to match your source column
        info = NEW_DOMAIN_CONCEPTS.get(
            code, {'concept_id': 0, 'name': f'Unknown {code}', 'unit': 'score'}
        )
        measurements.append({
            'person_id': row['person_id'],
            'measurement_concept_id': info['concept_id'],
            'measurement_date': row['measurement_date'],
            'measurement_datetime': None,
            'measurement_time': None,
            'measurement_type_concept_id': 32817,  # EHR
            'operator_concept_id': None,
            'value_as_number': float(row['VALUE']) if pd.notna(row['VALUE']) else None,
            'value_as_concept_id': None,
            'unit_concept_id': 0,
            'unit_source_value': info.get('unit', 'score'),
            'range_low': None,
            'range_high': None,
            'provider_id': None,
            'visit_occurrence_id': row.get('visit_occurrence_id'),
            'visit_detail_id': None,
            'measurement_source_value': f"NEW_DOMAIN:{code}",
            'measurement_source_concept_id': 0,
            'value_source_value': str(row['VALUE']) if pd.notna(row['VALUE']) else None,
        })

    result = pd.DataFrame(measurements) if measurements else pd.DataFrame()
    result['measurement_id'] = range(1, 1 + len(result))

    print(f"  Created New Domain MEASUREMENT with {len(result)} records")
    return result
```

### Adapting the template

Before using this template, check three things in your source CSV:

1. **Value column** -- The template filters on `VALUE`. Your file may use a different column name.
2. **Test code column** -- The template reads `TEST_CODE`. Substitute your column (e.g., `TESTCD`, `PARAMCD`, `LBTESTCD`).
3. **Date column** -- The template uses `DATE_DAYS_CONSENT`. Common alternatives include `TESTDATE_DAYS_CONSENT`, `LBDTM_DAYS_CONSENT`, and `Date_DAYS_CONSENT`.

### Using helpers.py (optional)

The `helpers` module provides shorthand for the merge-and-calculate pattern:

```python
from .helpers import build_person_lookup, link_to_person, link_to_visit, calc_date

person_lookup = build_person_lookup(person_df)
merged = link_to_person(filtered, person_lookup)
merged = link_to_visit(merged, build_visit_lookup(visit_occurrence_df))
merged['measurement_date'] = calc_date(date_anchor_df, merged, 'DATE_DAYS_CONSENT')
```

These helpers are not used by all existing modules, so either approach is acceptable.

---

## Step 5: Wire Into the Pipeline

**File:** `a4_omop_etl/pipeline.py`

Make three changes:

**5a. Import the function.**

```python
from .measurement_new_domain import create_measurement_new_domain
```

**5b. Call it after the existing measurement phases.**

```python
print("\n--- Phase NN: MEASUREMENT Table (New Domain) ---")
measurement_new = create_measurement_new_domain(
    src['new_source'], person, visit_occurrence, date_anchor
)
```

**5c. Add the result to the concatenation.**

```python
measurement = pd.concat([
    measurement_clinical, measurement_cognitive, measurement_biomarkers,
    measurement_imaging, measurement_cogstate, measurement_cogstate_battery,
    measurement_cog_extended, measurement_questionnaires_df,
    measurement_imaging_extended, measurement_cogstate_quest,
    measurement_new,  # <-- add here
], ignore_index=True)
```

The pipeline reassigns `measurement_id` after concatenation, so you do not need to coordinate IDs across modules.

---

## Step 6: Run and Verify

```bash
python -m a4_omop_etl
```

Check the console output for:

- Your phase header (`Phase NN: MEASUREMENT Table (New Domain)`)
- The row counts (`total -> valid`)
- The total measurement count (should increase by the number of records your module produced)
- All five validation checks still passing

---

## Reference

### Required OMOP Measurement Columns

Every DataFrame returned from a measurement module must include all of these columns, even when the value is `None` or `0`. Missing columns cause `pd.concat` errors.

| Column                          | Typical Value             |
|---------------------------------|---------------------------|
| `measurement_id`                | Sequential integer        |
| `person_id`                     | From person lookup        |
| `measurement_concept_id`        | From concept map          |
| `measurement_date`              | Calculated from days-col  |
| `measurement_datetime`          | `None`                    |
| `measurement_time`              | `None`                    |
| `measurement_type_concept_id`   | `32817`                   |
| `operator_concept_id`           | `None`                    |
| `value_as_number`               | Float or `None`           |
| `value_as_concept_id`           | `None`                    |
| `unit_concept_id`               | `0` (mapped in post-proc) |
| `unit_source_value`             | From concept map          |
| `range_low`                     | `None`                    |
| `range_high`                    | `None`                    |
| `provider_id`                   | `None`                    |
| `visit_occurrence_id`           | From visit lookup         |
| `visit_detail_id`               | `None`                    |
| `measurement_source_value`      | `"DOMAIN:code"`           |
| `measurement_source_concept_id` | `0`                       |
| `value_source_value`            | String of raw value       |

### Common Pitfalls

| Problem | Symptom | Fix |
|---------|---------|-----|
| Missing OMOP columns | `pd.concat` raises a warning or produces NaN columns | Include every column from the table above |
| NaN in date math | `TypeError` in `timedelta()` | Guard with `pd.notna()` before casting to `int` |
| VISCODE not zero-padded | Visit linkage returns all nulls | Use `.astype(str).str.zfill(3)` |
| Wrong concept key | `'concept_name'` KeyError | Use `info['name']` -- `_load_dict_of_dicts` maps it to `name` |
| Hardcoded concept IDs | IDs drift out of sync with CSV | Always load from `concept_maps/` via `concepts.py` |
| Empty DataFrame returned | Phase produces 0 records silently | Filter step may be too aggressive; print counts to diagnose |

### Observation Domains

For observation-type data instead of measurements, follow the same six steps with these differences:

- Module file: `a4_omop_etl/observation_new_domain.py`
- Return columns: `observation_id`, `person_id`, `observation_concept_id`, `observation_date`, `observation_datetime`, `observation_type_concept_id` (32817), `value_as_number`, `value_as_string`, `value_as_concept_id`, `qualifier_concept_id`, `unit_concept_id`, `provider_id`, `visit_occurrence_id`, `visit_detail_id`, `observation_source_value`, `observation_source_concept_id`, `unit_source_value`, `qualifier_source_value`
- Concatenation target: the `observation` concat block in `pipeline.py`
