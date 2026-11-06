r"""Split the flat observation data into Facility, Program, Specimen and Test files.

The one-time conversion of the Experiment split (steps doc, Stage 6; design §2).
It reads ``observation.json`` from ``--input`` plus the accepted-collapses file,
and writes into ``--output`` (never in place):

- ``facility.json``, ``program.json``, ``specimen.json`` and ``test.json``;
- ``observation.json`` with each record's ``test`` and ``label`` set and nothing
  else changed;
- ``report.md``, always.

Every file is written in the key set and format ``export_data`` writes. On any
rule violation the report lists every error, no data is written, and the exit
status is 1. ``--check`` validates and writes only the report.

The grouping and normalization rules come from ``measure_split_inputs.py``, so
the measurements and the conversion cannot drift apart. Every grouping and every
minted label follows a fully specified sort: two runs over the same input write
byte-identical files. Reference ids are taken as stored in each observation's
``reference`` (reference.json holds no ids), so the tool needs no Django.

Usage (run from the repository root):

    python scripts/split_observations.py convert --input resources/data \
        --accepted resources/archive/split_accepted_collapses.json \
        --output build/split
    python scripts/split_observations.py convert ... --check   # report only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from measure_split_inputs import (
    SPECIMEN_FIELDS as MEASURED_SPECIMEN_FIELDS,
)
from measure_split_inputs import (
    _accepted_index,
    _parse_sequence,
    load_accepted,
    normalize,
    slugify,
    specimen_key,
    test_key,
)

# Specimen-grain columns that must be constant within a specimen (or accepted).
# ``location`` is not among them: it seeds Facility, under its own rules.
SPECIMEN_FIELDS = tuple(f for f in MEASURED_SPECIMEN_FIELDS if f != 'location')

# The keys export_data writes for each new model (Stage 5). Every record this
# tool writes has exactly these keys.
EXPORT_KEYS = {
    'facility.json': frozenset({'label', 'name', 'location', 'notes'}),
    'program.json': frozenset({'label', 'name', 'notes', 'reference'}),
    'specimen.json': frozenset({
        'program',
        'facility',
        'reference',
        'label',
        'name',
        'contributor',
        'component',
        'comp_detail',
        'material',
        'size_class',
        'design_objective',
        'governing_design_standard',
        'comp_description',
        'notes',
    }),
    'test.json': frozenset({
        'specimen',
        'label',
        'test_order',
        'test_type',
        'loading_protocol',
        'peak_test_amplitude',
        'prior_damage',
        'prior_damage_repaired',
        'notes',
    }),
}
DATA_FILES = (*EXPORT_KEYS, 'observation.json')
REPORT = 'report.md'

# The rule behind each error code, as the report states it.
RULES = {
    'facility.location_varies': 'location is not constant within a specimen',
    'facility.spellings': 'more than one raw spelling in a location group',
    'facility.label_collision': 'facility label collision (case-insensitive)',
    'specimen.blank': 'blank specimen',
    'specimen.label_collision': 'specimen label collision within a program '
    '(case-insensitive)',
    'specimen.disagreement': 'specimen-level field disagrees within the specimen '
    'and is not in the accepted-collapses file',
    'accepted.no_group': 'accepted entry matches no specimen group and field',
    'accepted.no_value': 'accepted entry names a value no row holds',
    'accepted.duplicate': 'more than one accepted entry for a group and field',
    'test.invalid_sequence': 'sequence is not a positive integer',
    'test.duplicate_order': 'duplicate test_order within a specimen',
    'label.empty': 'label slugs to an empty string',
    'label.invalid': 'label fails validate_label (1-100 of A-Z a-z 0-9 _ . -)',
}

_LABEL = re.compile(r'[A-Za-z0-9_.-]{1,100}')  # mirrors validators.validate_label


@dataclass(frozen=True)
class Problem:
    """One rule violation: where it is, and every competing value with row ids."""

    rule: str
    reference: str = ''
    specimen: str = ''
    test: str = ''
    detail: str = ''
    values: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass
class Split:
    """The conversion's output tables, errors and report facts."""

    rows_in: int = 0
    errors: list[Problem] = field(default_factory=list)
    tables: dict[str, list[dict]] = field(default_factory=dict)
    # label -> (location, specimen count)
    facilities: dict[str, tuple[str, int]] = field(default_factory=dict)
    # reference -> facility labels, for references spanning several facilities
    multi_facility_refs: dict[str, list[str]] = field(default_factory=dict)
    # specimen id -> [(test label, test_order)], for multi-test specimens
    multi_test: dict[str, list[tuple[str, int | None]]] = field(default_factory=dict)
    # (entry, overridden row ids, chosen value) for each accepted entry applied
    applied: list[tuple[dict, list[str], str]] = field(default_factory=list)


def letter_label(index: int) -> str:
    """Return the ``index``-th letter label: 0 -> a, 25 -> z, 26 -> aa, 27 -> ab."""
    label = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        label = chr(ord('a') + rem) + label
    return label


def _values(rows: list[dict], fld: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Group row ids by a field's normalized value, as ``(json value, ids)``."""
    groups: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        groups[json.dumps(normalize(fld, row[fld]), ensure_ascii=False)].append(
            row['id']
        )
    return tuple((v, tuple(sorted(ids))) for v, ids in sorted(groups.items()))


def _test_text(key: tuple) -> str:
    """Return a test key's four grouping values as readable text."""
    return json.dumps(list(key[2:]), ensure_ascii=False)


def _check_label(label: str, err: list[Problem], **where: str) -> bool:
    """Record an error if ``label`` fails the label rule; return whether it passed."""
    if not label:
        err.append(Problem('label.empty', **where))
        return False
    if not _LABEL.fullmatch(label):
        err.append(Problem('label.invalid', detail=label, **where))
        return False
    return True


def _programs(rows: list[dict], split: Split) -> None:
    """One blank-labelled program per reference that has observations.

    Built from observation.json alone, so a reference with no observations gets
    no program (an empty program would be an orphan, AC11).
    """
    split.tables['program.json'] = [
        {'reference': ref, 'label': '', 'name': '', 'notes': ''}
        for ref in sorted({row['reference'] for row in rows})
    ]


def _accepted_values(
    accepted: list[dict], specimens: dict[tuple, list[dict]], split: Split
) -> dict[tuple, str]:
    """Validate the accepted entries; map (specimen key, field) to the chosen value."""
    chosen: dict[tuple, str] = {}
    seen: Counter = Counter()
    for entry in accepted:
        # The same (specimen key, field) the measure script matches on.
        (index_key,) = _accepted_index([entry])
        seen[index_key] += 1
        key, fld = index_key
        where = {'reference': key[0], 'specimen': key[1], 'detail': fld}
        if fld not in SPECIMEN_FIELDS or key not in specimens:
            split.errors.append(Problem('accepted.no_group', **where))
            continue
        value = normalize(fld, entry['value'])
        if value not in {normalize(fld, r[fld]) for r in specimens[key]}:
            split.errors.append(
                Problem(
                    'accepted.no_value',
                    values=_values(specimens[key], fld),
                    **{**where, 'detail': f'{fld} = {json.dumps(value)}'},
                )
            )
            continue
        chosen[index_key] = value
        overridden = sorted(
            r['id'] for r in specimens[key] if normalize(fld, r[fld]) != value
        )
        split.applied.append((entry, overridden, value))
    for (key, fld), n in sorted(seen.items()):
        if n > 1:
            split.errors.append(
                Problem(
                    'accepted.duplicate',
                    reference=key[0],
                    specimen=key[1],
                    detail=f'{fld} ({n} entries)',
                )
            )
            chosen.pop((key, fld), None)
    return chosen


def _facilities(
    specimens: dict[tuple, list[dict]], split: Split
) -> dict[tuple, str]:
    """Seed facilities from ``location``; return each specimen's facility label."""
    located: dict[tuple, str] = {}
    for key, rows in specimens.items():
        values = _values(rows, 'location')
        if len(values) > 1:
            split.errors.append(
                Problem(
                    'facility.location_varies',
                    reference=key[0],
                    specimen=key[1],
                    values=values,
                )
            )
        else:
            located[key] = normalize('location', rows[0]['location'])

    # Group by trimmed, collapsed and case-folded location.
    groups: dict[str, list[tuple]] = defaultdict(list)
    for key, loc in located.items():
        if loc:
            groups[loc.casefold()].append(key)
    facility_of: dict[tuple, str] = {}
    # (label, location) -> the specimens it seeds
    seeds: dict[tuple[str, str], list[tuple]] = defaultdict(list)
    for folded in sorted(groups):
        keys = groups[folded]
        spellings = {located[k] for k in keys}
        if len(spellings) > 1:
            rows = [r for k in keys for r in specimens[k]]
            split.errors.append(
                Problem(
                    'facility.spellings',
                    detail=folded,
                    values=_values(rows, 'location'),
                )
            )
            continue
        (spelling,) = spellings
        label = slugify(spelling)
        if not _check_label(label, split.errors, detail=f'location {spelling!r}'):
            continue
        seeds[label, spelling] = keys
        for k in keys:
            facility_of[k] = label
    # A specimen with no location: one placeholder per reference.
    for key, loc in located.items():
        if not loc:
            label = f'unknown_{key[0]}'
            if _check_label(label, split.errors, reference=key[0]):
                seeds[label, ''].append(key)
                facility_of[key] = label

    # Labels must be unique case-insensitively.
    folded_labels: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for seed in seeds:
        folded_labels[seed[0].casefold()].append(seed)
    for _, colliding in sorted(folded_labels.items()):
        if len(colliding) > 1:
            rows = [
                r for seed in colliding for k in seeds[seed] for r in specimens[k]
            ]
            split.errors.append(
                Problem(
                    'facility.label_collision',
                    detail=', '.join(sorted({lbl for lbl, _ in colliding})),
                    values=_values(rows, 'location'),
                )
            )

    split.facilities = {
        label: (loc, len(keys))
        for (label, loc), keys in sorted(
            seeds.items(), key=lambda s: (s[0][0].casefold(), s[0])
        )
    }
    by_ref: dict[str, set[str]] = defaultdict(set)
    for key, label in facility_of.items():
        by_ref[key[0]].add(label)
    split.multi_facility_refs = {
        ref: sorted(labels)
        for ref, labels in sorted(by_ref.items())
        if len(labels) > 1
    }
    split.tables['facility.json'] = [
        {'label': label, 'location': loc, 'name': '', 'notes': ''}
        for label, (loc, _) in split.facilities.items()
    ]
    return facility_of


def _specimens(
    specimens: dict[tuple, list[dict]],
    facility_of: dict[tuple, str],
    accepted: dict[tuple, str],
    split: Split,
) -> dict[tuple, str]:
    """Build one specimen per (reference, specimen); return each one's label."""
    label_of: dict[tuple, str] = {}
    records = []
    for key in sorted(specimens):
        ref, name = key
        rows = specimens[key]
        label = slugify(name)
        _check_label(label, split.errors, reference=ref, specimen=name)
        label_of[key] = label
        record = {
            'program': ref,
            'facility': facility_of.get(key),
            'reference': None,
            'label': label,
            'name': name,
            'notes': '',
        }
        for fld in SPECIMEN_FIELDS:
            values = {normalize(fld, r[fld]) for r in rows}
            if len(values) == 1:
                (record[fld],) = values
            elif (key, fld) in accepted:
                record[fld] = accepted[key, fld]
            else:
                split.errors.append(
                    Problem(
                        'specimen.disagreement',
                        reference=ref,
                        specimen=name,
                        detail=fld,
                        values=_values(rows, fld),
                    )
                )
                record[fld] = None
        records.append(record)

    # Labels must be unique within a program, case-insensitively.
    by_label: dict[tuple, list[str]] = defaultdict(list)
    for (ref, name), label in label_of.items():
        if label:
            by_label[ref, label.casefold()].append(name)
    for (ref, folded), names in sorted(by_label.items()):
        if len(names) > 1:
            rows = [r for n in names for r in specimens[ref, n]]
            split.errors.append(
                Problem(
                    'specimen.label_collision',
                    reference=ref,
                    detail=folded,
                    values=_values(rows, 'specimen'),
                )
            )
    split.tables['specimen.json'] = sorted(
        records, key=lambda s: (s['program'], s['label'].casefold(), s['label'])
    )
    return label_of


def _test_sort_key(item: tuple[tuple, int | None]) -> tuple:
    """Sort a ``(test key, test_order)`` pair as design §2.3 mints labels.

    test_order (nulls last), test_type, loading_protocol, peak_test_amplitude. The
    raw sequence breaks the one tie left (a duplicated order, already an error).
    """
    tkey, order = item
    return (order is None, order or 0, *tkey[2:5], tkey[-1])


def _tests(
    specimens: dict[tuple, list[dict]], label_of: dict[tuple, str], split: Split
) -> dict[tuple, str]:
    """Find each specimen's tests and mint their labels; return test key -> test id."""
    test_id_of: dict[tuple, str] = {}
    records = []
    for key in sorted(specimens):
        ref, name = key
        specimen_id = f'{ref}|{label_of[key]}'
        tests: dict[tuple, list[dict]] = defaultdict(list)
        for row in specimens[key]:
            tests[test_key(row)].append(row)

        order_of: dict[tuple, int | None] = {}
        for tkey, rows in tests.items():
            parsed = _parse_sequence(tkey[-1])
            if parsed == 'invalid':
                split.errors.append(
                    Problem(
                        'test.invalid_sequence',
                        reference=ref,
                        specimen=name,
                        test=_test_text(tkey),
                        values=_values(rows, 'specimen_inspection_sequence'),
                    )
                )
                parsed = None
            order_of[tkey] = parsed
        # A test_order may appear once per specimen, compared as an integer.
        by_order: dict[int, list[tuple]] = defaultdict(list)
        for tkey, order in order_of.items():
            if order is not None:
                by_order[order].append(tkey)
        for order, tkeys in sorted(by_order.items()):
            if len(tkeys) > 1:
                rows = [r for t in tkeys for r in tests[t]]
                split.errors.append(
                    Problem(
                        'test.duplicate_order',
                        reference=ref,
                        specimen=name,
                        test='; '.join(sorted(_test_text(t) for t in tkeys)),
                        detail=f'test_order {order}',
                        values=_values(rows, 'specimen_inspection_sequence'),
                    )
                )

        letters = 0
        minted = []
        for tkey, order in sorted(order_of.items(), key=_test_sort_key):
            if order is not None:
                label = str(order)
            else:
                label = letter_label(letters)
                letters += 1
            minted.append((label, order))
            test_id_of[tkey] = f'{specimen_id}|{label}'
            records.append({
                'specimen': specimen_id,
                'label': label,
                'test_order': order,
                'test_type': tkey[2],
                'loading_protocol': tkey[3],
                'peak_test_amplitude': tkey[4],
                # Nothing migrates into these (decision 7).
                'prior_damage': '',
                'prior_damage_repaired': '',
                'notes': '',
            })
        if len(minted) > 1:
            split.multi_test[specimen_id] = minted
    split.tables['test.json'] = sorted(
        records, key=lambda t: (t['specimen'], t['label'].casefold(), t['label'])
    )
    return test_id_of


def _observations(
    rows: list[dict], test_id_of: dict[tuple, str], split: Split
) -> None:
    """Set each observation's test and its zero-padded position within the test."""
    by_test: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if test_key(row) in test_id_of:
            by_test[test_id_of[test_key(row)]].append(row)
    label_of: dict[str, str] = {}
    for members in by_test.values():
        # Today's display order: ds_rank (nulls last), edp_value (nulls last), id.
        members.sort(
            key=lambda r: (
                r['ds_rank'] is None,
                r['ds_rank'] or 0,
                r['edp_value'] is None,
                r['edp_value'] or 0,
                r['id'],
            )
        )
        width = max(2, len(str(len(members))))
        for position, row in enumerate(members, start=1):
            label_of[row['id']] = str(position).zfill(width)
    # Keep every key, value and the record order; only test and label are set.
    split.tables['observation.json'] = [
        {
            **row,
            'test': test_id_of.get(test_key(row)),
            'label': label_of.get(row['id'], ''),
        }
        for row in rows
    ]


def split_rows(rows: list[dict], accepted: list[dict]) -> Split:
    """Apply every Stage 6 rule to the flat rows. Pure: no I/O."""
    split = Split(rows_in=len(rows))
    _programs(rows, split)

    blank: dict[str, list[dict]] = defaultdict(list)
    specimens: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = specimen_key(row)
        if key[1] == '':
            blank[key[0]].append(row)
        else:
            specimens[key].append(row)
    for ref, brows in sorted(blank.items()):
        split.errors.append(
            Problem(
                'specimen.blank', reference=ref, values=_values(brows, 'specimen')
            )
        )

    chosen = _accepted_values(accepted, specimens, split)
    facility_of = _facilities(specimens, split)
    label_of = _specimens(specimens, facility_of, chosen, split)
    test_id_of = _tests(specimens, label_of, split)
    _observations(rows, test_id_of, split)
    return split


def to_json(data: list[dict]) -> str:
    """Serialize records exactly as ``export_data`` does (no trailing newline)."""
    return json.dumps(data, indent=4, sort_keys=True)


def render_report(split: Split, check: bool) -> str:
    """Return the Markdown report."""
    out = ['# Observation split report', '']
    if split.errors:
        status = f'{len(split.errors)} errors; no data written'
    else:
        status = 'no errors' + ('; --check, so no data written' if check else '')
    out += [f'Result: {status}.', '']

    out += ['## Errors', '']
    if not split.errors:
        out.append('None.')
    for p in split.errors:
        where = ', '.join(
            f'{name} `{value}`'
            for name, value in (
                ('reference', p.reference),
                ('specimen', p.specimen),
                ('test', p.test),
            )
            if value
        )
        line = f'- **{p.rule}**: {RULES[p.rule]}'
        line += f'; {where}' if where else ''
        line += f' ({p.detail})' if p.detail else ''
        out.append(line)
        for value, ids in p.values:
            out.append(f'  - {value}: {", ".join(ids)}')

    t = split.tables
    out += ['', '## Summary', '', '| Quantity | Count |', '|---|---|']
    out += [
        f'| Rows in | {split.rows_in} |',
        f'| Facilities out | {len(t["facility.json"])} |',
        f'| Programs out | {len(t["program.json"])} |',
        f'| Specimens out | {len(t["specimen.json"])} |',
        f'| Tests out | {len(t["test.json"])} |',
        f'| Observations out | {len(t["observation.json"])} |',
    ]

    out += ['', '## Facilities', '', '| Label | Location | Specimens |']
    out.append('|---|---|---|')
    for label, (loc, count) in split.facilities.items():
        out.append(f'| `{label}` | {loc} | {count} |')
    out += ['', '### References spanning several facilities', '']
    if not split.multi_facility_refs:
        out.append('None.')
    for ref, labels in split.multi_facility_refs.items():
        out.append(f'- `{ref}`: {", ".join(f"`{lbl}`" for lbl in labels)}')

    out += ['', '## Tests', '', '### Minted labels of multi-test specimens', '']
    if not split.multi_test:
        out.append('None.')
    for spec_id, minted in split.multi_test.items():
        labels = ', '.join(lbl for lbl, _ in minted)
        out.append(f'- `{spec_id}`: {labels}')
    unordered = [
        s
        for s, minted in split.multi_test.items()
        if all(o is None for _, o in minted)
    ]
    out += [
        '',
        f'### Multi-test specimens with no test_order ({len(unordered)})',
        '',
    ]
    out += [f'- `{s}`' for s in unordered] or ['None.']

    out += ['', '## Accepted collapses applied', '']
    if not split.applied:
        out.append('None.')
    for entry, overridden, value in split.applied:
        out.append(
            f'- `{entry["reference"]}` | `{entry["specimen"]}` | {entry["field"]}: '
            f'{json.dumps(value, ensure_ascii=False)} '
            f'(reason: {entry.get("reason", "")})'
        )
        out.append(f'  - overrides {len(overridden)} cells: {", ".join(overridden)}')
    return '\n'.join(out) + '\n'


def convert(input_dir: Path, accepted: Path, output: Path, check: bool) -> int:
    """Run the conversion; return the exit status (0 ok, 1 errors, 2 usage)."""
    if output.exists() and (
        not output.is_dir() or {p.name for p in output.iterdir()} - {REPORT}
    ):
        print(
            f'{output} must be new or empty (apart from {REPORT})', file=sys.stderr
        )
        return 2
    rows = json.loads((input_dir / 'observation.json').read_text(encoding='utf-8'))
    split = split_rows(rows, load_accepted(accepted))

    output.mkdir(parents=True, exist_ok=True)
    report = render_report(split, check)
    (output / REPORT).write_bytes(report.encode('utf-8'))
    if not split.errors and not check:
        for name in DATA_FILES:
            (output / name).write_bytes(to_json(split.tables[name]).encode('utf-8'))

    counts = ', '.join(
        f'{len(split.tables[n])} {n.removesuffix(".json")}' for n in DATA_FILES
    )
    print(f'{split.rows_in} rows in; {counts}; {len(split.errors)} errors')
    print(f'Report: {output / REPORT}')
    return 1 if split.errors else 0


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and run the conversion."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    cmd = commands.add_parser('convert', help='convert the flat observation data')
    cmd.add_argument('--input', type=Path, required=True, help='flat data directory')
    cmd.add_argument(
        '--accepted',
        type=Path,
        required=True,
        help='accepted-collapses file (missing = no entries)',
    )
    cmd.add_argument(
        '--output',
        type=Path,
        required=True,
        help=f'new or empty directory (an old {REPORT} may remain)',
    )
    cmd.add_argument(
        '--check', action='store_true', help='validate and write the report only'
    )
    args = parser.parse_args(argv)
    return convert(args.input, args.accepted, args.output, args.check)


if __name__ == '__main__':
    sys.exit(main())
