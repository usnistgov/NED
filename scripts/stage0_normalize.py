#!/usr/bin/env python
r"""Experiment split, Stage 0a: mechanical whitespace normalization of the flat data.

One-off, scripted edit to ``resources/data/experiment.json`` (or
``observation.json`` after the Stage 3 rename), committed together with its
output. Per the README's rule for systematic edits, remove it in a follow-up
commit once the change is merged.

In every column the split groups on or stores at a parent grain, it collapses
runs of whitespace and trims the ends. Short label columns also lose their line
breaks, which are data-entry artifacts there. The free-text columns
``comp_description``, ``loading_protocol`` and ``peak_test_amplitude`` keep
their line breaks. Every value whose line breaks are removed is listed, so a
human can check none was meaningful. Within one specimen, free-text values that
differ *only* in line breaks are then harmonized to the most common layout.

Only layout changes, never words. ``prior_damage_repaired`` is deliberately not
touched: it moves verbatim to ``Observation.legacy_prior_damage_repaired``
(decision 7).

The rules come from ``measure_split_inputs.py``, so this script and the
measurements cannot disagree. It is idempotent: a second run changes nothing.

Usage (run from the repository root):

    python scripts/stage0_normalize.py            # dry run: report only
    python scripts/stage0_normalize.py --apply    # write the file

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
from collections import Counter, defaultdict
from pathlib import Path

# Same directory as this script, so a plain `python scripts/stage0_normalize.py`
# finds it. It owns the normalization and grouping rules.
from measure_split_inputs import (
    DEFAULT_DATA_DIR,
    MULTILINE_FIELDS,
    NED,
    NORMALIZED_FIELDS,
    contributor_field,
    flatten,
    normalize,
    specimen_key,
)


def normalize_rows(rows: list[dict], fields: tuple[str, ...]) -> dict:
    """Normalize whitespace in place. Return per-field change counts and notes."""
    changed: Counter = Counter()
    flattened = []  # (id, field, before) for line breaks removed from label fields
    for row in rows:
        for field in fields:
            before = row[field]
            after = normalize(field, before)
            if after == before:
                continue
            changed[field] += 1
            row[field] = after
            if (
                field not in MULTILINE_FIELDS
                and isinstance(before, str)
                and ('\n' in before or '\r' in before)
            ):
                flattened.append((row['id'], field, before))
    return {'changed': changed, 'flattened': flattened}


def harmonize_line_breaks(rows: list[dict]) -> list[tuple]:
    """Within each specimen, give texts that differ only in line breaks one layout.

    The most common layout wins; ties go to the layout with more line breaks
    (it keeps more structure), then to the alphabetically first. Only the layout
    changes, never the words. Returns (specimen key, field, rows changed).
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[specimen_key(row)].append(row)
    changes = []
    for key, grows in groups.items():
        for field in sorted(MULTILINE_FIELDS):
            by_text: dict[object, Counter] = defaultdict(Counter)
            for row in grows:
                by_text[flatten(row[field])][row[field]] += 1
            for layouts in by_text.values():
                if len(layouts) < 2:
                    continue
                best = min(layouts, key=lambda v: (-layouts[v], -v.count('\n'), v))
                moved = [
                    r for r in grows if r[field] in layouts and r[field] != best
                ]
                for row in moved:
                    row[field] = best
                changes.append((key, field, len(moved)))
    return changes


def write_export_format(path: Path, rows: list[dict]) -> None:
    """Write ``rows`` exactly as ``export_data`` would (indent 4, sorted keys)."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=4, sort_keys=True)


def main() -> int:
    """Normalize the flat data, reporting by default and writing with --apply."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument('--apply', action='store_true', help='write the changes')
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='examples per section; 0 shows all (default 20)',
    )
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
    rows = json.loads(path.read_text(encoding='utf-8'))

    # Normalize the file's own contributor column, whatever it is called.
    contributor = contributor_field(rows)
    fields = tuple(
        contributor if f == 'contributor' else f for f in NORMALIZED_FIELDS
    )
    ws = normalize_rows(rows, fields)
    layout = harmonize_line_breaks(rows)

    limit = None if args.limit == 0 else args.limit
    print(f'# Stage 0a normalization of `{path.relative_to(NED)}`\n')
    print('## Whitespace: rows changed per column\n')
    print('| Column | Rows changed |')
    print('|---|---|')
    for field in fields:
        print(f'| {field} | {ws["changed"][field]} |')
    print(f'\n## Line breaks removed from label columns ({len(ws["flattened"])})\n')
    print('Check that none of these line breaks carried meaning.\n')
    for row_id, field, before in ws['flattened'][:limit]:
        print(f'- `{row_id}` {field}: {before!r}')
    print(f'\n## Line-break-only variants harmonized ({len(layout)})\n')
    for (ref, spec), field, n in layout:
        print(f'- {ref} | {spec} - {field}: {n} rows given the common layout')

    total = sum(ws['changed'].values()) + sum(n for *_, n in layout)
    if not args.apply:
        print(
            f'\nDry run: {total} cell changes found, nothing written. '
            'Re-run with --apply to write.'
        )
        return 0
    write_export_format(path, rows)
    print(f'\nWrote {total} cell changes to {path.relative_to(NED)}.')
    print(
        'Next: regenerate the fixture from a fresh build, then re-measure '
        "(see this script's docstring)."
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
