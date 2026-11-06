r"""Experiment split, Stage 0b case 7: one correct location string per laboratory.

One-off, scripted edit to ``resources/data/experiment.json`` (or
``observation.json`` after the Stage 3 rename), committed together with its
output. Per the README's rule for systematic edits, remove it in a follow-up
commit once the change is merged.

When the table is split, each distinct ``location`` string becomes one
Facility. So within a reference, one laboratory spelled several ways becomes
several facilities, and a wrong value becomes a wrong facility. Each change
below comes from reading the reference: it gives every specimen tested in the
same laboratory one string, preferring a string the reference (or the dataset)
already uses; corrects values that don't name where the specimen was tested;
and, where the paper names no laboratory, generalizes to the country the
reference supports rather than guessing a facility. Merging the same
laboratory across references, and naming facilities, is later curation.

Each change is keyed on (reference, current location), covers every row of the
reference with that string, and is guarded by the number of rows it expects to
change, so it never touches a row it wasn't written for. It is idempotent: a
second run changes nothing.

Usage (run from the repository root):

    python scripts/stage0b_locations.py            # dry run: report only
    python scripts/stage0b_locations.py --apply    # write the file

After ``--apply``, regenerate the fixture from a fresh build and re-measure:

    rm db.sqlite3 && python manage.py migrate && python manage.py ingest
    PYTHONUTF8=1 python manage.py dumpdata ned_app --indent 2 \
        --output ned_app/fixtures/initial_data.json
    python scripts/measure_split_inputs.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Same directory as this script, so a plain `python scripts/...` finds them.
from measure_split_inputs import DEFAULT_DATA_DIR, NED
from stage0_normalize import write_export_format

UC = 'University of Canterbury, New Zealand'

# (reference, current location) -> (new location, rows expected to change)
CHANGES = {
    # Config12. Specimen 31's exp1917a: "Sliding" was copied from comp_detail
    # ("Full height - Sliding"). Every Davies wall was tested on the UB-NCS in
    # Buffalo, which the other 194 rows already say.
    ('Davies-2011', 'Sliding'): ('Buffalo, NY', 1),
    # One facility: the BNCS building on the UCSD shake table. Five partition
    # wall specimens and the fire sprinkler system used other spellings.
    ('Pantoli_NCS_DamageStates-2016', 'UCSD, California'): (
        'NHERI, U of California San Diego',
        20,
    ),
    ('Pantoli_NCS_DamageStates-2016', 'California'): (
        'NHERI, U of California San Diego',
        3,
    ),
    # One test bed at the UNR-NEES site; "Nevada" is a region, not a laboratory.
    ('Rahmanishamsi_CPP_TestBed-2014', 'Nevada'): ('UNR-NEES site', 13),
    # All six walls were tested in one frame in the University of Canterbury
    # structures laboratory.
    ('Tasligedik-2014', 'New Zealand'): (UC, 9),
    # Every specimen is a physical test from one University of Canterbury
    # program: the brace and hanger-rod component tests ("New Zealand") and the
    # shake-table piping specimens ("Not applicable", an entry error).
    ('Rashid-2022', 'New Zealand'): (UC, 62),
    ('Rashid-2022', 'Not applicable'): (UC, 18),
    # The 22 racking-test specimens compiled from John A. Blume and Associates
    # Research Division reports: "San Francisco" is only where the reports were
    # issued, and no source says where the tests ran, so generalize to the
    # country, using the dataset's existing string.
    ('Mosqueda-2016', 'San Francisco'): ('US', 39),
    # Blank: the paper names no laboratory, but the program is Chinese (Nanjing
    # and Tongji University authors, Chinese national funding, a cited SKLDRCE
    # Shanghai report).
    ('Huang-2017', ''): ('China', 8),
}


def main() -> int:
    """Apply the location changes, reporting by default and writing with --apply."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument('--apply', action='store_true', help='write the changes')
    args = parser.parse_args()

    path = next(
        (
            args.data_dir / n
            for n in ('experiment.json', 'observation.json')
            if (args.data_dir / n).exists()
        ),
        None,
    )
    if path is None:
        sys.exit(f'No experiment.json or observation.json in {args.data_dir}')
    shown = path.relative_to(NED) if path.is_relative_to(NED) else path
    rows = json.loads(path.read_text(encoding='utf-8'))

    print(f'# Stage 0b location changes to `{shown}`\n')
    print('| Reference | Location | Becomes | Rows |')
    print('|---|---|---|---|')
    total = 0
    for (ref, old), (new, expected) in CHANGES.items():
        hits = [r for r in rows if r['reference'] == ref and r['location'] == old]
        if not hits:
            print(f'| {ref} | {old!r} | {new!r} | already applied |')
            continue
        if len(hits) != expected:
            sys.exit(
                f'Refused: {ref} has {len(hits)} rows with location {old!r}, '
                f'expected {expected}'
            )
        for r in hits:
            r['location'] = new
        total += len(hits)
        print(f'| {ref} | {old!r} | {new!r} | {len(hits)} |')

    if not args.apply:
        print(f'\nDry run: {total} rows would change. Re-run with --apply to write.')
        return 0
    write_export_format(path, rows)
    print(f'\nWrote {total} changed rows to {shown}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
