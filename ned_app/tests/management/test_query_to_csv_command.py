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

from ned_app.models import (
    Component,
    Facility,
    Observation,
    Program,
    Reference,
    Specimen,
    Test,
)


class QueryToCsvCommandTests(TestCase):
    """Tests for the query_to_csv command."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.output_file = os.path.join(self.temp_dir, 'out.csv')

        self.reference = Reference.objects.create(
            study_type='Experiment',
            comp_type='Sprinkler systems',
            csl_data={
                'type': 'article-journal',
                'title': 'A Title',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2020]]},
            },
        )
        self.component = Component.objects.create(
            component_id='D.50.2.1.A', name='CPVC sprinkler pipe'
        )
        program = Program.objects.create(reference=self.reference)
        facility = Facility.objects.create(label='Lab')
        specimen = self._make_specimen(program, facility, 'SP-1', material='Steel')
        self._make_specimen(program, facility, 'SP-2', material='CPVC')
        self.test = Test.objects.create(
            specimen=specimen, label='a', test_type='Dynamic, uniaxial'
        )
        self._make_experiment('01', notes='plain')
        self._make_experiment('02', notes='ratio=0.5')

    def _make_specimen(self, program, facility, label, material):
        return Specimen.objects.create(
            program=program,
            facility=facility,
            reference=self.reference,
            label=label,
            contributor='Contributor',
            component=self.component,
            material=material,
            comp_description='CPVC sprinkler pipe',
        )

    def _make_experiment(self, label, notes):
        return Observation.objects.create(
            test=self.test,
            label=label,
            ds_description='Leakage',
            edp_metric='Peak Floor Acceleration, horizontal',
            edp_unit='g',
            edp_value=Decimal('0.45'),
            legacy_ds_rank=1,
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
            model='Specimen',
            output_file=self.output_file,
            fields='specimen_id,program,facility,reference,component',
            stdout=StringIO(),
        )
        rows = {r['specimen_id']: r for r in self._read_rows()}
        # reference must be the reference_id natural key, not the auto PK int;
        # component must be the component_id, not the concatenated id PK; the
        # program and facility must be their program_id and label.
        row = rows['Smith-2020|SP-1']
        self.assertEqual(row['program'], 'Smith-2020')
        self.assertEqual(row['facility'], 'Lab')
        self.assertEqual(row['reference'], 'Smith-2020')
        self.assertEqual(row['component'], 'D.50.2.1.A')

        # An observation's test must be the test_id.
        call_command(
            'query_to_csv',
            model='Observation',
            output_file=self.output_file,
            fields='observation_id,test',
            stdout=StringIO(),
        )
        rows = {r['observation_id']: r for r in self._read_rows()}
        self.assertEqual(rows['Smith-2020|SP-1|a|01']['test'], 'Smith-2020|SP-1|a')

    # -- field selection / filtering -----------------------------------

    def test_fields_selection_limits_columns(self):
        call_command(
            'query_to_csv',
            model='Specimen',
            output_file=self.output_file,
            fields='specimen_id,material',
            stdout=StringIO(),
        )
        rows = self._read_rows()
        self.assertEqual(set(rows[0].keys()), {'specimen_id', 'material'})

    def test_filter_basic(self):
        call_command(
            'query_to_csv',
            model='Specimen',
            output_file=self.output_file,
            filter='material=Steel',
            stdout=StringIO(),
        )
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['specimen_id'], 'Smith-2020|SP-1')

    def test_filter_value_containing_equals(self):
        # split('=', 1) must keep 'ratio=0.5' intact as the value.
        call_command(
            'query_to_csv',
            model='Observation',
            output_file=self.output_file,
            filter='notes=ratio=0.5',
            stdout=StringIO(),
        )
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['observation_id'], 'Smith-2020|SP-1|a|02')

    # -- friendly error handling ---------------------------------------

    def test_invalid_filter_field_reports_friendly_error(self):
        with self.assertRaises(CommandError) as cm:
            call_command(
                'query_to_csv',
                model='Observation',
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
                model='Observation',
                output_file=self.output_file,
                fields='observation_id,bogus_field',
                stderr=StringIO(),
            )
        self.assertIn("Field 'bogus_field' does not exist", str(cm.exception))
        self.assertFalseFileWritten()

    def test_malformed_filter_reports_friendly_error(self):
        with self.assertRaises(CommandError) as cm:
            call_command(
                'query_to_csv',
                model='Observation',
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
            model='Specimen',
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
        self.assertIn('Observation', out.getvalue())
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
            model='Observation',
            output_file=self.output_file,
            fields='observation_id',
            stdout=StringIO(),
        )
        with open(self.output_file, 'rb') as f:
            self.assertEqual(f.read(3), b'\xef\xbb\xbf')
