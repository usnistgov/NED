import os
import tempfile
import json
from decimal import Decimal
from django.test import TestCase
from django.core.management import call_command
from ned_app.models import (
    Reference,
    Component,
    Experiment,
    FragilityModel,
    ExperimentFragilityModelBridge,
    FragilityCurve,
)


class ExportDataCommandTest(TestCase):
    """Test cases for the export_data management command."""

    def setUp(self):
        """Set up test data for all models."""
        # Create a temporary directory for output files
        self.temp_dir = tempfile.mkdtemp()

        # Create Component
        self.component = Component.objects.create(
            id='B2011.A', component_id='B.20.1.1.A', name='Test Exterior Walls'
        )

        # Create Reference
        self.reference = Reference.objects.create(
            id='test-ref-001',
            study_type='Experiment',
            comp_type='Test Component Type',
            pdf_saved=True,
            csl_data={
                'type': 'article-journal',
                'id': 'test-ref-001',
                'title': 'Test Reference Article',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2023]]},
                'container-title': 'Journal of Building Engineering',
                'volume': '42',
                'page': '101-120',
                'DOI': '10.1234/test.2023.001',
            },
        )

        # Create Experiment
        self.experiment = Experiment.objects.create(
            id='test-exp-001',
            reference=self.reference,
            component=self.component,
            specimen='Test specimen',
            specimen_inspection_sequence='1st test',
            reviewer='Test reviewer',
            test_type='Dynamic, uniaxial',
            comp_detail='Detailed connection',
            material='Steel',
            size_class='Medium',
            loading_protocol='FEMA P-695',
            peak_test_amplitude='2.5% drift',
            location='University Test Lab',
            governing_design_standard='ASCE 7-16',
            design_objective='Life safety performance level',
            comp_description='Test component description',
            ds_description='Test damage state description',
            prior_damage='No prior damage',
            prior_damage_repaired='N/A',
            edp_metric='Story Drift Ratio',
            edp_unit='Ratio',
            edp_value=Decimal('0.01'),
            alt_edp_metric='Peak Floor Acceleration, horizontal',
            alt_edp_unit='g',
            alt_edp_value=Decimal('0.35'),
            ds_rank=2,
            ds_class='Consequential',
            notes='Test notes about the experiment.',
        )

        # Create FragilityModel
        self.fragility_model = FragilityModel.objects.create(
            id='test-fm-001',
            component=self.component,
            p58_fragility='B2011.001',
            comp_detail='Steel connection',
            material='Cold-formed steel',
            size_class='Medium',
            comp_description='Test fragility model description',
        )

        # Create ExperimentFragilityModelBridge
        self.bridge = ExperimentFragilityModelBridge.objects.create(
            experiment=self.experiment, fragility_model=self.fragility_model
        )

        # Create FragilityCurve
        self.fragility_curve = FragilityCurve.objects.create(
            fragility_model=self.fragility_model,
            reference=self.reference,
            reviewer='Test reviewer',
            source='Experimental data',
            basis='Experiment',
            num_observations=15,
            edp_metric='Story Drift Ratio',
            edp_unit='Ratio',
            ds_rank=1,
            ds_description='Test damage state description',
            median=Decimal('0.02'),
            beta=Decimal('0.5'),
            probability=Decimal('0.75'),
        )

    def test_export_data_command(self):
        """Test that export_data command exports JSON files for all models."""
        # Call the export_data command with the temp_dir as output directory
        call_command('export_data', output_dir=self.temp_dir)

        # Check that JSON files were created for each model
        expected_files = [
            'reference.json',
            'component.json',
            'experiment.json',
            'fragility_model.json',
            'experiment_fragility_model_bridge.json',
            'fragility_curve.json',
        ]

        for filename in expected_files:
            file_path = os.path.join(self.temp_dir, filename)

            # Assert file exists
            self.assertTrue(
                os.path.exists(file_path),
                f'Expected file {filename} was not created',
            )

            # Assert file is not empty
            self.assertGreater(
                os.path.getsize(file_path), 0, f'File {filename} is empty'
            )

            # Load and verify the file contents
            with open(file_path, 'r') as f:
                data = json.load(f)
                self.assertIsInstance(
                    data, list, f'Data in {filename} is not a list'
                )
                self.assertGreater(len(data), 0, f'No data in {filename}')

        # Verify reference data (source-of-truth fields)
        with open(os.path.join(self.temp_dir, 'reference.json'), 'r') as f:
            reference_data = json.load(f)
            self.assertEqual(len(reference_data), 1)
            ref_data = reference_data[0]

            # Positive assertions - required source-of-truth fields
            self.assertEqual(ref_data['id'], 'test-ref-001')
            self.assertIn('study_type', ref_data)
            self.assertEqual(ref_data['study_type'], 'Experiment')
            self.assertIn('comp_type', ref_data)
            self.assertEqual(ref_data['comp_type'], 'Test Component Type')
            self.assertIn('pdf_saved', ref_data)
            self.assertEqual(ref_data['pdf_saved'], True)
            self.assertIn('csl_data', ref_data)
            self.assertEqual(ref_data['csl_data']['id'], 'test-ref-001')
            self.assertEqual(ref_data['csl_data']['title'], 'Test Reference Article')
            self.assertEqual(ref_data['csl_data']['type'], 'article-journal')
            self.assertEqual(
                ref_data['csl_data']['container-title'],
                'Journal of Building Engineering',
            )
            self.assertEqual(ref_data['csl_data']['volume'], '42')
            self.assertEqual(ref_data['csl_data']['page'], '101-120')
            self.assertEqual(ref_data['csl_data']['DOI'], '10.1234/test.2023.001')
            self.assertIn('author', ref_data['csl_data'])
            self.assertIn('issued', ref_data['csl_data'])

            # Negative assertions - denormalized fields should be absent
            self.assertNotIn('author', ref_data)
            self.assertNotIn('year', ref_data)
            self.assertNotIn('title', ref_data)

        # Verify component data (source-of-truth fields)
        with open(os.path.join(self.temp_dir, 'component.json'), 'r') as f:
            component_data = json.load(f)
            self.assertEqual(len(component_data), 1)
            comp_data = component_data[0]

            # Positive assertions - required source-of-truth fields
            self.assertIn('component_id', comp_data)
            self.assertEqual(comp_data['component_id'], 'B.20.1.1.A')
            self.assertIn('name', comp_data)
            self.assertEqual(comp_data['name'], 'Test Exterior Walls')

            # Negative assertions - denormalized fields should be absent
            self.assertNotIn('id', comp_data)
            self.assertNotIn('major_group', comp_data)
            self.assertNotIn('group', comp_data)
            self.assertNotIn('element', comp_data)
            self.assertNotIn('subelement', comp_data)

        # Verify experiment data
        with open(os.path.join(self.temp_dir, 'experiment.json'), 'r') as f:
            experiment_data = json.load(f)
            self.assertEqual(len(experiment_data), 1)
            exp_data = experiment_data[0]

            # Positive assertions - required source-of-truth fields
            self.assertIn('id', exp_data)
            self.assertEqual(exp_data['id'], 'test-exp-001')
            self.assertIn('reference', exp_data)
            self.assertEqual(exp_data['reference'], 'test-ref-001')
            self.assertIn('component', exp_data)
            # Component should use component_id string value, not id
            self.assertEqual(exp_data['component'], 'B.20.1.1.A')

            # Verify all experiment fields are present
            self.assertIn('specimen', exp_data)
            self.assertEqual(exp_data['specimen'], 'Test specimen')
            self.assertIn('specimen_inspection_sequence', exp_data)
            self.assertEqual(exp_data['specimen_inspection_sequence'], '1st test')
            self.assertIn('reviewer', exp_data)
            self.assertEqual(exp_data['reviewer'], 'Test reviewer')
            self.assertIn('test_type', exp_data)
            self.assertEqual(exp_data['test_type'], 'Dynamic, uniaxial')
            self.assertIn('comp_detail', exp_data)
            self.assertEqual(exp_data['comp_detail'], 'Detailed connection')
            self.assertIn('material', exp_data)
            self.assertEqual(exp_data['material'], 'Steel')
            self.assertIn('size_class', exp_data)
            self.assertEqual(exp_data['size_class'], 'Medium')
            self.assertIn('loading_protocol', exp_data)
            self.assertEqual(exp_data['loading_protocol'], 'FEMA P-695')
            self.assertIn('peak_test_amplitude', exp_data)
            self.assertEqual(exp_data['peak_test_amplitude'], '2.5% drift')
            self.assertIn('location', exp_data)
            self.assertEqual(exp_data['location'], 'University Test Lab')
            self.assertIn('governing_design_standard', exp_data)
            self.assertEqual(exp_data['governing_design_standard'], 'ASCE 7-16')
            self.assertIn('design_objective', exp_data)
            self.assertEqual(
                exp_data['design_objective'], 'Life safety performance level'
            )
            self.assertIn('comp_description', exp_data)
            self.assertEqual(
                exp_data['comp_description'], 'Test component description'
            )
            self.assertIn('ds_description', exp_data)
            self.assertEqual(
                exp_data['ds_description'], 'Test damage state description'
            )
            self.assertIn('prior_damage', exp_data)
            self.assertEqual(exp_data['prior_damage'], 'No prior damage')
            self.assertIn('prior_damage_repaired', exp_data)
            self.assertEqual(exp_data['prior_damage_repaired'], 'N/A')
            self.assertIn('edp_metric', exp_data)
            self.assertEqual(exp_data['edp_metric'], 'Story Drift Ratio')
            self.assertIn('edp_unit', exp_data)
            self.assertEqual(exp_data['edp_unit'], 'Ratio')
            self.assertIn('edp_value', exp_data)
            self.assertEqual(float(exp_data['edp_value']), 0.01)
            self.assertIn('alt_edp_metric', exp_data)
            self.assertEqual(
                exp_data['alt_edp_metric'], 'Peak Floor Acceleration, horizontal'
            )
            self.assertIn('alt_edp_unit', exp_data)
            self.assertEqual(exp_data['alt_edp_unit'], 'g')
            self.assertIn('alt_edp_value', exp_data)
            self.assertEqual(float(exp_data['alt_edp_value']), 0.35)
            self.assertIn('ds_rank', exp_data)
            self.assertEqual(exp_data['ds_rank'], 2)
            self.assertIn('ds_class', exp_data)
            self.assertEqual(exp_data['ds_class'], 'Consequential')
            self.assertIn('notes', exp_data)
            self.assertEqual(exp_data['notes'], 'Test notes about the experiment.')

        # Verify fragility model data
        with open(os.path.join(self.temp_dir, 'fragility_model.json'), 'r') as f:
            fragility_model_data = json.load(f)
            self.assertEqual(len(fragility_model_data), 1)
            fm_data = fragility_model_data[0]

            # Positive assertions - required source-of-truth fields
            self.assertIn('id', fm_data)
            self.assertEqual(fm_data['id'], 'test-fm-001')
            self.assertIn('component', fm_data)
            # Foreign key should use component_id string value, not id
            self.assertEqual(fm_data['component'], 'B.20.1.1.A')

            # Verify all FragilityModel fields
            self.assertIn('p58_fragility', fm_data)
            self.assertEqual(fm_data['p58_fragility'], 'B2011.001')
            self.assertIn('comp_detail', fm_data)
            self.assertEqual(fm_data['comp_detail'], 'Steel connection')
            self.assertIn('material', fm_data)
            self.assertEqual(fm_data['material'], 'Cold-formed steel')
            self.assertIn('size_class', fm_data)
            self.assertEqual(fm_data['size_class'], 'Medium')
            self.assertIn('comp_description', fm_data)
            self.assertEqual(
                fm_data['comp_description'], 'Test fragility model description'
            )

        # Verify bridge data
        with open(
            os.path.join(self.temp_dir, 'experiment_fragility_model_bridge.json'),
            'r',
        ) as f:
            bridge_data = json.load(f)
            self.assertEqual(len(bridge_data), 1)
            bridge = bridge_data[0]

            # Positive assertions - required source-of-truth fields
            # Bridge model has just two fields: experiment and fragility_model
            self.assertIn('experiment', bridge)
            self.assertEqual(bridge['experiment'], 'test-exp-001')
            self.assertIn('fragility_model', bridge)
            self.assertEqual(bridge['fragility_model'], 'test-fm-001')

            # Check that there are only these two fields
            self.assertEqual(
                len(bridge.keys()),
                2,
                'ExperimentFragilityModelBridge should only have 2 fields',
            )

        # Verify fragility curve data
        with open(os.path.join(self.temp_dir, 'fragility_curve.json'), 'r') as f:
            curve_data = json.load(f)
            self.assertEqual(len(curve_data), 1)
            curve = curve_data[0]

            # Positive assertions - required source-of-truth fields
            self.assertIn('fragility_model', curve)
            self.assertEqual(curve['fragility_model'], 'test-fm-001')
            self.assertIn('reference', curve)
            self.assertEqual(curve['reference'], 'test-ref-001')
            self.assertIn('reviewer', curve)
            self.assertEqual(curve['reviewer'], 'Test reviewer')
            self.assertIn('source', curve)
            self.assertEqual(curve['source'], 'Experimental data')
            self.assertIn('basis', curve)
            self.assertEqual(curve['basis'], 'Experiment')
            self.assertIn('num_observations', curve)
            self.assertEqual(curve['num_observations'], 15)
            self.assertIn('edp_metric', curve)
            self.assertEqual(curve['edp_metric'], 'Story Drift Ratio')
            self.assertIn('edp_unit', curve)
            self.assertEqual(curve['edp_unit'], 'Ratio')
            self.assertIn('ds_rank', curve)
            self.assertEqual(curve['ds_rank'], 1)
            self.assertIn('ds_description', curve)
            self.assertEqual(
                curve['ds_description'], 'Test damage state description'
            )
            self.assertIn('median', curve)
            self.assertEqual(float(curve['median']), 0.02)
            self.assertIn('beta', curve)
            self.assertEqual(float(curve['beta']), 0.5)
            self.assertIn('probability', curve)
            self.assertEqual(float(curve['probability']), 0.75)

    def tearDown(self):
        """Clean up test data and temporary files."""
        # Delete test records
        FragilityCurve.objects.all().delete()
        ExperimentFragilityModelBridge.objects.all().delete()
        FragilityModel.objects.all().delete()
        Experiment.objects.all().delete()
        Reference.objects.all().delete()
        Component.objects.all().delete()

        # Clean up temporary directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
