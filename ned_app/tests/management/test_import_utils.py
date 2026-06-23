"""
Unit tests for the shared CSV-import helpers and the import_model
conversion functions (Tier 2: pure functions, no database).
"""

import os
import tempfile

from django.test import SimpleTestCase

from ned_app.management import import_utils
from ned_app.management.commands import import_model


class CoerceValueTests(SimpleTestCase):
    """Tests for import_utils.coerce_value type coercion."""

    def test_integer_field_parsed(self):
        self.assertEqual(import_utils.coerce_value('ds_rank', '5'), 5)

    def test_float_field_parsed(self):
        self.assertEqual(import_utils.coerce_value('median', '0.4'), 0.4)

    def test_empty_numeric_becomes_none(self):
        self.assertIsNone(import_utils.coerce_value('ds_rank', ''))
        self.assertIsNone(import_utils.coerce_value('edp_value', ''))

    def test_boolean_true_false_case_insensitive(self):
        self.assertIs(import_utils.coerce_value('pdf_saved', 'True'), True)
        self.assertIs(import_utils.coerce_value('pdf_saved', 'false'), False)
        self.assertIs(import_utils.coerce_value('pdf_saved', 'FALSE'), False)

    def test_unparseable_numeric_passes_through(self):
        # Producing valid JSON is the goal; bad types surface at ingest.
        self.assertEqual(import_utils.coerce_value('ds_rank', 'abc'), 'abc')

    def test_untyped_field_passes_through(self):
        self.assertEqual(import_utils.coerce_value('reference_id', 'X'), 'X')
        self.assertEqual(import_utils.coerce_value('comp_type', ''), '')


class FindUnknownColumnsTests(SimpleTestCase):
    """Tests for import_utils.find_unknown_columns."""

    def test_all_known_returns_empty(self):
        self.assertEqual(
            import_utils.find_unknown_columns(['a', 'b'], {'a', 'b', 'c'}), []
        )

    def test_detects_unknown_column(self):
        self.assertEqual(
            import_utils.find_unknown_columns(['a', 'edp_val'], {'a', 'edp_value'}),
            ['edp_val'],
        )

    def test_ignores_blank_and_none_columns(self):
        # csv.DictReader yields '' / None keys for trailing-comma columns.
        self.assertEqual(
            import_utils.find_unknown_columns(['a', '', None], {'a'}), []
        )


class FragilityModelIdTests(SimpleTestCase):
    """Tests for import_utils.fragility_model_id derivation."""

    def test_with_reference(self):
        self.assertEqual(import_utils.fragility_model_id('REF', 'm1'), 'REF|m1')

    def test_without_reference(self):
        self.assertEqual(import_utils.fragility_model_id('', 'm1'), 'm1')


class BuildPkSetTests(SimpleTestCase):
    """Tests for import_utils.build_pk_set."""

    def test_single_key(self):
        records = [{'reference_id': 'a'}, {'reference_id': 'b'}]
        self.assertEqual(
            import_utils.build_pk_set(records, ['reference_id']),
            {('a',), ('b',)},
        )

    def test_composite_key(self):
        records = [{'reference': 'r', 'model_id': 'm'}]
        self.assertEqual(
            import_utils.build_pk_set(records, ['reference', 'model_id']),
            {('r', 'm')},
        )

    def test_skips_comment_records(self):
        records = [{'_comment': 'note'}, {'reference_id': 'a'}]
        self.assertEqual(
            import_utils.build_pk_set(records, ['reference_id']), {('a',)}
        )


class ReadCsvTests(SimpleTestCase):
    """Tests for import_utils.read_csv parsing and BOM handling."""

    def _write(self, content, encoding='utf-8'):
        fd, path = tempfile.mkstemp(suffix='.csv')
        os.close(fd)
        with open(path, 'w', encoding=encoding, newline='') as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_reads_rows(self):
        path = self._write('reference_id,study_type\nR1,Experiment\n')
        columns, rows = import_utils.read_csv(path)
        self.assertEqual(columns, ['reference_id', 'study_type'])
        self.assertEqual(rows, [{'reference_id': 'R1', 'study_type': 'Experiment'}])

    def test_strips_utf8_bom(self):
        # Excel writes a BOM at the front of saved CSVs; utf-8-sig strips it.
        path = self._write('reference_id,study_type\nR1,Experiment\n', 'utf-8-sig')
        columns, _ = import_utils.read_csv(path)
        self.assertEqual(columns[0], 'reference_id')

    def test_header_only_returns_no_rows(self):
        path = self._write('reference_id,study_type\n')
        columns, rows = import_utils.read_csv(path)
        self.assertEqual(columns, ['reference_id', 'study_type'])
        self.assertEqual(rows, [])


class ParseAuthorsTests(SimpleTestCase):
    """Tests for import_model._parse_authors CSL author parsing."""

    def test_family_given_pairs(self):
        self.assertEqual(
            import_model._parse_authors('Smith, John; Doe, Jane'),
            [
                {'family': 'Smith', 'given': 'John'},
                {'family': 'Doe', 'given': 'Jane'},
            ],
        )

    def test_literal_when_no_comma(self):
        self.assertEqual(
            import_model._parse_authors('Acme Corporation'),
            [{'literal': 'Acme Corporation'}],
        )

    def test_ignores_empty_segments(self):
        self.assertEqual(
            import_model._parse_authors('Smith, John; '),
            [{'family': 'Smith', 'given': 'John'}],
        )


class BuildCslDataTests(SimpleTestCase):
    """Tests for import_model._build_csl_data reconstruction."""

    def test_required_and_optional_fields(self):
        row = {
            'reference_id': 'SMITH-2020',
            'csl_type': 'article-journal',
            'csl_title': 'A Title',
            'csl_year': '2020',
            'csl_authors': 'Smith, John',
            'csl_doi': '10.1/x',
            'csl_journal': 'J. Eng.',
        }
        csl = import_model._build_csl_data(row)
        self.assertEqual(csl['id'], 'SMITH-2020')
        self.assertEqual(csl['type'], 'article-journal')
        self.assertEqual(csl['title'], 'A Title')
        self.assertEqual(csl['issued'], {'date-parts': [[2020]]})
        self.assertEqual(csl['author'], [{'family': 'Smith', 'given': 'John'}])
        self.assertEqual(csl['DOI'], '10.1/x')
        self.assertEqual(csl['container-title'], 'J. Eng.')

    def test_blank_optional_fields_omitted(self):
        row = {
            'reference_id': 'R',
            'csl_type': 'article-journal',
            'csl_title': 'T',
            'csl_year': '2020',
            'csl_authors': 'Smith, John',
            'csl_doi': '',
        }
        csl = import_model._build_csl_data(row)
        self.assertNotIn('DOI', csl)


class RowToRecordTests(SimpleTestCase):
    """Tests for import_model._row_to_record conversion."""

    def test_reference_flattens_csl_and_coerces_boolean(self):
        row = {
            'reference_id': 'R',
            'study_type': 'Experiment',
            'comp_type': 'Walls',
            'pdf_saved': 'True',
            'csl_type': 'article-journal',
            'csl_title': 'T',
            'csl_year': '2020',
            'csl_authors': 'Smith, John',
        }
        record = import_model._row_to_record(row, 'Reference')
        # pdf_saved coerced to a real boolean, not the string "True"
        self.assertIs(record['pdf_saved'], True)
        # csl_* columns are folded into nested csl_data, not left flat
        self.assertNotIn('csl_title', record)
        self.assertEqual(record['csl_data']['title'], 'T')
        self.assertEqual(record['study_type'], 'Experiment')

    def test_non_reference_coerces_numerics(self):
        row = {'id': 'exp1', 'ds_rank': '2', 'edp_value': '0.45'}
        record = import_model._row_to_record(row, 'Experiment')
        self.assertEqual(record['ds_rank'], 2)
        self.assertEqual(record['edp_value'], 0.45)
        self.assertEqual(record['id'], 'exp1')


class ExpectedColumnsTests(SimpleTestCase):
    """Tests for import_model._expected_columns derivation."""

    def test_reference_uses_flattened_csl_columns(self):
        from ned_app.serialization.serializer import ReferenceSerializer

        cols = import_model._expected_columns('Reference', ReferenceSerializer)
        self.assertIn('csl_title', cols)
        self.assertIn('reference_id', cols)
        # nested/auto-populated fields are not CSV columns
        self.assertNotIn('csl_data', cols)
        self.assertNotIn('title', cols)
        self.assertNotIn('year', cols)
