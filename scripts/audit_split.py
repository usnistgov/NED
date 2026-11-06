r"""Audit the Experiment split by rebuilding the flat records from the hierarchy.

The reconstruction audit of the Experiment split (steps doc, Stage 7; design
AC5). It joins every observation to its test, specimen, program and facility,
rebuilds one flat record per observation in the pre-split shape from an explicit
field -> home map, and compares the result with the frozen snapshot of the flat
``observation.json``. The audit passes only if the cells that differ are exactly
the ones the accepted-collapses file predicts, and every observation joins and
matches exactly one snapshot record.

Two modes:

- ``--normalized <dir>`` reads ``facility.json``, ``program.json``,
  ``specimen.json``, ``test.json`` and ``observation.json`` from ``<dir>``, and
  so checks the conversion;
- ``--database`` reads the ingested database through the ORM, and so checks
  ingest. It uses ``db.sqlite3``, or the SQLite file named by the
  ``NED_AUDIT_DATABASE`` environment variable. Django is set up only here.

Observations are matched to the snapshot by their old ``id`` while they carry
one, and through the id map (old id -> ``observation_id``) once they don't
(Stage 10). The choice follows the data's shape, never whether the map exists.

The audit is independent of the conversion tool: it never imports
``split_observations`` and keeps its own sequence parser. It prints a Markdown
report and exits 0 on pass, 1 on fail, 2 if an input can't be read.

Usage (run from the repository root):

    python scripts/audit_split.py --normalized build/split \
        --snapshot resources/archive/observation_pre_split.json
    python scripts/audit_split.py --database
    NED_AUDIT_DATABASE=/tmp/scratch.sqlite3 python scripts/audit_split.py --database
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from measure_split_inputs import load_accepted, normalize

NED = Path(__file__).resolve().parent.parent
ARCHIVE = NED / 'resources' / 'archive'
DEFAULT_SNAPSHOT = ARCHIVE / 'observation_pre_split.json'
DEFAULT_ACCEPTED = ARCHIVE / 'split_accepted_collapses.json'
DEFAULT_ID_MAP = ARCHIVE / 'observation_id_map.json'
DATABASE_ENV = 'NED_AUDIT_DATABASE'

TABLES = ('facility', 'program', 'specimen', 'test', 'observation')

# Specimen-grain columns, stored on Specimen under the same name.
SPECIMEN_FIELDS = (
    'contributor',
    'component',
    'comp_detail',
    'material',
    'size_class',
    'design_objective',
    'governing_design_standard',
    'comp_description',
)
TEST_FIELDS = ('test_type', 'loading_protocol', 'peak_test_amplitude')
# Kept on Observation, renamed legacy_<name> at the cutover (decisions 7 and 8).
# Never read from Test.prior_damage*, which start blank by design.
LEGACY_FIELDS = ('ds_rank', 'prior_damage', 'prior_damage_repaired')
OBSERVATION_FIELDS = (
    'ds_description',
    'ds_class',
    'edp_metric',
    'edp_unit',
    'edp_value',
    'alt_edp_metric',
    'alt_edp_unit',
    'alt_edp_value',
    'notes',
    'damage_location',
)

# Where each pre-split field is rebuilt from, as (table, column). Two homes are
# rules rather than columns: 'effective_reference' (Specimen.reference, else
# Program.reference) and 'legacy' (the Observation column, current or legacy_
# name). Every snapshot key except SKIPPED must appear here.
FIELD_HOME: dict[str, tuple[str, str]] = {
    'specimen': ('specimen', 'name'),
    **{f: ('specimen', f) for f in SPECIMEN_FIELDS},
    **{f: ('test', f) for f in TEST_FIELDS},
    'specimen_inspection_sequence': ('test', 'test_order'),
    'reference': ('effective_reference', ''),
    'location': ('facility', 'location'),
    **{f: ('legacy', f) for f in LEGACY_FIELDS},
    **{f: ('observation', f) for f in OBSERVATION_FIELDS},
}
# The match key, and the two fields the split fills by design (the snapshot
# holds Stage 5's placeholders for them).
SKIPPED = frozenset({'id', 'test', 'label'})

LIMIT = 50  # lines listed per report section


class _Missing:
    """A rebuilt cell whose home holds no such column."""

    def __repr__(self) -> str:
        return '<missing>'


MISSING = _Missing()


def parse_sequence(value: object) -> object:
    """Parse a snapshot sequence as the integer Test.test_order holds.

    ``''`` gives None, and ``'7'`` and ``'7.0'`` give 7. Anything else (not a
    positive whole number) comes back unchanged, so it never equals a test_order.
    """
    if value == '' or value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() and number > 0 else value


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def same(a: object, b: object) -> bool:
    """Compare two cells raw: numbers as numbers, everything else by type and value."""
    if _is_number(a) and _is_number(b):
        return a == b
    return type(a) is type(b) and a == b


def derived_ids(tables: dict[str, list[dict]]) -> dict[str, list[str | None]]:
    """Derive every record's id, as ingest does (design §2.1); None if it can't."""

    def join(parent: object, label: object) -> str | None:
        if not isinstance(parent, str) or not isinstance(label, str):
            return None
        return f'{parent}|{label}'

    return {
        'facility': [r.get('label') for r in tables['facility']],
        'program': [r.get('label') or r.get('reference') for r in tables['program']],
        'specimen': [
            join(r.get('program'), r.get('label')) for r in tables['specimen']
        ],
        'test': [join(r.get('specimen'), r.get('label')) for r in tables['test']],
        'observation': [
            join(r.get('test'), r.get('label')) for r in tables['observation']
        ],
    }


def matches_by_id_map(observations: list[dict]) -> bool:
    """True once observations no longer carry their old ``id`` (Stage 10)."""
    return any('id' not in o for o in observations)


def expected_differences(
    snapshot: list[dict], accepted: list[dict]
) -> tuple[set[tuple], list[str]]:
    """Compute the differences the accepted-collapses file predicts.

    For each entry, every snapshot cell in its group and field whose value isn't
    the entry's ``value``, as ``(old id, field, value)`` with the value the
    rebuilt cell must hold. Uses the snapshot and the file only. Also returns the
    entries that match no snapshot group.
    """
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in snapshot:
        groups[
            row.get('reference'), normalize('specimen', row.get('specimen'))
        ].append(row)
    expected: set[tuple] = set()
    unmatched = []
    for entry in accepted:
        key = (entry['reference'], normalize('specimen', entry['specimen']))
        fld, value = entry['field'], entry['value']
        rows = groups.get(key, [])
        if not rows or fld not in rows[0]:
            unmatched.append(f'`{key[0]}` | `{key[1]}` | {fld}')
            continue
        expected |= {(r['id'], fld, value) for r in rows if not same(r[fld], value)}
    return expected, unmatched


@dataclass
class Audit:
    """The audit's findings. It passes only if every failure list is empty."""

    matched_by: str = 'old id'
    snapshot_records: int = 0
    rebuilt_records: int = 0
    errors: list[str] = field(default_factory=list)
    unmapped_fields: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    unjoined: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    matched_twice: list[str] = field(default_factory=list)
    unmatched_entries: list[str] = field(default_factory=list)
    expected: set[tuple] = field(default_factory=set)
    actual: set[tuple] = field(default_factory=set)
    # (old id, field) -> snapshot value, for every differing cell
    was: dict[tuple, object] = field(default_factory=dict)

    @property
    def unexpected(self) -> set[tuple]:
        """Differences the accepted-collapses file doesn't predict."""
        return self.actual - self.expected

    @property
    def unmaterialized(self) -> set[tuple]:
        """Predicted differences that the rebuilt records don't show."""
        return self.expected - self.actual

    @property
    def failures(self) -> dict[str, list[str]]:
        """Every failure, by report section title."""
        return {
            'Errors': self.errors,
            # An empty snapshot would otherwise pass with nothing compared.
            'Empty snapshot': [] if self.snapshot_records else ['no records'],
            'Snapshot fields with no home': self.unmapped_fields,
            'Derived ids duplicated (ignoring case)': self.duplicate_ids,
            'Observations that do not join': self.unjoined,
            'Snapshot records with no rebuilt record': self.missing,
            'Rebuilt records with no snapshot record': self.unmatched,
            'Snapshot records matched more than once': self.matched_twice,
            'Accepted entries matching no snapshot group': self.unmatched_entries,
            'Unexpected differences': [
                self._diff_line(d) for d in sorted(self.unexpected, key=_sort_key)
            ],
            'Expected differences that did not materialize': [
                f'`{i}` {f}: expected {_show(v)}'
                for i, f, v in sorted(self.unmaterialized, key=_sort_key)
            ],
        }

    @property
    def passed(self) -> bool:
        return not any(self.failures.values())

    def _diff_line(self, diff: tuple) -> str:
        old_id, fld, value = diff
        was = _show(self.was[old_id, fld])
        return f'`{old_id}` {fld}: snapshot {was}, rebuilt {_show(value)}'


def _sort_key(diff: tuple) -> tuple:
    return (str(diff[0]), diff[1], repr(diff[2]))


def _show(value: object) -> str:
    if value is MISSING:
        return repr(value)
    return json.dumps(value, ensure_ascii=False)


def _rebuild(
    obs: dict, test: dict, specimen: dict, program: dict, facility: dict
) -> dict:
    """Rebuild one flat record from its joined rows, through FIELD_HOME only."""
    source = {
        'observation': obs,
        'test': test,
        'specimen': specimen,
        'facility': facility,
    }
    record = {}
    for fld, (table, column) in FIELD_HOME.items():
        if table == 'effective_reference':
            record[fld] = specimen.get('reference') or program.get(
                'reference', MISSING
            )
        elif table == 'legacy':
            legacy = f'legacy_{column}'
            record[fld] = obs[legacy] if legacy in obs else obs.get(column, MISSING)
        else:
            record[fld] = source[table].get(column, MISSING)
    return record


def _index(records: list[dict], ids: list[str | None]) -> dict[str, dict]:
    """Index records by derived id (first wins; duplicates are reported apart)."""
    index: dict[str, dict] = {}
    for record, rid in zip(records, ids):
        if rid is not None:
            index.setdefault(rid, record)
    return index


def audit(
    tables: dict[str, list[dict]],
    snapshot: list[dict],
    accepted: list[dict],
    id_map: dict[str, str] | None = None,
) -> Audit:
    """Rebuild the flat records and compare them with the snapshot. Pure: no I/O."""
    result = Audit(snapshot_records=len(snapshot))

    # 1. The field -> home map must cover every snapshot key.
    keys = {k for row in snapshot for k in row}
    result.unmapped_fields = sorted(keys - SKIPPED - set(FIELD_HOME))

    # 4. Derived ids must be unique, ignoring case.
    ids = derived_ids(tables)
    for table in TABLES:
        seen: dict[str, list[str]] = defaultdict(list)
        for rid in ids[table]:
            if rid is not None:
                seen[rid.lower()].append(rid)
        result.duplicate_ids += [
            f'{table} {", ".join(f"`{r}`" for r in sorted(group))}'
            for _, group in sorted(seen.items())
            if len(group) > 1
        ]

    # 2. Match by old id while observations carry it, else through the id map.
    observations = tables['observation']
    old_id_of: dict[str, str] = {}
    if matches_by_id_map(observations):
        result.matched_by = 'id map'
        if id_map is None:
            result.errors.append(
                'observations carry no old `id`, so they must be matched through '
                'the id map, but none was found'
            )
            id_map = {}
        old_id_of = {new: old for old, new in id_map.items()}

    facilities = _index(tables['facility'], ids['facility'])
    programs = _index(tables['program'], ids['program'])
    specimens = _index(tables['specimen'], ids['specimen'])
    tests = _index(tables['test'], ids['test'])

    rebuilt: dict[str, dict] = {}
    for obs, obs_id in zip(observations, ids['observation']):
        name = f'`{obs["id"]}`' if 'id' in obs else f'`{obs_id}`'
        # Observation -> Test -> Specimen -> {Program, Facility}, by exact id.
        test = tests.get(obs.get('test'))
        specimen = specimens.get(test.get('specimen')) if test else None
        program = programs.get(specimen.get('program')) if specimen else None
        facility = facilities.get(specimen.get('facility')) if specimen else None
        if test is None:
            broken = f'test `{obs.get("test")}`'
        elif specimen is None:
            broken = f'specimen `{test.get("specimen")}`'
        elif program is None:
            broken = f'program `{specimen.get("program")}`'
        elif facility is None:
            broken = f'facility `{specimen.get("facility")}`'
        else:
            broken = None
        if broken:
            result.unjoined.append(f'{name}: {broken} not found')
            continue
        old_id = obs['id'] if 'id' in obs else old_id_of.get(obs_id)
        if old_id is None:
            result.unmatched.append(f'{name}: not in the id map')
            continue
        if old_id in rebuilt:
            result.matched_twice.append(f'`{old_id}`')
            continue
        rebuilt[old_id] = _rebuild(obs, test, specimen, program, facility)
    result.rebuilt_records = len(rebuilt)

    # 3 and 4. Compare cell by cell with the snapshot.
    snapshot_ids = set()
    for row in snapshot:
        old_id = row['id']
        snapshot_ids.add(old_id)
        record = rebuilt.get(old_id)
        if record is None:
            result.missing.append(f'`{old_id}`')
            continue
        for fld, was in row.items():
            if fld in SKIPPED or fld not in FIELD_HOME:
                continue
            now = record[fld]
            if fld == 'specimen_inspection_sequence':
                differs = not same(parse_sequence(was), now)
            else:
                differs = not same(was, now)
            if differs:
                result.actual.add((old_id, fld, now))
                result.was[old_id, fld] = was
    result.unmatched += [
        f'`{old_id}`: not in the snapshot'
        for old_id in rebuilt
        if old_id not in snapshot_ids
    ]
    result.expected, result.unmatched_entries = expected_differences(
        snapshot, accepted
    )
    return result


def render(result: Audit, source: str, snapshot: Path, accepted: Path) -> str:
    """Return the audit as a Markdown report."""
    failures = result.failures
    out = ['# Split reconstruction audit', '']
    out.append(f'Result: **{"PASS" if result.passed else "FAIL"}**.')
    out += [
        '',
        f'- Source: {source}',
        f'- Snapshot: `{snapshot}`',
        f'- Accepted collapses: `{accepted}`',
        f'- Matched by: {result.matched_by}',
        '',
        '## Summary',
        '',
        '| Quantity | Count |',
        '|---|---|',
        f'| Snapshot records | {result.snapshot_records} |',
        f'| Rebuilt records | {result.rebuilt_records} |',
        f'| Expected differences | {len(result.expected)} |',
        f'| Actual differences | {len(result.actual)} |',
    ]
    out += [f'| {title} | {len(lines)} |' for title, lines in failures.items()]
    for title, lines in failures.items():
        if not lines:
            continue
        out += ['', f'## {title} ({len(lines)})', '']
        out += [f'- {line}' for line in lines[:LIMIT]]
        if len(lines) > LIMIT:
            out.append(f'- ... {len(lines) - LIMIT} more')
    out += ['', '## Expected differences', '']
    out += [
        f'- `{i}` {f}: {_show(v)}'
        for i, f, v in sorted(result.expected, key=_sort_key)
    ] or ['None.']
    return '\n'.join(out) + '\n'


def load_normalized(directory: Path) -> dict[str, list[dict]]:
    """Read the five hierarchy files the conversion writes."""
    return {
        table: json.loads((directory / f'{table}.json').read_text(encoding='utf-8'))
        for table in TABLES
    }


def load_database() -> dict[str, list[dict]]:
    """Read the five hierarchy tables through the ORM, shaped like the JSON files.

    Each record maps field names to stored values: a foreign key gives the
    string it holds (the parent's derived id), a decimal gives a float, as
    ``export_data`` writes them. An integer primary key is left out, so a record
    carries ``id`` only while the primary key is the old string id.
    """
    from ned_app.models import Facility, Observation, Program, Specimen, Test

    models = dict(zip(TABLES, (Facility, Program, Specimen, Test, Observation)))
    tables = {}
    for table, model in models.items():
        fields = [
            f
            for f in model._meta.concrete_fields
            if not (f.primary_key and f.get_internal_type().endswith('AutoField'))
        ]
        rows = model.objects.order_by('pk').values(*(f.attname for f in fields))
        tables[table] = [
            {
                f.name: float(v) if isinstance(v := row[f.attname], Decimal) else v
                for f in fields
            }
            for row in rows
        ]
    return tables


def _setup_django() -> str:
    """Set up Django for ``--database``; return a description of the database."""
    if str(NED) not in sys.path:
        sys.path.insert(0, str(NED))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ned_proj.settings')
    import django
    from django.apps import apps
    from django.conf import settings

    if not apps.ready:  # already set up when run from the test suite
        override = os.environ.get(DATABASE_ENV)
        if override:
            settings.DATABASES['default']['NAME'] = override
        name = Path(settings.DATABASES['default']['NAME'])
        if not name.is_file():
            raise FileNotFoundError(f'no database at {name}')
    django.setup()
    return f'database `{settings.DATABASES["default"]["NAME"]}`'


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding='utf-8'))


def main(argv: list[str] | None = None) -> int:
    """Parse the command line, run the audit and print the report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        '--normalized', type=Path, metavar='DIR', help='converted JSON directory'
    )
    mode.add_argument(
        '--database',
        action='store_true',
        help=f'the ingested database (db.sqlite3, or ${DATABASE_ENV})',
    )
    parser.add_argument('--snapshot', type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument(
        '--accepted',
        type=Path,
        default=DEFAULT_ACCEPTED,
        help='accepted-collapses file (missing = no entries)',
    )
    parser.add_argument(
        '--id-map',
        type=Path,
        default=DEFAULT_ID_MAP,
        help='old id -> observation_id, used once observations have no id',
    )
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='backslashreplace')

    try:
        snapshot = _read_json(args.snapshot)
        accepted = load_accepted(args.accepted)
        if args.database:
            source = _setup_django()
            tables = load_database()
        else:
            source = f'normalized `{args.normalized}`'
            tables = load_normalized(args.normalized)
        id_map = None
        if matches_by_id_map(tables['observation']) and args.id_map.exists():
            id_map = _read_json(args.id_map)
    except (OSError, ValueError) as exc:
        print(f'Cannot read the audit inputs: {exc}', file=sys.stderr)
        return 2

    result = audit(tables, snapshot, accepted, id_map)
    print(render(result, source, args.snapshot, args.accepted), end='')
    return 0 if result.passed else 1


if __name__ == '__main__':
    sys.exit(main())
