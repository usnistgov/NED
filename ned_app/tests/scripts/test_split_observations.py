"""
Unit tests for scripts/split_observations.py, the Experiment-split conversion tool.

Fixtures are small lists of rows shaped like Stage 5's observation.json (with the
test / label / damage_location placeholders). No database is needed.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from django.test import SimpleTestCase

SCRIPTS = Path(__file__).resolve().parents[3] / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import split_observations as so

REF = 'Smith-2020'
OTHER = 'Jones-2019'

# The keys export_data writes for each model (steps doc, Stage 5), written out
# here rather than taken from the script, so the check is independent.
STAGE5_KEYS = {
    'facility.json': {'label', 'name', 'location', 'notes'},
    'program.json': {'label', 'name', 'notes', 'reference'},
    'specimen.json': {
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
    },
    'test.json': {
        'specimen',
        'label',
        'test_order',
        'test_type',
        'loading_protocol',
        'peak_test_amplitude',
        'prior_damage',
        'prior_damage_repaired',
        'notes',
    },
}


def row(id, specimen='S1', reference=REF, **overrides):
    """Return one flat observation row with Stage 5's placeholders."""
    base = {
        'id': id,
        'reference': reference,
        'specimen': specimen,
        'specimen_inspection_sequence': '',
        'contributor': 'NIST',
        'component': 'B.20.1.1.A',
        'comp_detail': 'Detail',
        'material': 'Steel',
        'size_class': 'Full',
        'design_objective': '',
        'governing_design_standard': '',
        'comp_description': 'Line one\nLine two',
        'location': 'UCSD, California',
        'test_type': 'Cyclic',
        'loading_protocol': 'FEMA 461',
        'peak_test_amplitude': '3% drift',
        'ds_description': 'Cracking',
        'ds_class': 'Damage',
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


def run(rows, accepted=()):
    """Split ``rows`` and return the result."""
    return so.split_rows(rows, list(accepted))


def rules(split):
    """Return the set of error codes raised."""
    return {p.rule for p in split.errors}


def obs_by_id(split):
    """Map old observation id to its output record."""
    return {o['id']: o for o in split.tables['observation.json']}


def tests_of(split):
    """Map test label to test record (single-specimen fixtures)."""
    return {t['label']: t for t in split.tables['test.json']}


class GeneralTests(SimpleTestCase):
    def test_clean_group(self):
        split = run([row('e1'), row('e2', edp_value=0.02)])
        self.assertEqual(split.errors, [])
        self.assertEqual(
            split.tables['facility.json'],
            [
                {
                    'label': 'UCSD_California',
                    'location': 'UCSD, California',
                    'name': '',
                    'notes': '',
                }
            ],
        )
        self.assertEqual(
            split.tables['program.json'],
            [{'reference': REF, 'label': '', 'name': '', 'notes': ''}],
        )
        (specimen,) = split.tables['specimen.json']
        self.assertEqual(specimen['program'], REF)
        self.assertEqual(specimen['facility'], 'UCSD_California')
        self.assertIsNone(specimen['reference'])
        self.assertEqual((specimen['label'], specimen['name']), ('S1', 'S1'))
        self.assertEqual(specimen['comp_description'], 'Line one\nLine two')
        (test,) = split.tables['test.json']
        self.assertEqual(test['specimen'], f'{REF}|S1')
        self.assertEqual(test['label'], 'a')
        self.assertIsNone(test['test_order'])
        self.assertEqual(
            (test['prior_damage'], test['prior_damage_repaired'], test['notes']),
            ('', '', ''),
        )
        obs = obs_by_id(split)
        self.assertEqual(obs['e1']['test'], f'{REF}|S1|a')
        self.assertEqual((obs['e1']['label'], obs['e2']['label']), ('01', '02'))

    def test_specimen_label_is_slug_and_name_verbatim(self):
        split = run([row('e1', specimen='Config8. Specimen 20')])
        (specimen,) = split.tables['specimen.json']
        self.assertEqual(specimen['label'], 'Config8._Specimen_20')
        self.assertEqual(specimen['name'], 'Config8. Specimen 20')

    def test_observation_keeps_every_key_and_value(self):
        rows = [row('e2', prior_damage='Cracks'), row('e1', ds_rank=3)]
        split = run(rows)
        out = split.tables['observation.json']
        self.assertEqual([o['id'] for o in out], ['e2', 'e1'])  # order kept
        for before, after in zip(rows, out):
            self.assertEqual(set(after), set(before))
            for key in set(before) - {'test', 'label'}:
                self.assertEqual(after[key], before[key])

    def test_input_without_placeholders_gains_only_test_and_label(self):
        rows = [row('e1')]
        for key in ('test', 'label', 'damage_location'):
            del rows[0][key]
        (out,) = run(rows).tables['observation.json']
        self.assertEqual(set(out) - set(rows[0]), {'test', 'label'})
        self.assertNotIn('damage_location', out)

    def test_two_runs_are_byte_identical(self):
        # Separate processes with different hash seeds, so output can't depend on
        # set or dict-hash order.
        rows = [
            row('e3', specimen='S 2', specimen_inspection_sequence='2'),
            row('e1', specimen_inspection_sequence='7.0'),
            row('e2', specimen='S3', peak_test_amplitude='4%', location=''),
            row('e4', reference=OTHER, specimen='B-1', location='Lab'),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_input(tmp / 'input', rows)
            (tmp / 'accepted.json').write_text('[]', encoding='utf-8')
            outputs = []
            for seed in ('1', '2'):
                out = tmp / f'out{seed}'
                done = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / 'split_observations.py'),
                        'convert',
                        '--input',
                        str(tmp / 'input'),
                        '--accepted',
                        str(tmp / 'accepted.json'),
                        '--output',
                        str(out),
                    ],
                    env={**os.environ, 'PYTHONHASHSEED': seed},
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(done.returncode, 0, done.stderr)
                outputs.append({
                    p.name: p.read_bytes() for p in sorted(out.iterdir())
                })
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(
                sorted(outputs[0]),
                sorted([*so.DATA_FILES, 'report.md']),
            )


def write_input(directory, rows):
    """Write the flat observation.json, the tool's only data input."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'observation.json').write_text(json.dumps(rows), encoding='utf-8')


def convert_in(tmp, rows, output, check=False, accepted=()):
    """Write the inputs under ``tmp`` and run the conversion into ``output``."""
    write_input(tmp / 'input', rows)
    accepted_path = tmp / 'accepted.json'
    accepted_path.write_text(json.dumps(list(accepted)), encoding='utf-8')
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        return so.convert(tmp / 'input', accepted_path, output, check)


class AcceptedCollapseTests(SimpleTestCase):
    def test_unlisted_disagreement_is_an_error(self):
        split = run([row('e1'), row('e2', material='Aluminum')])
        self.assertEqual(rules(split), {'specimen.disagreement'})
        (problem,) = split.errors
        self.assertEqual((problem.reference, problem.specimen), (REF, 'S1'))
        self.assertEqual(problem.detail, 'material')
        self.assertEqual(
            dict(problem.values), {'"Aluminum"': ('e2',), '"Steel"': ('e1',)}
        )

    def test_listed_disagreement_uses_the_listed_value(self):
        entry = {
            'reference': REF,
            'specimen': 'S1',
            'field': 'material',
            'value': 'Aluminum',
            'reason': 'paper, Table 2',
        }
        rows = [row('e1'), row('e2'), row('e3', material='Aluminum')]
        split = run(rows, [entry])
        self.assertEqual(split.errors, [])
        (specimen,) = split.tables['specimen.json']
        self.assertEqual(specimen['material'], 'Aluminum')
        self.assertEqual(split.applied, [(entry, ['e1', 'e2'], 'Aluminum')])
        # The observation file still holds the original values.
        self.assertEqual(obs_by_id(split)['e1']['material'], 'Steel')

    def test_entry_matching_nothing_is_an_error(self):
        entry = {
            'reference': REF,
            'specimen': 'No such specimen',
            'field': 'material',
            'value': 'Steel',
            'reason': '',
        }
        self.assertEqual(rules(run([row('e1')], [entry])), {'accepted.no_group'})

    def test_two_entries_for_one_group_and_field_are_an_error(self):
        entry = {
            'reference': REF,
            'specimen': 'S1',
            'field': 'material',
            'value': 'Steel',
            'reason': '',
        }
        rows = [row('e1', material='Steel'), row('e2', material='Aluminum')]
        self.assertIn('accepted.duplicate', rules(run(rows, [entry, entry])))

    def test_entry_naming_a_value_no_row_holds_is_an_error(self):
        entry = {
            'reference': REF,
            'specimen': 'S1',
            'field': 'material',
            'value': 'Wood',
            'reason': '',
        }
        rows = [row('e1'), row('e2', material='Aluminum')]
        # The entry is rejected, so the disagreement is unlisted too.
        self.assertEqual(
            rules(run(rows, [entry])),
            {'accepted.no_value', 'specimen.disagreement'},
        )


class FacilityTests(SimpleTestCase):
    def test_blank_location_gets_the_placeholder_facility(self):
        rows = [
            row('e1', location=''),
            row('e2', specimen='S2', location=''),
            row('e3', reference=OTHER, location=''),
        ]
        split = run(rows)
        self.assertEqual(split.errors, [])
        self.assertEqual(
            split.tables['facility.json'],
            [
                {
                    'label': f'unknown_{OTHER}',
                    'location': '',
                    'name': '',
                    'notes': '',
                },
                {'label': f'unknown_{REF}', 'location': '', 'name': '', 'notes': ''},
            ],
        )
        facilities = {
            (s['program'], s['label']): s['facility']
            for s in split.tables['specimen.json']
        }
        self.assertEqual(facilities[REF, 'S2'], f'unknown_{REF}')
        self.assertEqual(facilities[OTHER, 'S1'], f'unknown_{OTHER}')

    def test_location_varying_within_a_specimen_is_an_error(self):
        split = run([row('e1'), row('e2', location='Buffalo, NY')])
        self.assertEqual(rules(split), {'facility.location_varies'})
        self.assertEqual(
            dict(split.errors[0].values),
            {'"Buffalo, NY"': ('e2',), '"UCSD, California"': ('e1',)},
        )

    def test_two_raw_spellings_in_one_group_is_an_error(self):
        rows = [row('e1'), row('e2', specimen='S2', location='ucsd,  CALIFORNIA')]
        split = run(rows)
        self.assertEqual(rules(split), {'facility.spellings'})

    def test_label_collision_is_an_error(self):
        rows = [
            row('e1', location='UCSD, CA'),
            row('e2', specimen='S2', location='UCSD CA'),
        ]
        self.assertEqual(rules(run(rows)), {'facility.label_collision'})

    def test_reference_spanning_several_facilities_is_reported(self):
        rows = [row('e1'), row('e2', specimen='S2', location='Buffalo, NY')]
        split = run(rows)
        self.assertEqual(split.errors, [])
        self.assertEqual(
            split.multi_facility_refs, {REF: ['Buffalo_NY', 'UCSD_California']}
        )


class SpecimenTests(SimpleTestCase):
    def test_slug_collision_within_a_program_is_an_error(self):
        rows = [
            row('e1', specimen='S 1'),
            row('e2', specimen='s_1'),
            row('e3', specimen='S 1', reference=OTHER),  # another program: fine
        ]
        split = run(rows)
        self.assertEqual(rules(split), {'specimen.label_collision'})
        (problem,) = split.errors
        self.assertEqual(problem.reference, REF)
        self.assertEqual(dict(problem.values), {'"S 1"': ('e1',), '"s_1"': ('e2',)})

    def test_blank_specimen_is_an_error(self):
        split = run([row('e1'), row('e2', specimen='  ')])
        self.assertEqual(rules(split), {'specimen.blank'})
        self.assertEqual(split.errors[0].values, (('""', ('e2',)),))

    def test_label_over_100_characters_is_an_error(self):
        self.assertIn('label.invalid', rules(run([row('e1', specimen='S' * 101)])))

    def test_specimen_that_slugs_to_nothing_is_an_error(self):
        self.assertEqual(rules(run([row('e1', specimen='###')])), {'label.empty'})


class TestTests(SimpleTestCase):
    def test_sequence_starting_at_7_keeps_7(self):
        rows = [
            row('e1', specimen_inspection_sequence='7.0'),
            row('e2', specimen_inspection_sequence='8', peak_test_amplitude='4%'),
            row('e3', specimen_inspection_sequence='12'),
        ]
        split = run(rows)
        self.assertEqual(split.errors, [])
        tests = tests_of(split)
        self.assertEqual(sorted(tests), ['12', '7', '8'])
        self.assertEqual(
            [tests[lbl]['test_order'] for lbl in ('7', '8', '12')], [7, 8, 12]
        )
        self.assertEqual(obs_by_id(split)['e1']['test'], f'{REF}|S1|7')

    def test_mixed_numeric_and_blank_give_digit_and_letter_labels(self):
        rows = [
            row('e1', specimen_inspection_sequence='3', peak_test_amplitude='9%'),
            row('e2', peak_test_amplitude='5%'),
            row('e3', peak_test_amplitude='2%'),
        ]
        split = run(rows)
        self.assertEqual(split.errors, [])
        obs = obs_by_id(split)
        self.assertEqual(
            [obs[i]['test'].rsplit('|', 1)[1] for i in ('e1', 'e3', 'e2')],
            ['3', 'a', 'b'],
        )
        self.assertEqual(
            split.multi_test, {f'{REF}|S1': [('3', 3), ('a', None), ('b', None)]}
        )

    def test_duplicate_test_order_is_an_error(self):
        rows = [
            row('e1', specimen_inspection_sequence='7'),
            row('e2', specimen_inspection_sequence='7.0'),  # same integer
        ]
        split = run(rows)
        self.assertEqual(rules(split), {'test.duplicate_order'})
        self.assertEqual(
            dict(split.errors[0].values), {'"7"': ('e1',), '"7.0"': ('e2',)}
        )

    def test_invalid_sequences_are_errors(self):
        for value in ('7.5', '0', '-1', 'first'):
            with self.subTest(value=value):
                split = run([row('e1', specimen_inspection_sequence=value)])
                self.assertEqual(rules(split), {'test.invalid_sequence'})

    def test_several_unordered_tests_get_a_b_c(self):
        rows = [
            row('e1', test_type='Monotonic'),
            row('e2', loading_protocol='ATC-24'),
            row('e3', test_type='Cyclic', peak_test_amplitude=''),
            row('e4'),  # same test as none of the others
        ]
        split = run(rows)
        self.assertEqual(split.errors, [])
        obs = obs_by_id(split)
        # Sorted by test_type, then loading_protocol, then peak_test_amplitude.
        self.assertEqual(
            {i: obs[i]['test'].rsplit('|', 1)[1] for i in obs},
            {'e2': 'a', 'e3': 'b', 'e4': 'c', 'e1': 'd'},
        )
        self.assertEqual(split.multi_test[f'{REF}|S1'][0], ('a', None))

    def test_letter_labels(self):
        self.assertEqual(
            [so.letter_label(i) for i in (0, 1, 25, 26, 27, 51, 52, 701, 702)],
            ['a', 'b', 'z', 'aa', 'ab', 'az', 'ba', 'zz', 'aaa'],
        )


class ObservationTests(SimpleTestCase):
    def test_label_order_with_null_ds_rank_and_an_edp_tie(self):
        rows = [
            row('e5', ds_rank=None, edp_value=None),
            row('e4', ds_rank=None, edp_value=0.01),
            row('e1', ds_rank=None, edp_value=0.01),  # ties e4; id breaks it
            row('e2', ds_rank=2, edp_value=0.001),
            row('e3', ds_rank=1, edp_value=0.05),
        ]
        obs = obs_by_id(run(rows))
        self.assertEqual(
            {i: o['label'] for i, o in obs.items()},
            {'e3': '01', 'e2': '02', 'e1': '03', 'e4': '04', 'e5': '05'},
        )

    def test_label_width_grows_past_99(self):
        rows = [row(f'e{i:03d}', edp_value=i / 1000) for i in range(100)]
        labels = sorted(o['label'] for o in run(rows).tables['observation.json'])
        self.assertEqual((labels[0], labels[-1]), ('001', '100'))


class ProgramTests(SimpleTestCase):
    def test_one_program_per_reference_with_observations(self):
        # Programs come from observation.json alone: a reference with no
        # observations never appears, so it gets no program.
        rows = [row('e1'), row('e2', specimen='S2'), row('e3', reference=OTHER)]
        split = run(rows)
        self.assertEqual(
            split.tables['program.json'],
            [
                {'reference': OTHER, 'label': '', 'name': '', 'notes': ''},
                {'reference': REF, 'label': '', 'name': '', 'notes': ''},
            ],
        )


class OutputTests(SimpleTestCase):
    rows: ClassVar[list[dict]] = [
        row('e1', specimen_inspection_sequence='2'),
        row('e2', specimen='S2', location=''),
    ]

    def test_written_keys_equal_stage5_export_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.assertEqual(convert_in(tmp, self.rows, tmp / 'out'), 0)
            for name, keys in STAGE5_KEYS.items():
                records = json.loads((tmp / 'out' / name).read_text('utf-8'))
                self.assertTrue(records, name)
                for record in records:
                    self.assertEqual(set(record), keys, name)
            observations = json.loads(
                (tmp / 'out' / 'observation.json').read_text('utf-8')
            )
            for record in observations:
                self.assertEqual(set(record), set(self.rows[0]))

    def test_files_are_in_export_data_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            convert_in(tmp, self.rows, tmp / 'out')
            for name in so.DATA_FILES:
                raw = (tmp / 'out' / name).read_bytes().decode('utf-8')
                canonical = json.dumps(json.loads(raw), indent=4, sort_keys=True)
                self.assertEqual(raw, canonical, name)

    def test_errors_write_the_report_and_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rows = [*self.rows, row('e3', specimen='')]
            self.assertEqual(convert_in(tmp, rows, tmp / 'out'), 1)
            self.assertEqual(
                [p.name for p in (tmp / 'out').iterdir()], ['report.md']
            )
            report = (tmp / 'out' / 'report.md').read_text('utf-8')
            self.assertIn('specimen.blank', report)
            self.assertIn('e3', report)

    def test_check_writes_only_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            self.assertEqual(convert_in(tmp, self.rows, tmp / 'out', check=True), 0)
            self.assertEqual(
                [p.name for p in (tmp / 'out').iterdir()], ['report.md']
            )

    def test_output_must_be_new_or_empty_apart_from_a_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            out = tmp / 'out'
            out.mkdir()
            (out / 'report.md').write_text('old', encoding='utf-8')
            self.assertEqual(convert_in(tmp, self.rows, out), 0)
            self.assertNotEqual((out / 'report.md').read_text('utf-8'), 'old')
            # Now it holds data files, so a second run is refused.
            self.assertEqual(convert_in(tmp, self.rows, out), 2)


class PostSplitInputTests(SimpleTestCase):
    """The live data is split since Stage 8: both scripts' main() stop on it
    with a message instead of failing on a missing key."""

    def post_split_input(self, tmp):
        """Write a post-split observation.json (a test, no id); return its folder."""
        record = {k: v for k, v in row('e1').items() if k != 'id'}
        write_input(
            tmp / 'input', [{**record, 'test': f'{REF}|S1|a', 'label': '01'}]
        )
        return tmp / 'input'

    def test_convert_stops_on_post_split_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            argv = ['convert', '--input', str(self.post_split_input(tmp))]
            argv += ['--accepted', str(tmp / 'none.json')]
            argv += ['--output', str(tmp / 'out')]
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(so.main(argv), 2)
            self.assertIn('post-split observations', err.getvalue())
            self.assertIn('observation_pre_split.json', err.getvalue())
            self.assertFalse((tmp / 'out').exists())

    def test_measure_stops_on_post_split_input(self):
        import measure_split_inputs

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            argv = ['measure_split_inputs.py', '--data-dir']
            argv += [str(self.post_split_input(tmp))]
            err = io.StringIO()
            with patch.object(sys, 'argv', argv), contextlib.redirect_stderr(err):
                self.assertEqual(measure_split_inputs.main(), 2)
            self.assertIn('post-split observations', err.getvalue())
