"""
Tests for the query_to_csv management command, including the foreign-key
natural-key fix, filter parsing, field selection, friendly errors, and the
no-truncate-on-empty-result behavior.
"""

import csv
import json
import os
import shutil
import tempfile
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ned_app.models import Component, Experiment, Reference


class QueryToCsvCommandTests(TestCase):
    """Tests for the query_to_csv command."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.output_file = os.path.join(self.temp_dir, 'out.csv')

        self.reference = Reference.objects.create(
            reference_id='SMITH-2020-EXP',
            study_type='Experiment',
            comp_type='Sprinkler systems',
            pdf_saved=True,
            csl_data={
                'type': 'article-journal',
                'id': 'SMITH-2020-EXP',
                'title': 'A Title',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2020]]},
            },
        )
        self.component = Component.objects.create(
            component_id='D.50.2.1.A', name='CPVC sprinkler pipe'
        )
        self._make_experiment('exp001', material='Steel', notes='plain')
        self._make_experiment('exp002', material='CPVC', notes='ratio=0.5')

    def _make_experiment(self, exp_id, material, notes):
        return Experiment.objects.create(
            id=exp_id,
            reference=self.reference,
            component=self.component,
            specimen='SP-1',
            reviewer='Reviewer',
            test_type='Dynamic, uniaxial',
            material=material,
            comp_description='CPVC sprinkler pipe',
            ds_description='Leakage',
            edp_metric='Peak Floor Acceleration, horizontal',
            edp_unit='g',
            edp_value=Decimal('0.45'),
            ds_rank=1,
            ds_class='Consequential',
            notes=notes,
        )

    def _read_rows(self):
        # utf-8-sig strips the BOM the command now writes for Excel.
        with open(self.output_file, 'r', encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))

    # -- the foreign-key fix -------------------------------------------

    def test_fk_columns_use_natural_keys(self):
        call_command(
            'query_to_csv',
            model='Experiment',
            output_file=self.output_file,
            fields='id,reference,component',
            stdout=StringIO(),
        )
        rows = {r['id']: r for r in self._read_rows()}
        # reference must be the reference_id natural key, not the auto PK int;
        # component must be the component_id, not the concatenated id PK.
        self.assertEqual(rows['exp001']['reference'], 'SMITH-2020-EXP')
        self.assertEqual(rows['exp001']['component'], 'D.50.2.1.A')

    # -- field selection / filtering -----------------------------------

    def test_fields_selection_limits_columns(self):
        call_command(
            'query_to_csv',
            model='Experiment',
            output_file=self.output_file,
            fields='id,material',
            stdout=StringIO(),
        )
        rows = self._read_rows()
        self.assertEqual(set(rows[0].keys()), {'id', 'material'})

    def test_filter_basic(self):
        call_command(
            'query_to_csv',
            model='Experiment',
            output_file=self.output_file,
            filter='material=Steel',
            stdout=StringIO(),
        )
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'exp001')

    def test_filter_value_containing_equals(self):
        # split('=', 1) must keep 'ratio=0.5' intact as the value.
        call_command(
            'query_to_csv',
            model='Experiment',
            output_file=self.output_file,
            filter='notes=ratio=0.5',
            stdout=StringIO(),
        )
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], 'exp002')

    # -- friendly error handling ---------------------------------------

    def test_invalid_filter_field_reports_friendly_error(self):
        with self.assertRaises(CommandError) as cm:
            call_command(
                'query_to_csv',
                model='Experiment',
                output_file=self.output_file,
                filter='bogus_field=x',
                stderr=StringIO(),
            )
        self.assertIn('Invalid filter', str(cm.exception))
        self.assertFalseFileWritten()

    def test_invalid_field_name_reports_friendly_error(self):
        with self.assertRaises(CommandError) as cm:
            call_command(
                'query_to_csv',
                model='Experiment',
                output_file=self.output_file,
                fields='id,bogus_field',
                stderr=StringIO(),
            )
        self.assertIn("Field 'bogus_field' does not exist", str(cm.exception))
        self.assertFalseFileWritten()

    def test_malformed_filter_reports_friendly_error(self):
        with self.assertRaises(CommandError) as cm:
            call_command(
                'query_to_csv',
                model='Experiment',
                output_file=self.output_file,
                filter='no_equals_sign',
                stderr=StringIO(),
            )
        self.assertIn('Invalid filter', str(cm.exception))
        self.assertFalseFileWritten()

    def assertFalseFileWritten(self):
        self.assertFalse(
            os.path.exists(self.output_file),
            'output file should not be created on error',
        )

    # -- no-truncate-on-empty-result -----------------------------------

    def test_empty_result_does_not_truncate_existing_file(self):
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write('PRE-EXISTING CONTENT')

        out = StringIO()
        call_command(
            'query_to_csv',
            model='Experiment',
            output_file=self.output_file,
            filter='material=DoesNotExist',
            stdout=out,
        )
        self.assertIn('No data found', out.getvalue())
        with open(self.output_file, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read(), 'PRE-EXISTING CONTENT')

    # -- list models ----------------------------------------------------

    def test_list_models(self):
        out = StringIO()
        call_command('query_to_csv', list_models=True, stdout=out)
        self.assertIn('Experiment', out.getvalue())
        self.assertIn('Reference', out.getvalue())

    # -- JSONField encoding + Excel BOM --------------------------------

    def test_jsonfield_exported_as_valid_json(self):
        call_command(
            'query_to_csv',
            model='Reference',
            output_file=self.output_file,
            fields='reference_id,csl_data',
            stdout=StringIO(),
        )
        row = self._read_rows()[0]
        # Must be valid JSON (double-quoted), not a Python dict repr.
        parsed = json.loads(row['csl_data'])
        self.assertEqual(parsed['title'], 'A Title')
        self.assertEqual(parsed['issued'], {'date-parts': [[2020]]})

    def test_output_written_with_utf8_bom(self):
        call_command(
            'query_to_csv',
            model='Experiment',
            output_file=self.output_file,
            fields='id',
            stdout=StringIO(),
        )
        with open(self.output_file, 'rb') as f:
            self.assertEqual(f.read(3), b'\xef\xbb\xbf')
