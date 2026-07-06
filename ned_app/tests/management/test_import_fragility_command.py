"""
Tests for the import_fragility management command.

Covers the keystone contract (template -> import -> ingest produces the
model/curve/bridge graph), the cross-row consistency check (the one check
this command still enforces), and dedupe / dry-run behaviors.
"""

import json
import os
import shutil
import tempfile
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TransactionTestCase

from ned_app.management import import_utils
from ned_app.models import (
    Component,
    ComponentFragilityModelBridge,
    FragilityCurve,
    FragilityModel,
    Reference,
)

TEMPLATE_DIR = 'resources/import_templates'
FRAGILITY_TEMPLATE = os.path.join(TEMPLATE_DIR, 'fragility_import_template.csv')


class ImportFragilityCommandTests(TransactionTestCase):
    """Tests for import_fragility: keystone import->ingest plus behaviors."""

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

    def _write_csv(self, name, content):
        path = os.path.join(self.temp_dir, name)
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        return path

    def _make_base_data(self):
        Reference.objects.create(
            reference_id='SMITH-2020-EXP',
            study_type='Experiment',
            comp_type='Sprinkler systems',
            pdf_saved=True,
            csl_data={
                'type': 'article-journal',
                'id': 'SMITH-2020-EXP',
                'title': 'Seismic performance of CPVC sprinkler systems',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2020]]},
            },
        )
        Component.objects.create(component_id='A.40.1.1', name='Sprinkler pipe')
        Component.objects.create(component_id='A.40.1.2', name='Sprinkler head')

    # -- Tier 1: keystone template -> import -> ingest ------------------

    def test_template_imports_and_ingests(self):
        self._make_base_data()

        out = StringIO()
        call_command('import_fragility', input_file=FRAGILITY_TEMPLATE, stdout=out)
        self.assertNotIn('unrecognized column', out.getvalue())

        call_command('ingest', stdout=StringIO(), stderr=StringIO())

        # The template defines two models (fra001 with 2 curves, fra002 with 1).
        self.assertEqual(
            FragilityModel.objects.filter(model_id__in=['fra001', 'fra002']).count(),
            2,
        )
        fra001 = FragilityModel.objects.get(model_id='fra001')
        self.assertEqual(
            FragilityCurve.objects.filter(fragility_model=fra001).count(), 2
        )
        # fra001 lists two component links; fra002 lists one.
        self.assertEqual(
            ComponentFragilityModelBridge.objects.filter(
                fragility_model=fra001
            ).count(),
            2,
        )

    # -- Tier 1.2: drift guard — accepted columns vs template header ----

    def test_template_headers_are_all_recognized_columns(self):
        from ned_app.management.commands.import_fragility import _expected_columns

        columns, _ = import_utils.read_csv(FRAGILITY_TEMPLATE)
        unknown = import_utils.find_unknown_columns(columns, _expected_columns())
        self.assertEqual(
            unknown, [], f'fragility template has unrecognized columns: {unknown}'
        )

    # -- Tier 3: behaviors ---------------------------------------------

    def test_consistency_check_aborts_and_writes_nothing(self):
        # Two rows share (reference, model_id) but disagree on a model-level
        # field (comp_description) — the command must abort.
        header = (
            'reference,model_id,p58_fragility,comp_detail,material,size_class,'
            'comp_description,reviewer,source,edp_metric,edp_unit,component_ids,'
            'ds_rank,ds_description,median,beta,probability,basis,num_observations\n'
        )
        common = 'SMITH-2020-EXP,fra001,,Back-braced,CPVC,2 inch,'
        tail = (
            ',Reviewer,Literature,"Peak Floor Acceleration, horizontal",g,'
            'A.40.1.1,{rank},DS,{median},0.4,1.0,Experiment,30\n'
        )
        row1 = common + 'Description ONE' + tail.format(rank=1, median=0.5)
        row2 = common + 'Description TWO' + tail.format(rank=2, median=1.2)
        path = self._write_csv('inconsistent.csv', header + row1 + row2)

        err = StringIO()
        call_command(
            'import_fragility', input_file=path, stdout=StringIO(), stderr=err
        )
        self.assertIn('inconsistent', err.getvalue())
        # Nothing written for any of the three target files.
        self.assertFalse(os.path.exists(self._json_path('fragility_model.json')))

    def test_dry_run_writes_nothing(self):
        self._make_base_data()
        call_command(
            'import_fragility',
            input_file=FRAGILITY_TEMPLATE,
            dry_run=True,
            stdout=StringIO(),
        )
        self.assertFalse(os.path.exists(self._json_path('fragility_model.json')))
        self.assertFalse(os.path.exists(self._json_path('fragility_curve.json')))

    def test_duplicate_model_is_skipped(self):
        # Pre-seed the model PK so the template's fra001/fra002 dedupe logic
        # has something to skip against.
        with open(
            self._json_path('fragility_model.json'), 'w', encoding='utf-8'
        ) as f:
            json.dump([{'reference': 'SMITH-2020-EXP', 'model_id': 'fra001'}], f)

        out = StringIO()
        call_command('import_fragility', input_file=FRAGILITY_TEMPLATE, stdout=out)
        self.assertIn('Skipped 1 duplicate fragility model', out.getvalue())
        # Only fra002 is appended; fra001 was already present.
        model_ids = [r['model_id'] for r in self._read_json('fragility_model.json')]
        self.assertEqual(sorted(model_ids), ['fra001', 'fra002'])

    def test_non_numeric_ds_rank_does_not_crash(self):
        # A non-numeric ds_rank must convert (passing the raw value through)
        # rather than crashing; ingest reports the bad value later.
        header = (
            'reference,model_id,p58_fragility,comp_detail,material,size_class,'
            'comp_description,reviewer,source,edp_metric,edp_unit,component_ids,'
            'ds_rank,ds_description,median,beta,probability,basis,num_observations\n'
        )
        row = (
            'SMITH-2020-EXP,fraX,,Braced,CPVC,2 inch,Desc,Rev,Lit,'
            '"Peak Floor Acceleration, horizontal",g,A.40.1.1,'
            'one,Leak,0.5,0.4,1.0,Experiment,30\n'
        )
        path = self._write_csv('badrank.csv', header + row)

        call_command('import_fragility', input_file=path, stdout=StringIO())

        curves = self._read_json('fragility_curve.json')
        self.assertEqual(len(curves), 1)
        self.assertEqual(curves[0]['ds_rank'], 'one')
