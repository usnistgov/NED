#!/usr/bin/env python
"""Measure the flat Experiment data against the Experiment-split conversion rules.

Read-only. Reports every problem the strict conversion (steps doc, Stage 6) would
refuse, plus the figures for the decision log's "Measured facts" appendix, so the
Stage 0 curation pass can watch its own progress. Nothing is written.

The grouping and normalization helpers here (``normalize``, ``slugify``,
``specimen_key``, ``test_key``) are the single definition of those rules, and
the Stage 6 conversion tool will import them.

Usage (run from the repository root):

    python scripts/measure_split_inputs.py
    python scripts/measure_split_inputs.py --limit 0          # every detail row
    python scripts/measure_split_inputs.py --strict           # exit 1 if blocking
    python scripts/measure_split_inputs.py --json build/measure.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

NED = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = NED / 'resources' / 'data'
DEFAULT_ACCEPTED = NED / 'resources' / 'archive' / 'split_accepted_collapses.json'

# Columns that move to Specimen, and must therefore be constant within a specimen.
SPECIMEN_FIELDS = (
    'contributor',
    'component',
    'comp_detail',
    'material',
    'size_class',
    'design_objective',
    'governing_design_standard',
    'comp_description',
    'location',
)
# Columns that identify a test within its specimen (the one-time grouping rule).
TEST_GROUP_FIELDS = (
    'test_type',
    'loading_protocol',
    'peak_test_amplitude',
    'specimen_inspection_sequence',
)
# prior_damage_repaired is deliberately absent: like prior_damage it was recorded
# per observation, so it moves verbatim to Observation.legacy_prior_damage_repaired
# and is neither normalized nor required to agree within a test (decision 7).

# Every column the conversion groups on or stores at a parent grain.
NORMALIZED_FIELDS = ('specimen', *SPECIMEN_FIELDS, *TEST_GROUP_FIELDS)
# Free-text columns whose line breaks carry structure (numbered lists, one
# amplitude per line). Their line breaks are kept; every other normalized column
# is a short label or tag, where a line break is a data-entry artifact.
MULTILINE_FIELDS = frozenset({
    'comp_description',
    'loading_protocol',
    'peak_test_amplitude',
})

_INLINE_WS = re.compile(r'[ \t\f\v ]+')
_ANY_WS = re.compile(r'\s+')
_SLUG_INVALID = re.compile(r'[^A-Za-z0-9_.-]+')


def normalize(field: str, value: object) -> object:
    """Return ``value`` with whitespace normalized for ``field``.

    Single-line fields collapse every run of whitespace, line breaks included, to
    one space. Multi-line fields keep their line breaks (CR and CRLF become LF),
    collapse spaces within each line, and drop blank lines. Both trim the ends.
    Non-string values are returned unchanged.
    """
    if not isinstance(value, str):
        return value
    if field not in MULTILINE_FIELDS:
        return _ANY_WS.sub(' ', value).strip()
    lines = value.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    lines = [_INLINE_WS.sub(' ', line).strip() for line in lines]
    return '\n'.join(line for line in lines if line)


def flatten(value: object) -> object:
    """Return ``value`` with all whitespace, line breaks included, collapsed.

    Two texts with the same flattened form differ only in layout. Within one
    specimen they are the same fact written twice, so Stage 0a harmonizes them.
    """
    return _ANY_WS.sub(' ', value).strip() if isinstance(value, str) else value


def line_break_variants(rows: list[dict]) -> list[dict]:
    """List (specimen, field) pairs holding texts that differ only in line breaks.

    Only the multi-line fields can produce these: every other normalized field
    already has its line breaks collapsed by ``normalize``.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[specimen_key(row)].append(row)
    found = []
    for key, grows in groups.items():
        for field in sorted(MULTILINE_FIELDS):
            forms = {normalize(field, r[field]) for r in grows}
            if len({flatten(f) for f in forms}) < len(forms):
                found.append({
                    'group': list(key),
                    'field': field,
                    'forms': len(forms),
                })
    return found


def slugify(label: str) -> str:
    """Return the specimen-label slug (design §2.2): safe characters only."""
    return _SLUG_INVALID.sub('_', _ANY_WS.sub(' ', label).strip()).strip('_')


def contributor_field(rows: list[dict]) -> str:
    """Return the name of the contributor column (``reviewer`` before the rename)."""
    return 'reviewer' if rows and 'reviewer' in rows[0] else 'contributor'


def specimen_key(row: dict) -> tuple[str, str]:
    """Return the ``(reference, specimen)`` key a row's specimen is grouped on."""
    return row['reference'], normalize('specimen', row['specimen'])


def test_key(row: dict) -> tuple:
    """Return the key a row's test is grouped on: its specimen plus the test fields."""
    return (*specimen_key(row), *(normalize(f, row[f]) for f in TEST_GROUP_FIELDS))


def load_rows(data_dir: Path) -> tuple[Path, list[dict]]:
    """Load the flat observation file, before or after the Stage 3 rename."""
    for name in ('experiment.json', 'observation.json'):
        path = data_dir / name
        if path.exists():
            rows = json.loads(path.read_text(encoding='utf-8'))
            # Map the old column name so the rules can use one name throughout.
            if contributor_field(rows) == 'reviewer':
                rows = [{**r, 'contributor': r['reviewer']} for r in rows]
            return path, rows
    sys.exit(f'No experiment.json or observation.json in {data_dir}')


def load_accepted(path: Path) -> list[dict]:
    """Load the accepted-collapses file; a missing file means no entries."""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8'))


def _accepted_index(accepted: list[dict]) -> set[tuple]:
    """Index accepted entries by (specimen key, field), using normalized values."""
    return {
        ((e['reference'], normalize('specimen', e['specimen'])), e['field'])
        for e in accepted
    }


def _parse_sequence(value: str) -> int | str | None:
    """Parse a sequence string to an int; '' gives None, anything else 'invalid'."""
    if value == '':
        return None
    try:
        number = float(value)
    except ValueError:
        return 'invalid'
    return int(number) if number.is_integer() and number > 0 else 'invalid'


def _disagreements(groups: dict, fields: tuple, accepted: set[tuple]) -> list[dict]:
    """List groups in which a field takes more than one normalized value."""
    found = []
    for key, rows in groups.items():
        for field in fields:
            values = Counter(normalize(field, r[field]) for r in rows)
            if len(values) > 1:
                found.append({
                    'group': list(key),
                    'field': field,
                    'values': dict(values.most_common()),
                    'row_ids': sorted(r['id'] for r in rows),
                    'accepted': (key, field) in accepted,
                })
    return found


def measure(rows: list[dict], accepted: list[dict]) -> dict:
    """Compute every check and figure over the flat rows. Pure: no I/O."""
    accepted_idx = _accepted_index(accepted)
    specimens: dict[tuple, list[dict]] = defaultdict(list)
    tests: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        specimens[specimen_key(row)].append(row)
        tests[test_key(row)].append(row)

    blocking: dict[str, list] = {}
    info: dict[str, object] = {}

    blocking['blank_specimen'] = sorted(
        r['id'] for r in rows if normalize('specimen', r['specimen']) == ''
    )
    blocking['whitespace_variants'] = {
        f: sorted(r['id'] for r in rows if r[f] != normalize(f, r[f]))
        for f in NORMALIZED_FIELDS
    }

    blocking['line_break_variants'] = line_break_variants(rows)

    spec_dis = _disagreements(specimens, SPECIMEN_FIELDS, accepted_idx)
    blocking['specimen_field_disagreements'] = [
        d for d in spec_dis if not d['accepted']
    ]

    # Raw spellings within one location group (trim, collapse, case-fold).
    spellings: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        loc = normalize('location', row['location'])
        spellings[loc.casefold()][loc] += 1
    blocking['location_spellings'] = [
        dict(c) for c in spellings.values() if len(c) > 1
    ]

    # Sequence values: parseable, and unique across the tests of a specimen.
    sequences = {
        normalize('specimen_inspection_sequence', r['specimen_inspection_sequence'])
        for r in rows
    }
    blocking['invalid_sequences'] = sorted(
        s for s in sequences if _parse_sequence(s) == 'invalid'
    )
    per_specimen: dict[tuple, Counter] = defaultdict(Counter)
    for key in tests:
        if key[-1] != '':
            per_specimen[key[:2]][key[-1]] += 1
    blocking['duplicate_sequences'] = [
        {'specimen': list(k), 'sequence': s}
        for k, c in per_specimen.items()
        for s, n in c.items()
        if n > 1
    ]

    # Slug collisions within a reference, compared case-insensitively.
    specimen_keys = list(specimens)  # (reference, label) pairs
    slugs: dict[tuple, set] = defaultdict(set)
    for ref, label in specimen_keys:
        if label:
            slugs[ref, slugify(label).casefold()].add(label)
    blocking['slug_collisions'] = [
        {'reference': ref, 'labels': sorted(labels)}
        for (ref, _), labels in slugs.items()
        if len(labels) > 1
    ]
    blocking['empty_slugs'] = sorted(
        f'{ref} | {label}'
        for ref, label in specimen_keys
        if label and not slugify(label)
    )
    blocking['accepted_collapses_present'] = accepted  # AC14 target: zero

    # Informational figures.
    multi_test = defaultdict(list)
    for key in tests:
        multi_test[key[:2]].append(key)
    by_ref_labels: dict[str, list] = defaultdict(list)
    for ref, label in specimen_keys:
        by_ref_labels[ref].append(label)
    ref_locations = defaultdict(Counter)
    for row in rows:
        ref_locations[row['reference']][normalize('location', row['location'])] += 1
    info.update({
        'rows': len(rows),
        'references': len({r['reference'] for r in rows}),
        'specimen_groups': len(specimens),
        'tests': len(tests),
        'tests_with_several_observations': sum(
            1 for t in tests.values() if len(t) > 1
        ),
        'rows_in_multi_observation_tests': sum(
            len(t) for t in tests.values() if len(t) > 1
        ),
        'largest_test': max((len(t) for t in tests.values()), default=0),
        'specimens_with_several_tests': sum(
            1 for k in multi_test.values() if len(k) > 1
        ),
        'unordered_multi_test_specimens': sorted(
            ' | '.join(s)
            for s, ks in multi_test.items()
            if len(ks) > 1 and all(k[-1] == '' for k in ks)
        ),
        'labels_changed_by_slug': sum(
            1 for _, label in specimens if label and slugify(label) != label
        ),
        'longest_slug': max((len(slugify(lbl)) for _, lbl in specimens), default=0),
        'numeric_only_label_references': {
            ref: sorted(labels)
            for ref, labels in by_ref_labels.items()
            if labels and all(lbl.isdigit() for lbl in labels)
        },
        'blank_location_specimens': sorted(
            ' | '.join(k)
            for k, srows in specimens.items()
            if all(normalize('location', r['location']) == '' for r in srows)
        ),
        'references_with_several_locations': {
            ref: dict(c) for ref, c in ref_locations.items() if len(c) > 1
        },
        'replacement_characters': sorted(
            r['id'] for r in rows if any('�' in str(v) for v in r.values())
        ),
        'non_null_ds_rank': sum(1 for r in rows if r.get('ds_rank') is not None),
        'non_blank_prior_damage': sum(1 for r in rows if r.get('prior_damage')),
        'prior_damage_repaired_values': dict(
            Counter(r['prior_damage_repaired'] for r in rows).most_common()
        ),
        'specimen_field_disagreements_accepted': [
            d for d in spec_dis if d['accepted']
        ],
    })
    return {'blocking': blocking, 'info': info}


def _count(value: object) -> int:
    """Count a check's findings, summing per-column dicts."""
    if isinstance(value, dict):
        return sum(len(v) for v in value.values())
    return len(value)


def _print_list(title: str, items: list, limit: int) -> None:
    """Print up to ``limit`` items under a heading (0 means no limit)."""
    if not items:
        return
    print(f'\n### {title} ({len(items)})')
    shown = items if limit == 0 else items[:limit]
    for item in shown:
        print(f'- {item}')
    if len(shown) < len(items):
        print(f'- ... {len(items) - len(shown)} more (use --limit 0)')


def report(source: Path, result: dict, limit: int) -> None:
    """Print the measurements as Markdown."""
    blocking, info = result['blocking'], result['info']
    print('# Experiment-split input measurements\n')
    print(f'Source: `{source.relative_to(NED)}` ({info["rows"]} rows)\n')
    print('## Stage 0 blocking checks (all must be 0)\n')
    print('| Check | Count |')
    print('|---|---|')
    for name, value in blocking.items():
        print(f'| {name} | {_count(value)} |')

    print('\n## Figures\n')
    print('| Quantity | Value |')
    print('|---|---|')
    for name, value in info.items():
        if isinstance(value, (int, str)) or name == 'prior_damage_repaired_values':
            print(f'| {name} | {value} |')
        else:
            print(f'| {name} | {len(value)} (listed below) |')

    print('\n## Details')
    _print_list('blank_specimen', blocking['blank_specimen'], limit)
    variants = blocking['whitespace_variants']
    for field, ids in variants.items():
        _print_list(f'whitespace_variants: {field}', ids, limit)
    _print_list(
        'specimen_field_disagreements',
        [
            f'{" | ".join(d["group"])} - {d["field"]}: {d["values"]}'
            for d in blocking['specimen_field_disagreements']
        ],
        limit,
    )
    for name in (
        'line_break_variants',
        'location_spellings',
        'invalid_sequences',
        'duplicate_sequences',
        'slug_collisions',
        'empty_slugs',
        'accepted_collapses_present',
    ):
        _print_list(name, blocking[name], limit)
    for name in (
        'unordered_multi_test_specimens',
        'blank_location_specimens',
        'replacement_characters',
    ):
        _print_list(name, info[name], limit)
    for name in (
        'numeric_only_label_references',
        'references_with_several_locations',
    ):
        _print_list(name, [f'{k}: {v}' for k, v in info[name].items()], limit)


def main() -> int:
    """Run the measurements and print or save them."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        '--accepted',
        type=Path,
        default=DEFAULT_ACCEPTED,
        help='accepted-collapses file (missing = no entries)',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='detail rows per section; 0 shows all (default 20)',
    )
    parser.add_argument('--json', type=Path, help='also write the results here')
    parser.add_argument(
        '--strict',
        action='store_true',
        help='exit 1 if any blocking check is non-zero',
    )
    args = parser.parse_args()

    source, rows = load_rows(args.data_dir)
    result = measure(rows, load_accepted(args.accepted))
    report(source, result, args.limit)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(result, indent=2, default=list), encoding='utf-8'
        )
    blocked = any(_count(v) for v in result['blocking'].values())
    return 1 if args.strict and blocked else 0


if __name__ == '__main__':
    sys.exit(main())
