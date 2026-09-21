#!/usr/bin/env python3
"""Regenerate custom_vocabulary/CONCEPT.csv from the concept maps.

The concept maps in concept_maps/ are the source of truth for custom
(A4_LEARN) concepts: this script scans them for concept_ids in the custom
range, takes each concept's name from the map, and rewrites the vocabulary
file so the two can never drift apart.

Rules:
- Custom range is [2000000000, 2128000000). The 2128xxxxxx block is the
  DICOM2OMOP vocabulary, loaded separately from omop_table_staging_v5.csv,
  and is never written here.
- A concept_id used with two different names across maps is an error
  (that is how the WALKING/C-PATH collision happened).
- Concepts referenced only in a4_omop_etl/*.py code literals (e.g. the
  treatment-arm concepts) keep their existing vocabulary rows.
- domain_id / concept_class_id / concept_code are preserved from the
  existing vocabulary where the id is already registered; new ids get a
  domain inferred from their source map and a generated concept_code.

Run from the repo root:  python3 generate_custom_vocabulary.py
"""
import csv
import re
import sys
from pathlib import Path

BASE = Path(__file__).parent
MAP_DIR = BASE / 'concept_maps'
VOCAB_PATH = BASE / 'custom_vocabulary' / 'CONCEPT.csv'
ETL_DIR = BASE / 'a4_omop_etl'

CUSTOM_LO, CUSTOM_HI = 2_000_000_000, 2_128_000_000

# Default OMOP domain per map file for ids not already in the vocabulary.
MAP_DOMAINS = {
    'drugs.csv': 'Drug',
    'milestones.csv': 'Observation',
    'observations.csv': 'Observation',
    'questionnaires.csv': 'Observation',
    'cssrs.csv': 'Observation',
    'adqs.csv': 'Observation',
    'conditions.csv': 'Measurement',   # customs here are scores (PXEDSEV)
    'image_findings.csv': 'Measurement',
    'image_feature_types.csv': 'Metadata',
    'dicom_value_maps.csv': 'Meas Value',
}
DEFAULT_DOMAIN = 'Measurement'


def scan_maps():
    """(concept_id -> name), with the source files, from all concept maps."""
    found = {}
    for path in sorted(MAP_DIR.glob('*.csv')):
        with open(path, newline='') as f:
            # Skip leading comment lines (adqs.csv starts with one); otherwise
            # DictReader takes the comment as the header and scans nothing.
            lines = [l for l in f if not l.lstrip().startswith('#')]
            reader = csv.DictReader(lines)
            id_cols = [c for c in (reader.fieldnames or []) if c and 'concept_id' in c]
            name_col = next((c for c in (reader.fieldnames or [])
                             if c and 'concept_name' in c), None)
            for row in reader:
                for col in id_cols:
                    raw = (row.get(col) or '').strip()
                    if not re.fullmatch(r'2\d{9}', raw):
                        continue
                    cid = int(raw)
                    if not (CUSTOM_LO <= cid < CUSTOM_HI):
                        continue
                    # Name applies to the row's main concept only; value/qualifier
                    # id columns without their own name column keep the vocab name.
                    name = (row.get(name_col) or '').strip() if col == 'concept_id' and name_col else ''
                    found.setdefault(cid, []).append((path.name, name))
    return found


def scan_code_ids():
    """Custom concept_ids that appear as literals in the ETL code."""
    ids = set()
    for path in ETL_DIR.glob('*.py'):
        for m in re.finditer(r'\b(2\d{9})\b', path.read_text()):
            cid = int(m.group(1))
            if CUSTOM_LO <= cid < CUSTOM_HI:
                ids.add(cid)
    return ids


def main():
    existing = {}
    with open(VOCAB_PATH, newline='') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        for row in reader:
            existing[int(row['concept_id'])] = row

    found = scan_maps()
    code_ids = scan_code_ids()

    # Collision check: one id, more than one distinct non-empty name.
    errors = []
    resolved = {}
    for cid, refs in found.items():
        names = sorted({n for _, n in refs if n})
        if len(names) > 1:
            errors.append(f"  {cid}: {names} (in {sorted({f for f, _ in refs})})")
        elif names:
            resolved[cid] = names[0]
    if errors:
        print("ERROR: concept_id used with conflicting names:")
        print("\n".join(errors))
        sys.exit(1)

    out = {}
    for cid in sorted(set(found) | (code_ids & set(existing))):
        old = existing.get(cid)
        name = resolved.get(cid) or (old['concept_name'] if old else '')
        if not name:
            print(f"WARNING: {cid} has no name in maps or vocabulary; skipped")
            continue
        src_file = sorted({f for f, _ in found.get(cid, [])})
        domain = old['domain_id'] if old else MAP_DOMAINS.get(src_file[0] if src_file else '', DEFAULT_DOMAIN)
        out[cid] = {
            'concept_id': str(cid),
            'concept_name': name,
            'domain_id': domain,
            'vocabulary_id': old['vocabulary_id'] if old else 'A4_LEARN',
            'concept_class_id': old['concept_class_id'] if old else 'Clinical Observation',
            'standard_concept': old['standard_concept'] if old else 'S',
            'concept_code': old['concept_code'] if old else f'A4_{cid}',
            'valid_start_date': old['valid_start_date'] if old else '2020-01-01',
            'valid_end_date': old['valid_end_date'] if old else '2099-12-31',
            'invalid_reason': old['invalid_reason'] if old else '',
        }

    added = sorted(set(out) - set(existing))
    removed = sorted(set(existing) - set(out))
    renamed = sorted(cid for cid in set(out) & set(existing)
                     if out[cid]['concept_name'] != existing[cid]['concept_name'])

    with open(VOCAB_PATH, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for cid in sorted(out):
            writer.writerow(out[cid])

    print(f"Wrote {len(out)} concepts to {VOCAB_PATH}")
    print(f"  added:   {len(added)}" + (f"  {added[:8]}" if added else ""))
    print(f"  removed: {len(removed)}" + (f"  {removed[:8]}" if removed else ""))
    print(f"  renamed: {len(renamed)}" + (f"  {renamed[:8]}" if renamed else ""))


if __name__ == '__main__':
    main()
