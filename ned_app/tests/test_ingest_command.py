"""
Unit tests for the ingest management command.
"""

import os
import tempfile
import json
from django.test import TestCase
from django.core.management import call_command
from django.conf import settings
from ned_app.models import Component, Reference
from ned_app.serialization.data_files_processor import import_avail_data


class IngestCommandTest(TestCase):
    """Test cases for the ingest management command."""

    def setUp(self):
        """Set up test data and temporary files."""
        # Create temporary test data
        self.test_component_data = [
            {
                'component_id': 'B.20.1.1.A',
                'name': 'Test CFS Exterior Walls',
                'nistir_subelement': 'B2011',
            },
            {
                'component_id': 'D.20.2.2.A',
                'name': 'Test Domestic Water Piping',
                'nistir_subelement': 'D2022',
            },
        ]

        self.test_reference_data = [
            {
                'id': 'test-ref-001',
                'study_type': 'Experiment',
                'comp_type': 'Test Component Type',
                'pdf_saved': True,
                'csl_data': {
                    'type': 'article-journal',
                    'id': 'test-ref-001',
                    'title': 'Test Reference Article',
                    'author': [{'family': 'Smith', 'given': 'John'}],
                    'issued': {'date-parts': [[2023]]},
                },
            },
            {
                'id': 'test-ref-002',
                'study_type': 'Analytical Study',
                'comp_type': 'Another Test Component',
                'pdf_saved': False,
                'csl_data': {
                    'type': 'paper-conference',
                    'id': 'test-ref-002',
                    'title': 'Test Conference Paper',
                    'author': [
                        {'family': 'Doe', 'given': 'Jane'},
                        {'family': 'Johnson', 'given': 'Bob'},
                    ],
                    'issued': {'date-parts': [[2022]]},
                },
            },
        ]

    def test_ingest_command_populates_both_id_fields(self):
        """Test that ingest command correctly populates both component_id and id fields."""
        # Create temporary component data file
        temp_dir = tempfile.mkdtemp()
        component_file = os.path.join(temp_dir, 'component.json')

        with open(component_file, 'w') as f:
            json.dump(self.test_component_data, f)

        # Mock the file path by creating the expected directory structure
        os.makedirs(os.path.join(temp_dir, 'resources', 'data'), exist_ok=True)
        test_component_file = os.path.join(
            temp_dir, 'resources', 'data', 'component.json'
        )

        with open(test_component_file, 'w') as f:
            json.dump(self.test_component_data, f)

        # Temporarily change working directory and disable other data processing
        original_cwd = os.getcwd()
        with self.settings(BASE_DIR=temp_dir):
            # Temporarily disable other data processing to focus on components
            from ned_app.serialization import data_files_processor

            original_process_references = data_files_processor.PROCESS_REFERENCES
            original_process_fragility_models = (
                data_files_processor.PROCESS_FRAGILITY_MODELS
            )
            original_process_experiments = data_files_processor.PROCESS_EXPERIMENTS
            original_process_experiment_fragility_pairs = (
                data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS
            )
            original_process_fragility_curves = (
                data_files_processor.PROCESS_FRAGILITY_CURVES
            )

            try:
                # Change working directory to temp directory
                os.chdir(temp_dir)

                # Disable all processing except components
                data_files_processor.PROCESS_REFERENCES = False
                data_files_processor.PROCESS_FRAGILITY_MODELS = False
                data_files_processor.PROCESS_EXPERIMENTS = False
                data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS = False
                data_files_processor.PROCESS_FRAGILITY_CURVES = False

                # Run the ingest command
                call_command('ingest')

                # Verify components were created with correct fields
                components = Component.objects.all()
                self.assertEqual(components.count(), 2)

                # Check first component
                component1 = Component.objects.get(name='Test CFS Exterior Walls')
                self.assertEqual(
                    component1.component_id, 'B.20.1.1.A'
                )  # Dotted notation
                self.assertEqual(component1.id, 'B2011.A')  # Old-style concatenated

                # Check second component
                component2 = Component.objects.get(name='Test Domestic Water Piping')
                self.assertEqual(
                    component2.component_id, 'D.20.2.2.A'
                )  # Dotted notation
                self.assertEqual(component2.id, 'D2022.A')  # Old-style concatenated

                # Verify hierarchy fields are populated by the model's save() method
                self.assertEqual(component1.major_group, 'B - Shell')
                self.assertEqual(component1.group, '20 - Exterior Enclosure')
                self.assertEqual(component1.element, '1 - Exterior Walls')
                self.assertEqual(
                    component1.subelement, '1 - Exterior Wall Construction'
                )

            except Exception as e:
                self.fail(f'Ingest command failed: {e}')
            finally:
                # Restore original working directory
                os.chdir(original_cwd)

                # Restore original processing settings
                data_files_processor.PROCESS_REFERENCES = original_process_references
                data_files_processor.PROCESS_FRAGILITY_MODELS = (
                    original_process_fragility_models
                )
                data_files_processor.PROCESS_EXPERIMENTS = (
                    original_process_experiments
                )
                data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS = (
                    original_process_experiment_fragility_pairs
                )
                data_files_processor.PROCESS_FRAGILITY_CURVES = (
                    original_process_fragility_curves
                )

                # Clean up temporary files
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)

    def test_component_serializer_generates_old_style_id(self):
        """Test that ComponentSerializer correctly generates old-style ID from dotted notation."""
        from ned_app.serialization.serializer import ComponentSerializer

        test_data = {'component_id': 'B.20.1.1.A', 'name': 'Test Component'}

        serializer = ComponentSerializer(data=test_data)
        self.assertTrue(
            serializer.is_valid(), f'Serializer errors: {serializer.errors}'
        )

        component = serializer.save()

        # Verify both fields are set correctly
        self.assertEqual(component.component_id, 'B.20.1.1.A')  # Dotted notation
        self.assertEqual(component.id, 'B2011.A')  # Generated old-style ID
        self.assertEqual(component.name, 'Test Component')

    def test_component_serializer_handles_no_suffix(self):
        """Test that ComponentSerializer handles component IDs without suffixes."""
        from ned_app.serialization.serializer import ComponentSerializer

        test_data = {'component_id': 'A.10.1.1', 'name': 'Test Component No Suffix'}

        serializer = ComponentSerializer(data=test_data)
        self.assertTrue(
            serializer.is_valid(), f'Serializer errors: {serializer.errors}'
        )

        component = serializer.save()

        # Verify both fields are set correctly
        self.assertEqual(component.component_id, 'A.10.1.1')  # Dotted notation
        self.assertEqual(
            component.id, 'A1011'
        )  # Generated old-style ID without suffix
        self.assertEqual(component.name, 'Test Component No Suffix')

    def test_component_serializer_handles_multiple_suffix_parts(self):
        """Test that ComponentSerializer handles component IDs with multiple suffix parts."""
        from ned_app.serialization.serializer import ComponentSerializer

        test_data = {
            'component_id': 'B.20.1.1.A.B.C',
            'name': 'Test Component Multiple Suffixes',
        }

        serializer = ComponentSerializer(data=test_data)
        self.assertTrue(
            serializer.is_valid(), f'Serializer errors: {serializer.errors}'
        )

        component = serializer.save()

        # Verify both fields are set correctly
        self.assertEqual(component.component_id, 'B.20.1.1.A.B.C')  # Dotted notation
        self.assertEqual(
            component.id, 'B2011.A.B.C'
        )  # Generated old-style ID with multiple suffixes
        self.assertEqual(component.name, 'Test Component Multiple Suffixes')

    def test_ingest_command_creates_reference_objects(self):
        """Test that ingest command correctly creates Reference objects from reference.json."""
        # Create temporary reference data file
        temp_dir = tempfile.mkdtemp()
        reference_file = os.path.join(temp_dir, 'reference.json')

        with open(reference_file, 'w') as f:
            json.dump(self.test_reference_data, f)

        # Mock the file path by creating the expected directory structure
        os.makedirs(os.path.join(temp_dir, 'resources', 'data'), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, 'ned_app', 'schemas'), exist_ok=True)

        test_reference_file = os.path.join(
            temp_dir, 'resources', 'data', 'reference.json'
        )

        with open(test_reference_file, 'w') as f:
            json.dump(self.test_reference_data, f)

        # Copy CSL schema file to temporary directory
        import shutil

        original_schema_path = os.path.join(
            settings.BASE_DIR, 'ned_app', 'schemas', 'csl-data.json'
        )
        temp_schema_path = os.path.join(
            temp_dir, 'ned_app', 'schemas', 'csl-data.json'
        )
        shutil.copy2(original_schema_path, temp_schema_path)

        # Temporarily change working directory and disable other data processing
        original_cwd = os.getcwd()
        with self.settings(BASE_DIR=temp_dir):
            # Temporarily disable other data processing to focus on references
            from ned_app.serialization import data_files_processor

            original_process_components = data_files_processor.PROCESS_COMPONENTS
            original_process_fragility_models = (
                data_files_processor.PROCESS_FRAGILITY_MODELS
            )
            original_process_experiments = data_files_processor.PROCESS_EXPERIMENTS
            original_process_experiment_fragility_pairs = (
                data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS
            )
            original_process_fragility_curves = (
                data_files_processor.PROCESS_FRAGILITY_CURVES
            )

            try:
                # Change working directory to temp directory
                os.chdir(temp_dir)

                # Disable all processing except references
                data_files_processor.PROCESS_COMPONENTS = False
                data_files_processor.PROCESS_FRAGILITY_MODELS = False
                data_files_processor.PROCESS_EXPERIMENTS = False
                data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS = False
                data_files_processor.PROCESS_FRAGILITY_CURVES = False

                # Run the ingest command
                call_command('ingest')

                # Verify references were created with correct fields
                references = Reference.objects.all()
                self.assertEqual(references.count(), 2)

                # Check first reference
                reference1 = Reference.objects.get(id='test-ref-001')
                self.assertEqual(reference1.title, 'Test Reference Article')
                self.assertEqual(reference1.author, 'Smith')
                self.assertEqual(reference1.year, 2023)
                self.assertEqual(reference1.study_type, 'Experiment')
                self.assertEqual(reference1.comp_type, 'Test Component Type')
                self.assertTrue(reference1.pdf_saved)

                # Check second reference
                reference2 = Reference.objects.get(id='test-ref-002')
                self.assertEqual(reference2.title, 'Test Conference Paper')
                self.assertEqual(reference2.author, 'Doe and Johnson')
                self.assertEqual(reference2.year, 2022)
                self.assertEqual(reference2.study_type, 'Analytical Study')
                self.assertEqual(reference2.comp_type, 'Another Test Component')
                self.assertFalse(reference2.pdf_saved)

                # Verify CSL data is properly stored
                self.assertIsNotNone(reference1.csl_data)
                self.assertEqual(reference1.csl_data['type'], 'article-journal')
                self.assertEqual(reference2.csl_data['type'], 'paper-conference')

            except Exception as e:
                self.fail(f'Ingest command failed: {e}')
            finally:
                # Restore original working directory
                os.chdir(original_cwd)

                # Restore original processing settings
                data_files_processor.PROCESS_COMPONENTS = original_process_components
                data_files_processor.PROCESS_FRAGILITY_MODELS = (
                    original_process_fragility_models
                )
                data_files_processor.PROCESS_EXPERIMENTS = (
                    original_process_experiments
                )
                data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS = (
                    original_process_experiment_fragility_pairs
                )
                data_files_processor.PROCESS_FRAGILITY_CURVES = (
                    original_process_fragility_curves
                )

                # Clean up temporary files
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)

    def tearDown(self):
        """Clean up test data after each test."""
        Component.objects.all().delete()
        Reference.objects.filter(id__startswith='test-').delete()
