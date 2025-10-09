"""
Unit tests for the ingest management command.
"""

import os
import tempfile
import json
from io import StringIO
from unittest.mock import patch
from django.test import TransactionTestCase
from django.core.management import call_command
from django.conf import settings
from ned_app.models import (
    Component,
    Reference,
    Experiment,
    FragilityModel,
    ExperimentFragilityModelBridge,
    FragilityCurve,
)


class IngestCommandTests(TransactionTestCase):
    """Test cases for the ingest management command."""

    def test_full_ingestion_success(self):
        """Test successful end-to-end ingestion of all six models."""
        # Create temporary directory for test data files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Prepare test data for all six models
            reference_data = [
                {
                    'id': 'ref-001',
                    'study_type': 'Experiment',
                    'comp_type': 'Structural Component',
                    'pdf_saved': True,
                    'csl_data': {
                        'type': 'article-journal',
                        'id': 'ref-001',
                        'title': 'Experimental Study of Building Components',
                        'author': [{'family': 'Smith', 'given': 'John'}],
                        'issued': {'date-parts': [[2020]]},
                    },
                },
                {
                    'id': 'ref-002',
                    'study_type': 'Analytical Study',
                    'comp_type': 'Mechanical Component',
                    'pdf_saved': False,
                    'csl_data': {
                        'type': 'paper-conference',
                        'id': 'ref-002',
                        'title': 'Analysis of Component Fragility',
                        'author': [
                            {'family': 'Doe', 'given': 'Jane'},
                            {'family': 'Johnson', 'given': 'Bob'},
                        ],
                        'issued': {'date-parts': [[2021]]},
                    },
                },
            ]

            component_data = [
                {
                    'component_id': 'B.20.1.1.A',
                    'name': 'CFS Exterior Walls',
                },
                {
                    'component_id': 'D.30.3.2.B',
                    'name': 'Water Heater',
                },
            ]

            fragility_model_data = [
                {
                    'id': 'fm-001',
                    'component': 'B.20.1.1.A',
                    'p58_fragility': 'B2011.001',
                    'comp_detail': 'Standard attachment',
                    'material': 'Steel',
                    'comp_description': 'Cold-formed steel exterior wall system',
                },
                {
                    'id': 'fm-002',
                    'component': 'D.30.3.2.B',
                    'p58_fragility': '',
                    'comp_detail': 'Anchored',
                    'material': 'Steel tank',
                    'comp_description': 'Residential water heater',
                },
            ]

            experiment_data = [
                {
                    'id': 'exp-001',
                    'reference': 'ref-001',
                    'component': 'B.20.1.1.A',
                    'specimen': 'Specimen-A',
                    'test_type': 'Quasi-static Cyclic, uniaxial',
                    'comp_description': 'CFS wall panel test',
                    'ds_description': 'Buckling of studs',
                    'edp_metric': 'Story Drift Ratio',
                    'edp_unit': 'Ratio',
                    'edp_value': '0.025',
                    'ds_class': 'Consequential',
                },
                {
                    'id': 'exp-002',
                    'reference': 'ref-001',
                    'component': 'D.30.3.2.B',
                    'specimen': 'Specimen-B',
                    'test_type': 'Dynamic, uniaxial',
                    'comp_description': 'Water heater shake table test',
                    'ds_description': 'Tank rupture',
                    'edp_metric': 'Peak Floor Acceleration, horizontal',
                    'edp_unit': 'g',
                    'edp_value': '1.5',
                    'ds_class': 'Consequential',
                },
            ]

            bridge_data = [
                {
                    'experiment': 'exp-001',
                    'fragility_model': 'fm-001',
                },
                {
                    'experiment': 'exp-002',
                    'fragility_model': 'fm-002',
                },
            ]

            fragility_curve_data = [
                {
                    'fragility_model': 'fm-001',
                    'reference': 'ref-001',
                    'reviewer': 'Test Reviewer',
                    'source': 'Laboratory Testing',
                    'basis': 'Experiment',
                    'num_observations': 10,
                    'edp_metric': 'Story Drift Ratio',
                    'edp_unit': 'Ratio',
                    'ds_rank': 1,
                    'ds_description': 'Minor cracking',
                    'median': '0.005',
                    'beta': '0.4',
                    'probability': '0.5',
                },
                {
                    'fragility_model': 'fm-001',
                    'reference': 'ref-002',
                    'reviewer': 'Test Reviewer',
                    'source': 'Analytical Model',
                    'basis': 'Analytical Study',
                    'num_observations': 5,
                    'edp_metric': 'Story Drift Ratio',
                    'edp_unit': 'Ratio',
                    'ds_rank': 2,
                    'ds_description': 'Severe damage',
                    'median': '0.02',
                    'beta': '0.5',
                    'probability': '0.5',
                },
                {
                    'fragility_model': 'fm-002',
                    'reference': 'ref-002',
                    'reviewer': 'Test Reviewer',
                    'source': 'Field Observation',
                    'basis': 'Historical Event',
                    'num_observations': 15,
                    'edp_metric': 'Peak Floor Acceleration, horizontal',
                    'edp_unit': 'g',
                    'ds_rank': 1,
                    'ds_description': 'Leakage',
                    'median': '0.8',
                    'beta': '0.3',
                    'probability': '1.0',
                },
            ]

            # Write JSON files to temporary directory
            files_data = {
                'reference.json': reference_data,
                'component.json': component_data,
                'fragility_model.json': fragility_model_data,
                'experiment.json': experiment_data,
                'experiment_fragility_model_bridge.json': bridge_data,
                'fragility_curve.json': fragility_curve_data,
            }

            for filename, data in files_data.items():
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    json.dump(data, f)

            # Mock build_json_data_file_path to return paths in temp directory
            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # Execute the ingest command
                call_command('ingest')

            # Assert correct object counts for all models
            self.assertEqual(Reference.objects.count(), 2)
            self.assertEqual(Component.objects.count(), 2)
            self.assertEqual(FragilityModel.objects.count(), 2)
            self.assertEqual(Experiment.objects.count(), 2)
            self.assertEqual(ExperimentFragilityModelBridge.objects.count(), 2)
            self.assertEqual(FragilityCurve.objects.count(), 3)

            # Assert foreign key relationships for Experiment
            exp_001 = Experiment.objects.get(id='exp-001')
            self.assertEqual(exp_001.reference.id, 'ref-001')
            self.assertEqual(exp_001.component.component_id, 'B.20.1.1.A')

            exp_002 = Experiment.objects.get(id='exp-002')
            self.assertEqual(exp_002.reference.id, 'ref-001')
            self.assertEqual(exp_002.component.component_id, 'D.30.3.2.B')

            # Assert foreign key relationships for FragilityModel
            fm_001 = FragilityModel.objects.get(id='fm-001')
            self.assertEqual(fm_001.component.component_id, 'B.20.1.1.A')

            fm_002 = FragilityModel.objects.get(id='fm-002')
            self.assertEqual(fm_002.component.component_id, 'D.30.3.2.B')

            # Assert foreign key relationships for ExperimentFragilityModelBridge
            bridge_1 = ExperimentFragilityModelBridge.objects.get(
                experiment__id='exp-001', fragility_model__id='fm-001'
            )
            self.assertEqual(bridge_1.experiment.id, 'exp-001')
            self.assertEqual(bridge_1.fragility_model.id, 'fm-001')

            bridge_2 = ExperimentFragilityModelBridge.objects.get(
                experiment__id='exp-002', fragility_model__id='fm-002'
            )
            self.assertEqual(bridge_2.experiment.id, 'exp-002')
            self.assertEqual(bridge_2.fragility_model.id, 'fm-002')

            # Assert foreign key relationships for FragilityCurve
            fc_1 = FragilityCurve.objects.get(
                fragility_model__id='fm-001', ds_rank=1
            )
            self.assertEqual(fc_1.fragility_model.id, 'fm-001')
            self.assertEqual(fc_1.reference.id, 'ref-001')

            fc_2 = FragilityCurve.objects.get(
                fragility_model__id='fm-001', ds_rank=2
            )
            self.assertEqual(fc_2.fragility_model.id, 'fm-001')
            self.assertEqual(fc_2.reference.id, 'ref-002')

            fc_3 = FragilityCurve.objects.get(
                fragility_model__id='fm-002', ds_rank=1
            )
            self.assertEqual(fc_3.fragility_model.id, 'fm-002')
            self.assertEqual(fc_3.reference.id, 'ref-002')

    def test_ingest_component_id_generation(self):
        """Test that Component id field is auto-generated from component_id."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test data for a single component
            component_data = [
                {
                    'component_id': 'B.20.1.1.A',
                    'name': 'CFS Exterior Walls',
                },
            ]

            # Write component.json file
            component_file = os.path.join(temp_dir, 'component.json')
            with open(component_file, 'w') as f:
                json.dump(component_data, f)

            # Mock build_json_data_file_path to return temp directory path
            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # Execute the ingest command
                call_command('ingest')

            # Retrieve the created Component object
            component = Component.objects.get(component_id='B.20.1.1.A')

            # Assert that the id field was auto-generated correctly
            # From 'B.20.1.1.A' to 'B2011.A'
            self.assertEqual(component.id, 'B2011.A')

    def test_ingest_reference_denormalized_fields(self):
        """Test that Reference denormalized fields are populated from csl_data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test data for a single reference
            reference_data = [
                {
                    'id': 'ref-001',
                    'study_type': 'Experiment',
                    'comp_type': 'Structural Component',
                    'pdf_saved': True,
                    'csl_data': {
                        'type': 'article-journal',
                        'id': 'ref-001',
                        'title': 'Experimental Study of Building Components',
                        'author': [{'family': 'Smith', 'given': 'John'}],
                        'issued': {'date-parts': [[2020]]},
                    },
                },
            ]

            # Write reference.json file
            reference_file = os.path.join(temp_dir, 'reference.json')
            with open(reference_file, 'w') as f:
                json.dump(reference_data, f)

            # Mock build_json_data_file_path to return temp directory path
            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # Execute the ingest command
                call_command('ingest')

            # Retrieve the created Reference object
            reference = Reference.objects.get(id='ref-001')

            # Assert that denormalized fields were populated from csl_data
            self.assertEqual(
                reference.title, 'Experimental Study of Building Components'
            )
            self.assertEqual(reference.author, 'Smith')
            self.assertEqual(reference.year, 2020)

    def test_ingest_handles_missing_file(self):
        """Test that the command handles missing files gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create only reference and component files, omit fragility_model
            reference_data = [
                {
                    'id': 'ref-001',
                    'study_type': 'Experiment',
                    'comp_type': 'Structural Component',
                    'pdf_saved': True,
                    'csl_data': {
                        'type': 'article-journal',
                        'id': 'ref-001',
                        'title': 'Test Study',
                        'author': [{'family': 'Smith', 'given': 'John'}],
                        'issued': {'date-parts': [[2020]]},
                    },
                },
            ]

            component_data = [
                {
                    'component_id': 'B.20.1.1.A',
                    'name': 'CFS Exterior Walls',
                },
            ]

            # Write only reference and component files
            reference_file = os.path.join(temp_dir, 'reference.json')
            with open(reference_file, 'w') as f:
                json.dump(reference_data, f)

            component_file = os.path.join(temp_dir, 'component.json')
            with open(component_file, 'w') as f:
                json.dump(component_data, f)

            # Intentionally do not create fragility_model.json

            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            stdout = StringIO()
            stderr = StringIO()

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # Execute the ingest command, capturing output
                call_command('ingest', stdout=stdout, stderr=stderr)

            # Assert the command completed without crashing
            stdout_value = stdout.getvalue()
            stderr_value = stderr.getvalue()
            self.assertEqual(stderr_value, '')

            # Assert warning for missing file is logged
            self.assertIn('File not found', stdout_value)
            self.assertIn('fragility_model.json', stdout_value)

            # Assert data from valid files was ingested
            self.assertEqual(Reference.objects.count(), 1)
            self.assertEqual(Component.objects.count(), 1)
            self.assertEqual(FragilityModel.objects.count(), 0)

    def test_ingest_handles_corrupt_json(self):
        """Test that the command handles corrupt JSON files gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a corrupt JSON file with invalid syntax
            component_file = os.path.join(temp_dir, 'component.json')
            with open(component_file, 'w') as f:
                f.write(
                    '[{"component_id": "B.20.1.1.A", "name": "Test",}]'
                )  # Trailing comma

            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            stdout = StringIO()
            stderr = StringIO()

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # Execute the ingest command, capturing output
                call_command('ingest', stdout=stdout, stderr=stderr)

            # Assert the command completed without crashing
            stderr_value = stderr.getvalue()

            # Assert error for JSONDecodeError is logged
            self.assertIn('Invalid JSON', stderr_value)
            self.assertIn('component.json', stderr_value)

            # Assert no database records were created from corrupt file
            self.assertEqual(Component.objects.count(), 0)

    def test_ingest_handles_validation_error(self):
        """Test that the command handles validation errors gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create reference data with one valid and one invalid record
            reference_data = [
                {
                    'id': 'ref-001',
                    'study_type': 'Experiment',
                    'comp_type': 'Structural Component',
                    'pdf_saved': True,
                    'csl_data': {
                        'type': 'article-journal',
                        'id': 'ref-001',
                        'title': 'Valid Study',
                        'author': [{'family': 'Smith', 'given': 'John'}],
                        'issued': {'date-parts': [[2020]]},
                    },
                },
                {
                    'id': 'ref-002',
                    'study_type': 'Analytical Study',
                    'comp_type': 'Mechanical Component',
                    'pdf_saved': False,
                    'csl_data': {
                        'type': 'article-journal',
                        'id': 'ref-002',
                        # Missing required field 'title' to trigger a ValidationError
                        'author': [{'family': 'Doe', 'given': 'Jane'}],
                        'issued': {'date-parts': [[2021]]},
                    },
                },
            ]

            reference_file = os.path.join(temp_dir, 'reference.json')
            with open(reference_file, 'w') as f:
                json.dump(reference_data, f)

            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            stdout = StringIO()
            stderr = StringIO()

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # Execute the ingest command, capturing output
                call_command('ingest', stdout=stdout, stderr=stderr)

            # Assert the command completed
            stderr_value = stderr.getvalue()

            # Assert error for validation failure is logged
            self.assertIn('Error processing Reference', stderr_value)
            self.assertIn('ref-002', stderr_value)

            # Assert valid record was saved, invalid was skipped
            self.assertEqual(Reference.objects.count(), 1)
            self.assertTrue(Reference.objects.filter(id='ref-001').exists())
            self.assertFalse(Reference.objects.filter(id='ref-002').exists())

    def test_ingest_handles_invalid_foreign_key(self):
        """Test that the command handles invalid foreign key references gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create component data
            component_data = [
                {
                    'component_id': 'B.20.1.1.A',
                    'name': 'CFS Exterior Walls',
                },
            ]

            # Create experiment data with invalid component_id reference
            experiment_data = [
                {
                    'id': 'exp-001',
                    'reference': 'ref-001',  # Non-existent reference
                    'component': 'INVALID.COMPONENT',  # Non-existent component
                    'specimen': 'Specimen-A',
                    'test_type': 'Quasi-static Cyclic, uniaxial',
                    'comp_description': 'Test',
                    'ds_description': 'Damage',
                    'edp_metric': 'Story Drift Ratio',
                    'edp_unit': 'Ratio',
                    'edp_value': '0.025',
                    'ds_class': 'Consequential',
                },
            ]

            component_file = os.path.join(temp_dir, 'component.json')
            with open(component_file, 'w') as f:
                json.dump(component_data, f)

            experiment_file = os.path.join(temp_dir, 'experiment.json')
            with open(experiment_file, 'w') as f:
                json.dump(experiment_data, f)

            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            stdout = StringIO()
            stderr = StringIO()

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # Execute the ingest command, capturing output
                call_command('ingest', stdout=stdout, stderr=stderr)

            # Assert the command completed
            stderr_value = stderr.getvalue()

            # Assert parent object was created
            self.assertEqual(Component.objects.count(), 1)
            self.assertTrue(
                Component.objects.filter(component_id='B.20.1.1.A').exists()
            )

            # Assert child object with invalid FK was not created
            self.assertEqual(Experiment.objects.count(), 0)

            # Assert validation error is logged
            self.assertIn('Error processing Experiment', stderr_value)
            self.assertIn('exp-001', stderr_value)

    def test_ingest_is_idempotent(self):
        """Test that running ingest multiple times doesn't create duplicates and updates changed records."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # --- 1. Initial Data Setup ---
            reference_data = [
                {
                    'id': 'ref-idem',
                    'study_type': 'Experiment',
                    'csl_data': {
                        'type': 'article-journal',
                        'id': 'ref-idem',
                        'title': 'Original Title',
                        'author': [{'family': 'Test', 'given': 'John'}],
                        'issued': {'date-parts': [[2025]]},
                    },
                }
            ]

            component_data = [{'component_id': 'A.10.1.1', 'name': 'Original Name'}]

            fragility_model_data = [
                {
                    'id': 'fm-idem',
                    'component': 'A.10.1.1',
                    'comp_description': 'Original FM Description',
                }
            ]

            experiment_data = [
                {
                    'id': 'exp-idem',
                    'reference': 'ref-idem',
                    'component': 'A.10.1.1',
                    'test_type': 'Quasi-static Cyclic, uniaxial',
                    'comp_description': 'A typical steel frame component.',
                    'ds_description': 'Original EXP Description',
                    'edp_metric': 'Story Drift Ratio',
                    'edp_unit': 'Ratio',
                    'edp_value': '0.015',
                    'ds_class': 'Consequential',
                }
            ]

            bridge_data = [{'experiment': 'exp-idem', 'fragility_model': 'fm-idem'}]

            fragility_curve_data = [
                {
                    'fragility_model': 'fm-idem',
                    'reference': 'ref-idem',
                    #'reviewer': 'Idempotency Test',
                    #'source': 'Laboratory Testing',
                    #'basis': 'Experiment',
                    #'num_observations': 20,
                    'edp_metric': 'Story Drift Ratio',
                    'edp_unit': 'Ratio',
                    'ds_rank': 1,
                    'ds_description': 'Original FC Description',
                    'median': '0.01',
                    'beta': '0.4',
                    #'probability': '1.0'
                }
            ]

            files_data = {
                'reference.json': reference_data,
                'component.json': component_data,
                'fragility_model.json': fragility_model_data,
                'experiment.json': experiment_data,
                'experiment_fragility_model_bridge.json': bridge_data,
                'fragility_curve.json': fragility_curve_data,
            }

            for filename, data in files_data.items():
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w') as f:
                    json.dump(data, f)

            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # --- 2. First Ingestion: Create Objects ---
                call_command('ingest', stdout=StringIO(), stderr=StringIO())

                # Assert initial objects were created
                self.assertEqual(Reference.objects.count(), 1)
                self.assertEqual(Component.objects.count(), 1)
                self.assertEqual(FragilityModel.objects.count(), 1)
                self.assertEqual(Experiment.objects.count(), 1)
                self.assertEqual(ExperimentFragilityModelBridge.objects.count(), 1)
                self.assertEqual(FragilityCurve.objects.count(), 1)

                # Verify initial data was loaded correctly
                ref = Reference.objects.get(id='ref-idem')
                self.assertEqual(ref.title, 'Original Title')

                comp = Component.objects.get(component_id='A.10.1.1')
                self.assertEqual(comp.name, 'Original Name')

                fm = FragilityModel.objects.get(id='fm-idem')
                self.assertEqual(fm.comp_description, 'Original FM Description')

                exp = Experiment.objects.get(id='exp-idem')
                self.assertEqual(exp.ds_description, 'Original EXP Description')

                # For the bridge, verify the relationship is correct
                bridge = ExperimentFragilityModelBridge.objects.get(
                    experiment=exp, fragility_model=fm
                )
                self.assertEqual(bridge.experiment.id, 'exp-idem')

                fc = FragilityCurve.objects.get(fragility_model=fm, ds_rank=1)
                self.assertEqual(fc.ds_description, 'Original FC Description')

                # --- 3. Second Ingestion: Same Data, Check for Duplicates ---
                call_command('ingest', stdout=StringIO(), stderr=StringIO())

                # Assert no duplicates were created
                self.assertEqual(Reference.objects.count(), 1)
                self.assertEqual(Component.objects.count(), 1)
                self.assertEqual(FragilityModel.objects.count(), 1)
                self.assertEqual(Experiment.objects.count(), 1)
                self.assertEqual(ExperimentFragilityModelBridge.objects.count(), 1)
                self.assertEqual(FragilityCurve.objects.count(), 1)

                # --- 4. Update Data and Files ---
                reference_data[0]['csl_data']['title'] = 'Updated Title'
                component_data[0]['name'] = 'Updated Name'
                fragility_model_data[0]['comp_description'] = (
                    'Updated FM Description'
                )
                experiment_data[0]['ds_description'] = 'Updated EXP Description'
                fragility_curve_data[0]['ds_description'] = 'Updated FC Description'

                for filename, data in files_data.items():
                    filepath = os.path.join(temp_dir, filename)
                    with open(filepath, 'w') as f:
                        json.dump(data, f)

                # --- 5. Third Ingestion: Update Objects ---
                call_command('ingest', stdout=StringIO(), stderr=StringIO())

                # Assert counts are still the same
                self.assertEqual(Reference.objects.count(), 1)
                self.assertEqual(Component.objects.count(), 1)
                self.assertEqual(FragilityModel.objects.count(), 1)
                self.assertEqual(Experiment.objects.count(), 1)
                self.assertEqual(ExperimentFragilityModelBridge.objects.count(), 1)
                self.assertEqual(FragilityCurve.objects.count(), 1)

                # --- 6. Verify Updates in Database ---
                ref = Reference.objects.get(id='ref-idem')
                ref.refresh_from_db()
                self.assertEqual(ref.title, 'Updated Title')

                comp = Component.objects.get(component_id='A.10.1.1')
                comp.refresh_from_db()
                self.assertEqual(comp.name, 'Updated Name')

                fm = FragilityModel.objects.get(id='fm-idem')
                fm.refresh_from_db()
                self.assertEqual(fm.comp_description, 'Updated FM Description')

                exp = Experiment.objects.get(id='exp-idem')
                exp.refresh_from_db()
                self.assertEqual(exp.ds_description, 'Updated EXP Description')

                fc = FragilityCurve.objects.get(
                    fragility_model__id='fm-idem', ds_rank=1
                )
                fc.refresh_from_db()
                self.assertEqual(fc.ds_description, 'Updated FC Description')

            # Assert objects were updated, not duplicated
            self.assertEqual(Reference.objects.count(), 1)
            self.assertEqual(Component.objects.count(), 1)

            ref.refresh_from_db()
            self.assertEqual(ref.csl_data['title'], 'Updated Title')
            self.assertEqual(ref.title, 'Updated Title')

            comp.refresh_from_db()
            self.assertEqual(comp.name, 'Updated Name')

    def test_ingest_handles_empty_data_file(self):
        """Test that the command handles empty data files (empty JSON list) gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty data files (empty JSON lists)
            empty_data = []

            reference_file = os.path.join(temp_dir, 'reference.json')
            with open(reference_file, 'w') as f:
                json.dump(empty_data, f)

            component_file = os.path.join(temp_dir, 'component.json')
            with open(component_file, 'w') as f:
                json.dump(empty_data, f)

            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            stdout = StringIO()
            stderr = StringIO()

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # Execute the ingest command, capturing output
                call_command('ingest', stdout=stdout, stderr=stderr)

            # Assert the command completed successfully
            stdout_value = stdout.getvalue()
            self.assertIn(
                'All data ingestion tasks completed successfully', stdout_value
            )

            # Assert no errors were logged
            stderr_value = stderr.getvalue()
            self.assertEqual(stderr_value, '')

            # Assert no objects were created
            self.assertEqual(Reference.objects.count(), 0)
            self.assertEqual(Component.objects.count(), 0)

    def test_ingest_handles_empty_data_directory(self):
        """Test that the command handles empty data directory (no files found) gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create empty temp directory with no data files

            def mock_build_path(filename):
                return os.path.join(temp_dir, filename)

            stdout = StringIO()
            stderr = StringIO()

            with patch(
                'ned_app.management.commands.ingest.build_json_data_file_path',
                side_effect=mock_build_path,
            ):
                # Execute the ingest command, capturing output
                call_command('ingest', stdout=stdout, stderr=stderr)

            # Assert the command completed successfully
            stdout_value = stdout.getvalue()
            self.assertIn(
                'All data ingestion tasks completed successfully', stdout_value
            )

            # Assert warnings were logged for missing files
            self.assertIn('File not found, skipping', stdout_value)

            # Assert no errors were logged
            stderr_value = stderr.getvalue()
            self.assertEqual(stderr_value, '')

            # Assert no objects were created
            self.assertEqual(Reference.objects.count(), 0)
            self.assertEqual(Component.objects.count(), 0)
            self.assertEqual(FragilityModel.objects.count(), 0)
            self.assertEqual(Experiment.objects.count(), 0)
            self.assertEqual(ExperimentFragilityModelBridge.objects.count(), 0)
            self.assertEqual(FragilityCurve.objects.count(), 0)
