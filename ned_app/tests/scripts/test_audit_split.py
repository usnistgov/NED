"""
Unit tests for scripts/audit_split.py, the Experiment-split reconstruction audit.

Each test builds its own small flat fixture (shaped like Stage 5's
observation.json), converts it with Stage 6's tool, optionally tampers with the
result, and audits it against the fixture as the snapshot. The cases run in both
modes: normalized (the converted JSON) and database (the same JSON ingested into
the test database). The audit itself never imports the conversion tool; only
these tests do, to produce its input.
"""

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

SCRIPTS = Path(__file__).resolve().parents[3] / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import audit_split
import split_observations

from ned_app.models import Specimen, derive_reference_id

DATA = Path(__file__).resolve().parents[3] / 'resources' / 'data'
REF = 'Smith-2020'
COMPONENT = 'B.20.1.1.A'
LEGACY = ('ds_rank', 'prior_damage', 'prior_damage_repaired')
TABLE_FILES = ('facility', 'program', 'specimen', 'test', 'observation')


def row(id, specimen='S1', reference=REF, component=COMPONENT, **overrides):
    """Return one flat observation row with Stage 5's placeholders (valid choices)."""
    base = {
        'id': id,
        'reference': reference,
        'specimen': specimen,
        'specimen_inspection_sequence': '',
        'contributor': 'NIST',
        'component': component,
        'comp_detail': 'Detail',
        'material': 'Steel',
        'size_class': 'Full',
        'design_objective': '',
        'governing_design_standard': '',
        'comp_description': 'Line one\nLine two',
        'location': 'UCSD, California',
        'test_type': 'Quasi-static Cyclic, uniaxial',
        'loading_protocol': 'FEMA 461',
        'peak_test_amplitude': '3% drift',
        'ds_description': 'Cracking',
        'ds_class': 'Inconsequential',
        'ds_rank': None,
        'edp_metric': 'Story Drift Ratio',
        'edp_unit': 'Ratio',
        'edp_value': 0.01,
        'alt_edp_metric': '',
        'alt_edp_unit': '',
        'alt_edp_value': None,
        'prior_damage': '',
        'prior_damage_repaired': '',
        'notes': '',
        'test': None,
        'label': '',
        'damage_location': '',
    }
    base.update(overrides)
    return base


def clean_rows(ref=REF, component=COMPONENT):
    """Two specimens: S1 with tests 7 and 12 (sequences '7.0' and '12'), and
    'Spec 2' (blank location) with unordered tests a (e4) and b (e5, e6)."""

    def r(id, **kw):
        return row(id, reference=ref, component=component, **kw)

    return [
        r('e1', specimen_inspection_sequence='7.0'),
        r('e2', specimen_inspection_sequence='7.0', edp_value=0.02, ds_rank=1),
        r(
            'e3',
            specimen_inspection_sequence='12',
            peak_test_amplitude='4% drift',
            edp_value=0.03,
            prior_damage='Cracks',
            prior_damage_repaired='No',
        ),
        r('e4', specimen='Spec 2', location='', edp_value=0.015),
        r(
            'e5',
            specimen='Spec 2',
            location='',
            peak_test_amplitude='5% drift',
            edp_value=0.025,
            alt_edp_metric='Story Drift Ratio',
            alt_edp_unit='Ratio',
            alt_edp_value=0.5,
            notes='A note',
        ),
        r(
            'e6',
            specimen='Spec 2',
            location='',
            peak_test_amplitude='5% drift',
            edp_value=0.035,
            ds_rank=2,
        ),
    ]


def quiet():
    """Silence stdout and stderr."""
    stack = contextlib.ExitStack()
    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
    stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
    return stack


def write_json(path, data):
    """Write ASCII JSON (ingest opens files with the platform encoding)."""
    path.write_text(json.dumps(data), encoding='ascii')


def convert(tmp, rows, accepted=()):
    """Convert ``rows`` with Stage 6's tool; return the output directory."""
    (tmp / 'input').mkdir(parents=True, exist_ok=True)
    write_json(tmp / 'input' / 'observation.json', rows)
    accepted_path = tmp / 'convert_accepted.json'
    write_json(accepted_path, list(accepted))
    with quiet():
        status = split_observations.convert(
            tmp / 'input', accepted_path, tmp / 'split', check=False
        )
    assert status == 0, (tmp / 'split' / 'report.md').read_text('utf-8')
    return tmp / 'split'


def edit_tables(directory, edit):
    """Apply ``edit`` to the converted JSON tables in place."""
    tables = audit_split.load_normalized(directory)
    edit(tables)
    for name in TABLE_FILES:
        write_json(directory / f'{name}.json', tables[name])


def entry(ref, value, field='material', specimen='S1'):
    """Return one accepted-collapses entry."""
    return {
        'reference': ref,
        'specimen': specimen,
        'field': field,
        'value': value,
        'reason': 'test',
    }


def by_id(tables, old_id):
    """Return the observation record with the old id."""
    return next(o for o in tables['observation'] if o['id'] == old_id)


def duplicate(table, *ids):
    """Return the report line for derived ids duplicated in ``table``."""
    return f'{table} {", ".join(f"`{i}`" for i in sorted(ids))}'


def rename_test(old, new):
    """Return an edit relabelling a test, in test.json and its observations."""

    def edit(tables):
        for test in tables['test']:
            if f'{test["specimen"]}|{test["label"]}' == old:
                test['label'] = new.rsplit('|', 1)[1]
        for obs in tables['observation']:
            if obs['test'] == old:
                obs['test'] = new

    return edit


def to_legacy_names(tables):
    """Rename the kept Observation columns as the Stage 12 cutover will."""
    for obs in tables['observation']:
        for name in LEGACY:
            obs[f'legacy_{name}'] = obs.pop(name)


def to_observation_ids(tables):
    """Drop the old ids as Stage 10 will; return the id map it writes."""
    return {
        obs.pop('id'): f'{obs["test"]}|{obs["label"]}'
        for obs in tables['observation']
    }


class AuditCases:
    """The cases every mode must handle. ``run_audit`` is defined per mode."""

    ref = REF
    component = COMPONENT

    def rows(self):
        return clean_rows(self.ref, self.component)

    def run_audit(
        self,
        rows,
        *,
        convert_accepted=(),
        audit_accepted=None,
        edit=None,
        after=None,
        snapshot=None,
    ):
        """Convert, edit, load (and ``after`` the loaded tables), then audit.

        ``after`` may return an id map, used to audit.
        """
        raise NotImplementedError

    def audit_loaded(self, tables, rows, after, accepted, snapshot):
        id_map = after(tables) if after else None
        return audit_split.audit(
            tables, rows if snapshot is None else snapshot, list(accepted), id_map
        )

    def test_clean_pass(self):
        result = self.run_audit(self.rows())
        self.assertTrue(result.passed, result.failures)
        self.assertEqual(result.rebuilt_records, 6)
        self.assertEqual(result.actual, set())
        self.assertEqual(result.matched_by, 'old id')

    def test_accepted_collapse_that_materializes(self):
        rows = self.rows()
        rows[1]['material'] = 'Aluminum'
        accepted = [entry(self.ref, 'Steel')]
        result = self.run_audit(rows, convert_accepted=accepted)
        self.assertTrue(result.passed, result.failures)
        self.assertEqual(result.expected, {('e2', 'material', 'Steel')})
        self.assertEqual(result.actual, result.expected)

    def test_accepted_collapse_that_does_not_materialize(self):
        rows = self.rows()
        rows[1]['material'] = 'Aluminum'
        # The conversion applied a different choice than the file the audit reads.
        result = self.run_audit(
            rows,
            convert_accepted=[entry(self.ref, 'Aluminum')],
            audit_accepted=[entry(self.ref, 'Steel')],
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.unmaterialized, {('e2', 'material', 'Steel')})
        self.assertEqual(
            result.unexpected,
            {('e1', 'material', 'Aluminum'), ('e3', 'material', 'Aluminum')},
        )

    def test_accepted_entry_on_clean_data_does_not_materialize(self):
        result = self.run_audit(
            self.rows(), audit_accepted=[entry(self.ref, 'Aluminum')]
        )
        self.assertFalse(result.passed)
        self.assertEqual(
            result.unmaterialized,
            {(i, 'material', 'Aluminum') for i in ('e1', 'e2', 'e3')},
        )

    def test_tampered_observation_cell_fails(self):
        def edit(tables):
            by_id(tables, 'e1')['ds_description'] = 'Tampered'

        result = self.run_audit(self.rows(), edit=edit)
        self.assertFalse(result.passed)
        self.assertEqual(result.unexpected, {('e1', 'ds_description', 'Tampered')})

    def test_tampered_parent_cells_fail(self):
        # The moved columns are still on Observation, unchanged; the audit must
        # read Specimen and Test, not pass them against themselves.
        ref = self.ref

        def edit(tables):
            for specimen in tables['specimen']:
                if specimen['label'] == 'S1':
                    specimen['material'] = 'Tampered'
            for test in tables['test']:
                if test['specimen'] == f'{ref}|S1' and test['label'] == '12':
                    test['test_order'] = 13

        result = self.run_audit(self.rows(), edit=edit)
        self.assertFalse(result.passed)
        self.assertEqual(
            result.unexpected,
            {(i, 'material', 'Tampered') for i in ('e1', 'e2', 'e3')}
            | {('e3', 'specimen_inspection_sequence', 13)},
        )

    def test_missing_observation_fails(self):
        def edit(tables):
            tables['observation'] = [
                o for o in tables['observation'] if o['id'] != 'e6'
            ]

        result = self.run_audit(self.rows(), edit=edit)
        self.assertFalse(result.passed)
        self.assertEqual(result.missing, ['`e6`'])

    def test_observation_not_in_snapshot_fails(self):
        rows = self.rows()
        result = self.run_audit(rows, snapshot=rows[:-1])
        self.assertFalse(result.passed)
        self.assertEqual(result.unmatched, ['`e6`: not in the snapshot'])

    def test_duplicated_observation_label_fails(self):
        ref = self.ref
        for first, second in (('01', '01'), ('x', 'X')):
            with self.subTest(labels=(first, second)):

                def edit(tables, first=first, second=second):
                    by_id(tables, 'e5')['label'] = first
                    by_id(tables, 'e6')['label'] = second

                result = self.run_audit(self.rows(), edit=edit)
                self.assertFalse(result.passed)
                self.assertEqual(
                    result.duplicate_ids,
                    [
                        duplicate(
                            'observation',
                            f'{ref}|Spec_2|b|{first}',
                            f'{ref}|Spec_2|b|{second}',
                        )
                    ],
                )

    def test_legacy_field_names(self):
        result = self.run_audit(self.rows(), after=to_legacy_names)
        self.assertTrue(result.passed, result.failures)

    def test_legacy_field_value_is_compared(self):
        def after(tables):
            to_legacy_names(tables)
            by_id(tables, 'e3')['legacy_prior_damage'] = 'Changed'

        result = self.run_audit(self.rows(), after=after)
        self.assertFalse(result.passed)
        self.assertEqual(result.unexpected, {('e3', 'prior_damage', 'Changed')})

    def test_matching_through_an_id_map(self):
        result = self.run_audit(self.rows(), after=to_observation_ids)
        self.assertTrue(result.passed, result.failures)
        self.assertEqual(result.matched_by, 'id map')
        self.assertEqual(result.rebuilt_records, 6)

    def test_wrong_id_map_fails(self):
        def after(tables):
            id_map = to_observation_ids(tables)
            id_map['e1'], id_map['e2'] = id_map['e2'], id_map['e1']
            return id_map

        result = self.run_audit(self.rows(), after=after)
        self.assertFalse(result.passed)
        self.assertEqual(
            {(i, f) for i, f, _ in result.unexpected},
            {
                ('e1', 'edp_value'),
                ('e1', 'ds_rank'),
                ('e2', 'edp_value'),
                ('e2', 'ds_rank'),
            },
        )

    def test_no_id_map_fails(self):
        def after(tables):
            to_observation_ids(tables)

        result = self.run_audit(self.rows(), after=after)
        self.assertFalse(result.passed)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.unmatched), 6)
        self.assertEqual(len(result.missing), 6)


class NormalizedAuditTests(AuditCases, SimpleTestCase):
    def run_audit(
        self,
        rows,
        *,
        convert_accepted=(),
        audit_accepted=None,
        edit=None,
        after=None,
        snapshot=None,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            split = convert(Path(tmp), rows, convert_accepted)
            if edit:
                edit_tables(split, edit)
            tables = audit_split.load_normalized(split)
        accepted = convert_accepted if audit_accepted is None else audit_accepted
        return self.audit_loaded(tables, rows, after, accepted, snapshot)

    def test_duplicated_test_label_is_reported(self):
        old = f'{REF}|Spec_2|b'
        for new in (f'{REF}|Spec_2|a', f'{REF}|Spec_2|A'):
            with self.subTest(new=new):
                result = self.run_audit(self.rows(), edit=rename_test(old, new))
                self.assertFalse(result.passed)
                self.assertIn(
                    duplicate('test', f'{REF}|Spec_2|a', new), result.duplicate_ids
                )

    def test_observation_that_does_not_join_fails(self):
        def edit(tables):
            by_id(tables, 'e1')['test'] = f'{REF}|S1|99'

        result = self.run_audit(self.rows(), edit=edit)
        self.assertFalse(result.passed)
        self.assertEqual(result.unjoined, [f'`e1`: test `{REF}|S1|99` not found'])
        self.assertEqual(result.missing, ['`e1`'])

    def test_snapshot_field_with_no_home_fails(self):
        rows = self.rows()
        snapshot = [{**r, 'mystery': ''} for r in rows]
        result = self.run_audit(rows, snapshot=snapshot)
        self.assertFalse(result.passed)
        self.assertEqual(result.unmapped_fields, ['mystery'])

    def test_accepted_entry_matching_no_group_fails(self):
        result = self.run_audit(
            self.rows(), audit_accepted=[entry(REF, 'Steel', specimen='S9')]
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.unmatched_entries, [f'`{REF}` | `S9` | material'])

    def test_specimen_reference_overrides_the_programs(self):
        def edit(tables):
            for specimen in tables['specimen']:
                if specimen['label'] == 'S1':
                    specimen['reference'] = 'Other-2020'

        result = self.run_audit(self.rows(), edit=edit)
        self.assertFalse(result.passed)
        self.assertEqual(
            result.unexpected,
            {(i, 'reference', 'Other-2020') for i in ('e1', 'e2', 'e3')},
        )

    def test_tampered_facility_location_fails(self):
        def edit(tables):
            s1 = next(s for s in tables['specimen'] if s['label'] == 'S1')
            for facility in tables['facility']:
                if facility['label'] == s1['facility']:
                    facility['location'] = 'Tampered'

        result = self.run_audit(self.rows(), edit=edit)
        self.assertFalse(result.passed)
        self.assertEqual(
            result.unexpected,
            {(i, 'location', 'Tampered') for i in ('e1', 'e2', 'e3')},
        )

    def test_snapshot_record_matched_twice_fails(self):
        def edit(tables):
            tables['observation'].append({**by_id(tables, 'e1'), 'label': '99'})

        result = self.run_audit(self.rows(), edit=edit)
        self.assertFalse(result.passed)
        self.assertEqual(result.matched_twice, ['`e1`'])

    def test_empty_snapshot_fails(self):
        tables = {
            t: [] for t in ('facility', 'program', 'specimen', 'test', 'observation')
        }
        result = audit_split.audit(tables, [], [], None)
        self.assertFalse(result.passed)


class FieldMapTests(SimpleTestCase):
    def test_map_covers_every_stage5_key(self):
        keys = set(row('e1'))
        self.assertEqual(set(audit_split.FIELD_HOME) | audit_split.SKIPPED, keys)

    def test_moved_fields_are_not_read_from_observation(self):
        moved = {
            'specimen',
            'reference',
            'location',
            'specimen_inspection_sequence',
            *audit_split.SPECIMEN_FIELDS,
            *audit_split.TEST_FIELDS,
        }
        for name in moved:
            self.assertNotIn(
                audit_split.FIELD_HOME[name][0], {'observation', 'legacy'}
            )

    def test_parse_sequence(self):
        cases = {
            '': None,
            '7': 7,
            '7.0': 7,
            '12': 12,
            '7.5': '7.5',
            '0': '0',
            'x': 'x',
        }
        for value, parsed in cases.items():
            self.assertEqual(audit_split.parse_sequence(value), parsed, value)

    def test_numbers_compare_as_numbers_and_strings_raw(self):
        self.assertTrue(audit_split.same(7, 7.0))
        self.assertFalse(audit_split.same('7', 7))
        self.assertFalse(audit_split.same('', None))
        self.assertFalse(audit_split.same('a ', 'a'))


class NormalizedCommandLineTests(SimpleTestCase):
    def main(self, *argv):
        out = io.StringIO()
        with (
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            status = audit_split.main([str(a) for a in argv])
        return status, out.getvalue()

    def test_exit_status_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rows = clean_rows()
            split = convert(tmp, rows)
            write_json(tmp / 'snapshot.json', rows)
            args = ('--normalized', split, '--snapshot', tmp / 'snapshot.json')
            args += ('--accepted', tmp / 'none.json', '--id-map', tmp / 'none.json')
            status, report = self.main(*args)
            self.assertEqual(status, 0, report)
            self.assertIn('Result: **PASS**', report)

            def edit(tables):
                by_id(tables, 'e1')['ds_description'] = 'Tampered'

            edit_tables(split, edit)
            status, report = self.main(*args)
            self.assertEqual(status, 1)
            self.assertIn('Result: **FAIL**', report)
            self.assertIn(
                '`e1` ds_description: snapshot "Cracking", rebuilt', report
            )

    def test_id_map_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rows = clean_rows()
            split = convert(tmp, rows)
            write_json(tmp / 'snapshot.json', rows)
            id_map = {}
            edit_tables(
                split, lambda tables: id_map.update(to_observation_ids(tables))
            )
            write_json(tmp / 'id_map.json', id_map)
            args = ('--normalized', split, '--snapshot', tmp / 'snapshot.json')
            args += ('--accepted', tmp / 'none.json')
            status, report = self.main(*args, '--id-map', tmp / 'id_map.json')
            self.assertEqual(status, 0, report)
            self.assertIn('Matched by: id map', report)
            status, report = self.main(*args, '--id-map', tmp / 'none.json')
            self.assertEqual(status, 1)

    def test_unreadable_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, _ = self.main(
                '--normalized', tmp, '--snapshot', Path(tmp) / 'none.json'
            )
            self.assertEqual(status, 2)


class DatabaseAuditTests(AuditCases, TestCase):
    """The same cases through ingest: the converted JSON (plus one real reference
    and component) is ingested into the test database and audited there."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        references = json.loads((DATA / 'reference.json').read_text('utf-8'))
        components = json.loads((DATA / 'component.json').read_text('utf-8'))
        cls.reference = references[0]
        cls.ref = derive_reference_id(
            cls.reference.get('reference_label', ''), cls.reference['csl_data']
        )
        cls.component_record = next(
            c for c in components if c['component_id'] == COMPONENT
        )
        cls.component = COMPONENT

    def ingest(self, directory):
        """Ingest ``directory``; return what ingest wrote to stderr."""
        write_json(directory / 'reference.json', [self.reference])
        write_json(directory / 'component.json', [self.component_record])
        err = io.StringIO()
        with patch(
            'ned_app.management.commands.ingest.build_json_data_file_path',
            side_effect=lambda name: str(directory / name),
        ):
            try:
                call_command('ingest', stdout=io.StringIO(), stderr=err)
            except CommandError:
                pass
        return err.getvalue()

    def run_audit(
        self,
        rows,
        *,
        convert_accepted=(),
        audit_accepted=None,
        edit=None,
        after=None,
        snapshot=None,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            split = convert(Path(tmp), rows, convert_accepted)
            if edit:
                edit_tables(split, edit)
            self.ingest_errors = self.ingest(split)
        tables = audit_split.load_database()
        accepted = convert_accepted if audit_accepted is None else audit_accepted
        return self.audit_loaded(tables, rows, after, accepted, snapshot)

    def test_clean_pass(self):
        super().test_clean_pass()
        self.assertEqual(self.ingest_errors, '')

    def test_duplicated_test_label_exact_merges_and_fails(self):
        # Ingest looks tests up by test_id, so an exact duplicate silently
        # updates the first test; the audit sees the merged values.
        old, new = f'{self.ref}|Spec_2|b', f'{self.ref}|Spec_2|a'
        result = self.run_audit(self.rows(), edit=rename_test(old, new))
        self.assertFalse(result.passed)
        self.assertEqual(
            result.unexpected, {('e4', 'peak_test_amplitude', '5% drift')}
        )

    def test_duplicated_test_label_case_variant_is_rejected_and_fails(self):
        # The case-insensitive constraint rejects the second test, so its
        # observations fail to ingest and the audit finds them missing.
        old, new = f'{self.ref}|Spec_2|b', f'{self.ref}|Spec_2|A'
        result = self.run_audit(self.rows(), edit=rename_test(old, new))
        self.assertFalse(result.passed)
        self.assertIn(f'test_id={new}', self.ingest_errors)
        self.assertEqual(result.missing, ['`e5`', '`e6`'])

    def test_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rows = self.rows()
            self.ingest(convert(tmp, rows))
            write_json(tmp / 'snapshot.json', rows)
            args = ['--database', '--snapshot', str(tmp / 'snapshot.json')]
            args += ['--accepted', str(tmp / 'none.json')]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(audit_split.main(args), 0, out.getvalue())
            self.assertIn('Source: database', out.getvalue())

            # Change a specimen in the database only; Observation.material keeps
            # the snapshot value, and must not mask the change.
            Specimen.objects.filter(label='S1').update(material='Tampered')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(audit_split.main(args), 1)
            self.assertIn('`e1` material: snapshot "Steel", rebuilt', out.getvalue())
