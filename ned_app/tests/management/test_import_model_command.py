"""
Tests for the import_model management command.

Covers the keystone contract (template -> import -> ingest produces correct
records) and the importer's own behaviors (dedupe, dry-run, column warnings).
Validation itself is delegated to ingest and is not retested here.
"""

import json
import os
import shutil
import tempfile
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from ned_app.management import import_utils
from ned_app.models import Component, Experiment, Reference

TEMPLATE_DIR = 'resources/import_templates'


def _template(name):
    return os.path.join(TEMPLATE_DIR, name)


class ImportModelCommandTests(TransactionTestCase):
    """Tests for import_model: keystone import->ingest plus behaviors."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)

        def mock_path(filename):
            return os.path.join(self.temp_dir, filename)

        for target in (
            'ned_app.management.import_utils.build_json_data_file_path',
            'ned_app.management.commands.ingest.build_json_data_file_path',
        ):
            patcher = patch(target, side_effect=mock_path)
            patcher.start()
            self.addCleanup(patcher.stop)

    # -- helpers --------------------------------------------------------

    def _json_path(self, filename):
        return os.path.join(self.temp_dir, filename)

    def _read_json(self, filename):
        with open(self._json_path(filename), 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_json(self, filename, data):
        with open(self._json_path(filename), 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def _write_csv(self, name, content):
        path = os.path.join(self.temp_dir, name)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        return path

    def _make_reference(self, reference_id='Smith-2020'):
        return Reference.objects.create(
            reference_id=reference_id,
            study_type='Experiment',
            comp_type='Sprinkler systems',
            pdf_saved=True,
            csl_data={
                'type': 'article-journal',
                'title': 'Seismic performance of CPVC sprinkler systems',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2020]]},
            },
        )

    # -- Tier 1: keystone template -> import -> ingest ------------------

    def test_reference_template_imports_and_ingests(self):
        out = StringIO()
        call_command(
            'import_model',
            model='Reference',
            input_file=_template('reference_template.csv'),
            stdout=out,
        )
        self.assertNotIn('unrecognized column', out.getvalue())
        self.assertTrue(os.path.exists(self._json_path('reference.json')))

        call_command('ingest', stdout=StringIO(), stderr=StringIO())

        ref = Reference.objects.get(reference_id='Smith-2020')
        # CSL reconstruction + boolean coercion verified end to end.
        self.assertIs(ref.pdf_saved, True)
        self.assertEqual(ref.year, 2020)
        self.assertEqual(ref.title, 'Seismic performance of CPVC sprinkler systems')
        # No 'id' is carried into the stored CSL data.
        self.assertNotIn('id', ref.csl_data)

    def test_reference_label_drives_derived_id(self):
        # An optional reference_label overrides the surname token in the id.
        header = (
            'reference_label,study_type,pdf_saved,csl_type,csl_title,'
            'csl_year,csl_authors\n'
        )
        row = 'FEMA_P58,Experiment,True,article-journal,A Title,2020,"Smith, John"\n'
        path = self._write_csv('labeled.csv', header + row)

        out = StringIO()
        call_command('import_model', model='Reference', input_file=path, stdout=out)
        self.assertNotIn('unrecognized column', out.getvalue())

        rec = self._read_json('reference.json')[0]
        self.assertEqual(rec['reference_label'], 'FEMA_P58')

        call_command('ingest', stdout=StringIO(), stderr=StringIO())
        self.assertTrue(
            Reference.objects.filter(reference_id='FEMA_P58-2020').exists()
        )

    def test_experiment_template_imports_and_ingests(self):
        self._make_reference()
        Component.objects.create(
            component_id='D.50.2.1.A', name='CPVC sprinkler pipe'
        )

        call_command(
            'import_model',
            model='Experiment',
            input_file=_template('experiment_template.csv'),
            stdout=StringIO(),
        )
        call_command('ingest', stdout=StringIO(), stderr=StringIO())

        exp = Experiment.objects.get(id='exp001')
        self.assertEqual(exp.reference.reference_id, 'Smith-2020')
        self.assertEqual(exp.component.component_id, 'D.50.2.1.A')
        self.assertEqual(exp.edp_value, Decimal('0.45'))

    def test_bridge_template_converts_to_expected_record(self):
        # The bridge uses the generic conversion path; verify the appended
        # JSON record without standing up the full FK graph.
        call_command(
            'import_model',
            model='ExperimentFragilityModelBridge',
            input_file=_template('experiment_fragility_bridge_template.csv'),
            stdout=StringIO(),
        )
        records = self._read_json('experiment_fragility_model_bridge.json')
        self.assertEqual(
            records,
            [{'experiment': 'exp001', 'fragility_model': 'Smith-2020|fra001'}],
        )

    # -- Tier 1.2: drift guard — accepted columns vs template header ----

    def test_template_headers_are_all_recognized_columns(self):
        from ned_app.management.commands.import_model import (
            _MODEL_CONFIG,
            _expected_columns,
        )

        templates = {
            'Reference': 'reference_template.csv',
            'Experiment': 'experiment_template.csv',
            'ExperimentFragilityModelBridge': (
                'experiment_fragility_bridge_template.csv'
            ),
        }
        for model_name, template_name in templates.items():
            columns, _ = import_utils.read_csv(_template(template_name))
            expected = _expected_columns(
                model_name, _MODEL_CONFIG[model_name]['serializer']
            )
            unknown = import_utils.find_unknown_columns(columns, expected)
            self.assertEqual(
                unknown,
                [],
                f'{template_name} has columns not accepted by {model_name}: '
                f'{unknown}',
            )

    # -- Tier 3: behaviors ---------------------------------------------

    def test_duplicate_existing_pk_is_skipped(self):
        # Dedup is by the derived reference_id, not a stored field: this record
        # derives 'Smith-2020', matching the template row.
        self._write_json(
            'reference.json',
            [
                {
                    'study_type': 'Experiment',
                    'csl_data': {
                        'type': 'article-journal',
                        'title': 'A prior CPVC study',
                        'author': [{'family': 'Smith', 'given': 'John'}],
                        'issued': {'date-parts': [[2020]]},
                    },
                }
            ],
        )

        out = StringIO()
        call_command(
            'import_model',
            model='Reference',
            input_file=_template('reference_template.csv'),
            stdout=out,
        )
        # The dropped row is reported, naming the derived id it collided on.
        self.assertIn('already present', out.getvalue())
        self.assertIn('Smith-2020', out.getvalue())
        # Nothing appended: the file still has exactly the pre-existing record.
        self.assertEqual(len(self._read_json('reference.json')), 1)

    def test_within_file_duplicate_is_skipped(self):
        # Two rows deriving the same reference_id ('Smith-2020') collapse to one,
        # and the dropped row is reported rather than silently discarded.
        header = 'study_type,pdf_saved,csl_type,csl_title,csl_year,csl_authors\n'
        row = 'Experiment,True,article-journal,A Title,2020,"Smith, John"\n'
        path = self._write_csv('dups.csv', header + row + row)

        out = StringIO()
        call_command('import_model', model='Reference', input_file=path, stdout=out)
        self.assertEqual(len(self._read_json('reference.json')), 1)
        self.assertIn('within this CSV', out.getvalue())
        self.assertIn('Smith-2020', out.getvalue())

    def test_dry_run_writes_nothing(self):
        call_command(
            'import_model',
            model='Reference',
            input_file=_template('reference_template.csv'),
            dry_run=True,
            stdout=StringIO(),
        )
        self.assertFalse(os.path.exists(self._json_path('reference.json')))

    def test_unknown_column_warning(self):
        header = (
            'study_type,pdf_saved,csl_type,csl_title,csl_year,csl_authors,edp_val\n'
        )
        row = 'Experiment,True,article-journal,A Title,2020,"Smith, John",oops\n'
        path = self._write_csv('typo.csv', header + row)

        out = StringIO()
        call_command('import_model', model='Reference', input_file=path, stdout=out)
        self.assertIn('unrecognized column', out.getvalue())
        self.assertIn('edp_val', out.getvalue())

    def test_reference_id_column_is_no_longer_accepted(self):
        # reference_id is derived at ingest, so supplying it as a column is a
        # mistake: it must be flagged as unrecognized and never stored.
        header = (
            'reference_id,study_type,pdf_saved,csl_type,csl_title,'
            'csl_year,csl_authors\n'
        )
        row = 'MINE-9,Experiment,True,article-journal,A Title,2020,"Smith, John"\n'
        path = self._write_csv('with_refid.csv', header + row)

        out = StringIO()
        call_command('import_model', model='Reference', input_file=path, stdout=out)
        self.assertIn('unrecognized column', out.getvalue())
        self.assertIn('reference_id', out.getvalue())
        rec = self._read_json('reference.json')[0]
        self.assertNotIn('reference_id', rec)
        self.assertNotIn('id', rec['csl_data'])

    def test_non_numeric_csl_year_does_not_crash(self):
        # A non-numeric csl_year must convert (passing the raw value through)
        # rather than crashing; ingest's CSL validation reports it later.
        header = 'study_type,pdf_saved,csl_type,csl_title,csl_year,csl_authors\n'
        row = 'Experiment,True,article-journal,A Title,in press,"Smith, John"\n'
        path = self._write_csv('badyear.csv', header + row)

        call_command(
            'import_model', model='Reference', input_file=path, stdout=StringIO()
        )

        rec = self._read_json('reference.json')[0]
        self.assertEqual(rec['csl_data']['issued'], {'date-parts': [['in press']]})

    def test_semicolon_delimited_csv_is_rejected(self):
        # A semicolon-delimited CSV (common from non-US Excel) must be caught
        # with guidance rather than silently importing garbage.
        header = 'study_type;pdf_saved;csl_type;csl_title;csl_year;csl_authors\n'
        row = 'Experiment;True;article-journal;A Title;2020;Smith\n'
        path = self._write_csv('semicolon.csv', header + row)

        with self.assertRaises(CommandError) as cm:
            call_command(
                'import_model',
                model='Reference',
                input_file=path,
                stdout=StringIO(),
                stderr=StringIO(),
            )
        self.assertIn('semicolon-delimited', str(cm.exception))
        self.assertFalse(os.path.exists(self._json_path('reference.json')))
