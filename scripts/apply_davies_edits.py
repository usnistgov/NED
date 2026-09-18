#!/usr/bin/env python3
"""
One-off edits to the canonical JSON data in ``resources/data/``.

Per the Contributors Guide, systematic edits that touch many records are made
with a committed script rather than by hand, so a reviewer can see the logic
behind the JSON diff. Commit this script together with the data change, then
remove it in a follow-up commit once the change is merged.

Every edit runs against one shared, in-memory copy of the data files; nothing
is written until all of them succeed, so a failed validation leaves the working
tree untouched. The edits are **not** idempotent: they are meant to run exactly
once against the canonical data as of the commit this script ships in.

Usage::

    python scripts/apply_data_edits.py --dry-run
    python scripts/apply_data_edits.py

After running, rebuild the database and regenerate the fixture snapshot as
described in the Contributors Guide, then run the tests::

    rm -f db.sqlite3            # required: see below
    python manage.py migrate
    python manage.py ingest
    python manage.py dumpdata ned_app --indent 2 \
        --output ned_app/fixtures/initial_data.json
    python manage.py test ned_app.tests

Delete ``db.sqlite3`` first. ``ingest`` upserts on each record's natural key
and never deletes, so renaming an id leaves the row under the *old* id behind;
ingesting this change over an existing database yields 531 fragility models
instead of 523, and ``dumpdata`` would bake those orphans into the fixture.
"""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / 'resources' / 'data'

FRAGILITY_MODEL_FILE = 'fragility_model.json'
FRAGILITY_CURVE_FILE = 'fragility_curve.json'

# Files whose records point at a fragility model through the composite natural
# key "<reference_id>|<model_id>", stored in their 'fragility_model' field.
MODEL_REFERRING_FILES = (
    FRAGILITY_CURVE_FILE,
    'component_fragility_model_bridge.json',
    'experiment_fragility_model_bridge.json',
)

# FragilityCurve.median is a DecimalField(max_digits=9, decimal_places=4) and
# beta a DecimalField(max_digits=4, decimal_places=3); edited values must still
# fit those columns without losing precision.
MEDIAN_DECIMAL_PLACES = Decimal('0.0001')
BETA_DECIMAL_PLACES = Decimal('0.001')


class DataStore:
    """
    Lazily-loaded, write-once view of the canonical JSON data files.

    Edits mutate the loaded structures in place and mark the file dirty via
    :meth:`edit`; :meth:`save` then writes only the files that actually
    changed, once every edit has run.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._loaded: dict[str, Any] = {}
        self._dirty: set[str] = set()

    def read(self, name: str) -> list[dict[str, Any]]:
        """Return the records of a data file, loading it on first access."""
        if name not in self._loaded:
            with open(self.data_dir / name, encoding='utf-8') as f:
                self._loaded[name] = json.load(f)
        return self._loaded[name]

    def edit(self, name: str) -> list[dict[str, Any]]:
        """Return the records of a data file and mark it for writing."""
        records = self.read(name)
        self._dirty.add(name)
        return records

    def save(self) -> list[str]:
        """
        Write the files whose contents actually changed and return their names.

        Mirrors the formatting of the ``export_data`` management command
        (4-space indent, sorted keys, no trailing newline) so the diff is
        limited to the values the edits actually changed. A file an edit
        touched but left unchanged is skipped rather than rewritten, so it
        never shows up as a no-op diff.
        """
        written = []
        for name in sorted(self._dirty):
            path = self.data_dir / name
            serialized = json.dumps(self._loaded[name], indent=4, sort_keys=True)
            with open(path, encoding='utf-8') as f:
                if f.read() == serialized:
                    continue
            with open(path, 'w', encoding='utf-8') as f:
                f.write(serialized)
            written.append(name)
        return written


def split_composite_key(key: str) -> tuple[str, str]:
    """
    Split a composite "<reference_id>|<model_id>" key into its two parts.

    A reference_id never contains a pipe, so the first one separates them.
    """
    reference_id, _, model_id = str(key).partition('|')
    return reference_id, model_id


def rescale_median(median: float | int, divisor: int) -> float:
    """
    Divide a median by ``divisor`` using exact decimal arithmetic.

    Raises:
        ValueError: If the result does not fit the four decimal places the
            ``median`` column stores, which would silently truncate the value.
    """
    exact = Decimal(str(median)) / Decimal(divisor)
    quantized = exact.quantize(MEDIAN_DECIMAL_PLACES)
    if quantized != exact:
        raise ValueError(
            f'{median} / {divisor} = {exact} does not fit '
            f'{MEDIAN_DECIMAL_PLACES} precision'
        )
    return float(quantized)


def models_for_reference(store: DataStore, reference_id: str) -> set[str]:
    """Return the ``model_id`` values recorded under a given reference."""
    return {
        m['model_id']
        for m in store.read(FRAGILITY_MODEL_FILE)
        if m.get('reference') == reference_id
    }


def divide_davies_2011_medians_by_100(store: DataStore) -> None:
    """
    Convert the Davies-2011 fragility medians from percent to ratio.

    The eight Davies-2011 models all report an ``edp_metric`` of
    "Story Drift Ratio" with ``edp_unit`` "Ratio", but their curve medians were
    recorded as percentages (e.g. 0.26 for a 0.26% story drift ratio). Dividing
    every median by 100 puts them in the units the models declare. Dispersions
    (``beta``) are unitless and are left untouched.
    """
    reference_id = 'Davies-2011'
    expected_models = 8
    divisor = 100

    model_ids = models_for_reference(store, reference_id)
    if len(model_ids) != expected_models:
        raise ValueError(
            f'Expected {expected_models} {reference_id} models, '
            f'found {len(model_ids)}: {sorted(model_ids)}'
        )

    changed = 0
    for curve in store.edit(FRAGILITY_CURVE_FILE):
        curve_reference, curve_model = split_composite_key(curve['fragility_model'])
        if curve_reference != reference_id or curve_model not in model_ids:
            continue
        median = curve['median']
        if median is None:
            print(
                f'  {curve["fragility_model"]} ds_rank={curve["ds_rank"]}: '
                f'median is null, skipped'
            )
            continue
        rescaled = rescale_median(median, divisor)
        print(
            f'  {curve["fragility_model"]} ds_rank={curve["ds_rank"]}: '
            f'{median} -> {rescaled}'
        )
        curve['median'] = rescaled
        changed += 1

    print(f'  {changed} curve median(s) across {len(model_ids)} model(s)')


def rename_davies_2011_model_ids(store: DataStore) -> None:
    """
    Give the Davies-2011 models short ids matching the source's own labels.

    A model_id only has to be unique within its reference, and is the second
    half of the auto-generated fragility_model_id, "<reference_id>|<model_id>".
    That composite key is how fragility_curve.json and the two bridge files
    point at a model, so every stored occurrence is rewritten here to keep
    those foreign keys resolvable at ingest.
    """
    reference_id = 'Davies-2011'
    renames = {
        'fra1020': '1a',
        'fra1021': '1b',
        'fra1022': '1c',
        'fra1023': '2a',
        'fra1024': '2b',
        'fra1025': '2c',
        'fra1026': '3',
        'fra1027': '4',
    }

    model_ids = models_for_reference(store, reference_id)
    missing = sorted(set(renames) - model_ids)
    if missing:
        raise ValueError(f'No {reference_id} model with model_id {missing}')

    # model_id is unique per reference and fragility_model_id globally, so the
    # new ids must not collide with any id the reference keeps.
    kept = model_ids - set(renames)
    collisions = sorted(kept & set(renames.values()))
    if collisions:
        raise ValueError(
            f'{reference_id} already uses model_id {collisions}; '
            f'renaming would break uniqueness'
        )

    for model in store.edit(FRAGILITY_MODEL_FILE):
        if model.get('reference') != reference_id:
            continue
        new_id = renames.get(model['model_id'])
        if new_id is None:
            continue
        print(f'  {FRAGILITY_MODEL_FILE}: model_id {model["model_id"]} -> {new_id}')
        model['model_id'] = new_id

    for name in MODEL_REFERRING_FILES:
        updated = 0
        for record in store.edit(name):
            record_reference, record_model = split_composite_key(
                record['fragility_model']
            )
            if record_reference != reference_id:
                continue
            new_id = renames.get(record_model)
            if new_id is None:
                continue
            record['fragility_model'] = f'{reference_id}|{new_id}'
            updated += 1
        print(f'  {name}: {updated} reference(s) repointed')


def correct_curve_field(
    store: DataStore,
    reference_id: str,
    field: str,
    quantum: Decimal,
    corrections: dict[tuple[str, int], tuple[float, float]],
) -> None:
    """
    Apply per-curve corrections to one field, keyed by (model_id, ds_rank).

    Every correction records the value it expects to find alongside the value
    to write. A mismatch aborts rather than overwriting a record whose value is
    not the one the correction was derived from, which also pins these edits
    after the rescale and rename above: they are keyed by the model ids and
    values those produce.

    Args:
        field: The curve field to correct, e.g. 'median' or 'beta'.
        quantum: Smallest unit the column stores, so a corrected value that
            would be truncated on ingest is rejected here instead.

    Raises:
        ValueError: If a target is missing, ambiguous, holds an unexpected
            current value, or the corrected value exceeds the column's scale.
    """
    seen: set[tuple[str, int]] = set()
    for curve in store.edit(FRAGILITY_CURVE_FILE):
        curve_reference, curve_model = split_composite_key(curve['fragility_model'])
        if curve_reference != reference_id:
            continue
        target = (curve_model, curve['ds_rank'])
        correction = corrections.get(target)
        if correction is None:
            continue
        if target in seen:
            raise ValueError(
                f'{reference_id} model {curve_model} has more than one '
                f'ds_rank {curve["ds_rank"]} curve; cannot target a correction'
            )
        seen.add(target)

        expected, corrected = correction
        current = curve[field]
        if Decimal(str(current)) != Decimal(str(expected)):
            raise ValueError(
                f'{reference_id} model {curve_model} ds_rank '
                f'{curve["ds_rank"]}: expected {field} {expected}, found '
                f'{current}; correction not applied'
            )
        if Decimal(str(corrected)).quantize(quantum) != Decimal(str(corrected)):
            raise ValueError(
                f'{reference_id} model {curve_model} ds_rank '
                f'{curve["ds_rank"]}: {field} {corrected} does not fit '
                f'{quantum} precision'
            )
        print(
            f'  model {curve_model} ds_rank {curve["ds_rank"]}: '
            f'{field} {current} -> {corrected}'
        )
        curve[field] = corrected

    missing = sorted(set(corrections) - seen)
    if missing:
        raise ValueError(f'No {reference_id} curve found for {missing}')


def correct_davies_2011_medians(store: DataStore) -> None:
    """Apply reviewer corrections to individual Davies-2011 curve medians."""
    correct_curve_field(
        store,
        'Davies-2011',
        'median',
        MEDIAN_DECIMAL_PLACES,
        # (model_id, ds_rank): (expected current median, corrected median)
        {
            ('1c', 3): (0.0099, 0.0096),
            ('2b', 3): (0.0093, 0.0088),
            ('2c', 1): (0.0039, 0.0042),
            ('4', 1): (0.0036, 0.0034),
        },
    )


def correct_davies_2011_betas(store: DataStore) -> None:
    """Apply reviewer corrections to individual Davies-2011 curve dispersions."""
    correct_curve_field(
        store,
        'Davies-2011',
        'beta',
        BETA_DECIMAL_PLACES,
        # (model_id, ds_rank): (expected current beta, corrected beta)
        {
            ('1a', 2): (0.33, 0.35),
            ('1c', 3): (0.55, 0.61),
            ('2a', 1): (0.62, 0.55),
            ('2b', 2): (0.46, 0.43),
            ('2b', 3): (0.36, 0.33),
            ('2c', 1): (0.38, 0.31),
            ('2c', 2): (0.43, 0.40),
            ('4', 1): (0.80, 0.77),
        },
    )


def move_davies_2011_2a_ds3_to_2c(store: DataStore) -> None:
    """
    Reassign the Davies-2011 model 2a damage state 3 curve to model 2c.

    Model 2a is left with damage states 1-2 and model 2c gains a third, with a
    corrected median and dispersion. The curve keeps its ds_rank, description
    and provenance fields; only its owning model and the two fitted values
    change. Runs last, so it is keyed by the ids and values the edits above
    produce.

    ``ingest`` matches a curve on (fragility_model, ds_rank), so the move is
    only safe while the target model has no curve at that rank; ingesting a
    duplicated pair would silently upsert one curve onto the other.
    """
    reference_id = 'Davies-2011'
    source_model = '2a'
    target_model = '2c'
    ds_rank = 3
    expected = {'median': 0.0088, 'beta': 0.33}
    # median is a story drift ratio, i.e. 0.98% drift, matching the units the
    # rescale above put the rest of the reference's curves in.
    corrected = {'median': 0.0098, 'beta': 0.52}
    quanta = {'median': MEDIAN_DECIMAL_PLACES, 'beta': BETA_DECIMAL_PLACES}

    def ranks_of(curves: list[dict[str, Any]], model_id: str) -> list[int]:
        return sorted(
            c['ds_rank']
            for c in curves
            if split_composite_key(c['fragility_model']) == (reference_id, model_id)
        )

    curves = store.edit(FRAGILITY_CURVE_FILE)
    matches = [
        c
        for c in curves
        if split_composite_key(c['fragility_model']) == (reference_id, source_model)
        and c['ds_rank'] == ds_rank
    ]
    if len(matches) != 1:
        raise ValueError(
            f'Expected exactly one {reference_id} model {source_model} '
            f'ds_rank {ds_rank} curve, found {len(matches)}'
        )
    if ds_rank in ranks_of(curves, target_model):
        raise ValueError(
            f'{reference_id} model {target_model} already has a ds_rank '
            f'{ds_rank} curve; moving would collide on ingest'
        )

    curve = matches[0]
    for field, expected_value in expected.items():
        current = curve[field]
        if Decimal(str(current)) != Decimal(str(expected_value)):
            raise ValueError(
                f'{reference_id} model {source_model} ds_rank {ds_rank}: '
                f'expected {field} {expected_value}, found {current}; '
                f'move not applied'
            )
    for field, corrected_value in corrected.items():
        quantum = quanta[field]
        if Decimal(str(corrected_value)).quantize(quantum) != Decimal(
            str(corrected_value)
        ):
            raise ValueError(
                f'{field} {corrected_value} does not fit {quantum} precision'
            )

    curve['fragility_model'] = f'{reference_id}|{target_model}'
    curve['median'] = corrected['median']
    curve['beta'] = corrected['beta']
    print(
        f'  ds_rank {ds_rank} curve moved from model {source_model} to '
        f'{target_model}: median {expected["median"]} -> '
        f'{corrected["median"]}, beta {expected["beta"]} -> {corrected["beta"]}'
    )

    for model_id, wanted in ((source_model, [1, 2]), (target_model, [1, 2, 3])):
        ranks = ranks_of(curves, model_id)
        if ranks != wanted:
            raise ValueError(
                f'{reference_id} model {model_id} should end with damage '
                f'states {wanted}, has {ranks}'
            )
        print(f'  model {model_id} damage states: {ranks}')


# Edits are applied in order against the shared store. Append new ones here.
EDITS: list[tuple[str, Callable[[DataStore], None]]] = [
    (
        'Divide Davies-2011 fragility medians by 100 (percent -> ratio)',
        divide_davies_2011_medians_by_100,
    ),
    (
        'Rename Davies-2011 model ids to their source labels',
        rename_davies_2011_model_ids,
    ),
    (
        'Correct individual Davies-2011 curve medians',
        correct_davies_2011_medians,
    ),
    (
        'Correct individual Davies-2011 curve betas',
        correct_davies_2011_betas,
    ),
    (
        'Move the Davies-2011 model 2a damage state 3 curve to model 2c',
        move_davies_2011_2a_ds3_to_2c,
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Report every value that would change without writing any file.',
    )
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=DATA_DIR,
        help='Directory of canonical JSON files to edit (default: resources/data).',
    )
    args = parser.parse_args()

    store = DataStore(args.data_dir)
    for name, edit in EDITS:
        print(name)
        edit(store)

    if args.dry_run:
        print('\nDry run: no files were written.')
        return

    written = store.save()
    if not written:
        print('\nNo file contents changed; nothing was written.')
        return

    print('\nUpdated ' + ', '.join(written))
    print(
        'Next: rebuild from a DELETED db.sqlite3 (ingest cannot retire the '
        'rows left behind by an id rename), regenerate the fixture, then run '
        'python manage.py test ned_app.tests -- see this module docstring.'
    )


if __name__ == '__main__':
    main()
