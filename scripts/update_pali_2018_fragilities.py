#!/usr/bin/env python3
"""
One-off data fix for the Pali-2018 fragility models.

Two changes, applied together to the canonical JSON in ``resources/data/``:

1. Every fragility curve median belonging to a Pali-2018 fragility model is
   divided by 100. The source reported story drift ratio as a percentage; the
   database stores the ``Ratio`` EDP unit declared on these models.
2. The four opaque ``fraNNNN`` model ids are renamed to describe the wall
   configuration they model. Because ``FragilityModel.fragility_model_id`` is
   derived as ``<reference_id>|<model_id>``, the rename is also applied to
   every foreign key that points at these models.

Run from anywhere; paths resolve against the repository root.

    python scripts/update_pali_2018_fragilities.py --dry_run
    python scripts/update_pali_2018_fragilities.py

Afterwards, rebuild and validate per the contributor guide in README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / 'resources' / 'data'

REFERENCE_ID = 'Pali-2018'

# Old model_id -> new model_id. Spaces are avoided: no other model_id in the
# dataset contains one, and the value is embedded in the composite
# ``reference|model_id`` key that also travels through the CSV import/export
# commands.
RENAMES: Dict[str, str] = {
    'fra1016': 'type1_fixed',
    'fra1017': 'type1_sliding',
    'fra1018': 'type2_fixed',
    'fra1019': 'type2_sliding',
}

MEDIAN_DIVISOR = Decimal(100)

# FragilityCurve.median is DecimalField(max_digits=9, decimal_places=4).
MEDIAN_DECIMAL_PLACES = 4
MEDIAN_MAX_DIGITS = 9

EXPECTED_MODEL_COUNT = 4
EXPECTED_CURVE_COUNT = 12

MODEL_FILE = 'fragility_model.json'
CURVE_FILE = 'fragility_curve.json'
# Files whose 'fragility_model' field holds a '<reference>|<model_id>' foreign key.
FK_FILES = (
    CURVE_FILE,
    'component_fragility_model_bridge.json',
    'experiment_fragility_model_bridge.json',
)


def fragility_model_id(model_id: str) -> str:
    """Compose the derived id the way FragilityModel.save() does."""
    return f'{REFERENCE_ID}|{model_id}'


OLD_FK = {
    fragility_model_id(old): fragility_model_id(new) for old, new in RENAMES.items()
}


def load(file_name: str) -> Tuple[List[Dict[str, Any]], str]:
    """Read a canonical data file, returning its records and its newline style."""
    path = DATA_DIR / file_name
    with open(path, 'r', encoding='utf-8', newline='') as f:
        raw = f.read()
    # Preserve whatever line ending the file already uses, so the diff shows
    # only the intended content change.
    newline = '\r\n' if '\r\n' in raw else '\n'
    return json.loads(raw), newline


def dump(file_name: str, records: List[Dict[str, Any]], newline: str) -> None:
    """Write a canonical data file in the same format ``export_data`` produces."""
    path = DATA_DIR / file_name
    with open(path, 'w', encoding='utf-8', newline=newline) as f:
        json.dump(records, f, indent=4, sort_keys=True)


def scale_median(value: float) -> float:
    """Divide a median by 100 using decimal arithmetic.

    Float division introduces representation error (0.37 / 100 yields
    0.0037000000000000002), which would survive into the JSON and break the
    lossless JSON -> DB -> JSON round-trip test.
    """
    scaled = Decimal(str(value)) / MEDIAN_DIVISOR
    exponent = -scaled.as_tuple().exponent
    if exponent > MEDIAN_DECIMAL_PLACES:
        raise ValueError(
            f'{value} / 100 = {scaled} needs {exponent} decimal places; '
            f'FragilityCurve.median stores only {MEDIAN_DECIMAL_PLACES}.'
        )
    if len(scaled.as_tuple().digits) > MEDIAN_MAX_DIGITS:
        raise ValueError(
            f'{value} / 100 = {scaled} exceeds max_digits={MEDIAN_MAX_DIGITS}.'
        )
    return float(scaled)


def check_not_already_applied(models: List[Dict[str, Any]]) -> None:
    """Refuse to run twice: a second pass would divide the medians again."""
    present = {m['model_id'] for m in models if m.get('reference') == REFERENCE_ID}
    already = sorted(present & set(RENAMES.values()))
    if already:
        sys.exit(
            f'{REFERENCE_ID} models already carry the new ids ({already}); '
            'nothing to do. Re-running would divide the medians by 100 again.'
        )
    missing = sorted(set(RENAMES) - present)
    if missing:
        sys.exit(
            f'Expected {REFERENCE_ID} model_id(s) not found in {MODEL_FILE}: {missing}'
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Report what would change without writing any files.',
    )
    args = parser.parse_args()

    models, model_newline = load(MODEL_FILE)
    check_not_already_applied(models)

    targets = [m for m in models if m.get('reference') == REFERENCE_ID]
    if len(targets) != EXPECTED_MODEL_COUNT:
        sys.exit(
            f'Expected {EXPECTED_MODEL_COUNT} {REFERENCE_ID} fragility models, '
            f'found {len(targets)}. Aborting rather than guessing.'
        )

    curves, curve_newline = load(CURVE_FILE)
    matching_curves = [c for c in curves if c.get('fragility_model') in OLD_FK]
    if len(matching_curves) != EXPECTED_CURVE_COUNT:
        sys.exit(
            f'Expected {EXPECTED_CURVE_COUNT} {REFERENCE_ID} fragility curves, '
            f'found {len(matching_curves)}. Aborting rather than guessing.'
        )

    # 1. Scale the medians. Done before the rename so the lookup keys still match.
    print(f'Dividing {len(matching_curves)} {REFERENCE_ID} curve medians by 100:')
    for curve in matching_curves:
        median = curve.get('median')
        if median is None:
            sys.exit(
                f'Curve {curve["fragility_model"]} ds_rank={curve.get("ds_rank")} '
                'has a null median; expected a value.'
            )
        curve['median'] = scale_median(median)
        print(
            f'  {curve["fragility_model"]:<24} ds_rank={curve.get("ds_rank")}  '
            f'{median} -> {curve["median"]}'
        )

    # 2. Rename the model ids.
    print('\nRenaming model_id:')
    for model in targets:
        old = model['model_id']
        model['model_id'] = RENAMES[old]
        print(f'  {old} -> {model["model_id"]}  ({model.get("comp_detail")})')

    # 3. Repoint every foreign key at the new derived fragility_model_id.
    print('\nUpdating fragility_model foreign keys:')
    updated: Dict[str, List[Dict[str, Any]]] = {MODEL_FILE: models}
    newlines: Dict[str, str] = {MODEL_FILE: model_newline}
    loaded: Dict[str, Tuple[List[Dict[str, Any]], str]] = {
        CURVE_FILE: (curves, curve_newline)
    }
    for file_name in FK_FILES:
        records, newline = loaded.get(file_name) or load(file_name)
        count = 0
        for record in records:
            new_fk = OLD_FK.get(record.get('fragility_model'))
            if new_fk is not None:
                record['fragility_model'] = new_fk
                count += 1
        updated[file_name] = records
        newlines[file_name] = newline
        print(f'  {file_name}: {count} record(s)')

    if args.dry_run:
        print('\n--dry_run: no files written.')
        return 0

    print()
    for file_name, records in updated.items():
        dump(file_name, records, newlines[file_name])
        print(f'Wrote {(DATA_DIR / file_name).relative_to(REPO_ROOT)}')

    print(
        '\nNext:'
        '\n  python manage.py ingest'
        '\n  python manage.py dumpdata ned_app --indent 2 -o ned_app/fixtures/initial_data.json'
        '\n  python manage.py test ned_app.tests'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
