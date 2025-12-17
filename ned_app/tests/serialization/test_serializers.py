import json
import os
from unittest.mock import patch, mock_open
from django.test import TestCase
from django.conf import settings
from rest_framework.exceptions import ValidationError
from ned_app.serialization.serializer import (
    ReferenceSerializer,
    ComponentSerializer,
    FragilityModelSerializer,
    ExperimentSerializer,
    ExperimentFragilityModelBridgeSerializer,
    FragilityCurveSerializer,
)
from ned_app.models import (
    Reference,
    Component,
    FragilityModel,
    Experiment,
    ExperimentFragilityModelBridge,
    FragilityCurve,
)


class ReferenceSerializerTest(TestCase):
    """Test cases for the ReferenceSerializer, focusing on validation logic."""

    def setUp(self):
        """Set up test data."""
        self.valid_csl_data = {
            'type': 'article-journal',
            'id': 'test-serializer-001',
            'title': 'Test Article for Serializer',
            'author': [
                {'family': 'Smith', 'given': 'John'},
                {'family': 'Doe', 'given': 'Jane'},
            ],
            'issued': {'date-parts': [[2023]]},
        }

        self.valid_reference_data = {
            'id': 'test-serializer-001',
            'csl_data': self.valid_csl_data,
            'study_type': 'Experiment',
            'comp_type': 'Test Component',
            'pdf_saved': True,
        }

    def test_serializer_accepts_valid_csl_data(self):
        """Test that serializer accepts valid CSL data."""
        serializer = ReferenceSerializer(data=self.valid_reference_data)

        with patch('builtins.open', mock_open(read_data='{"type": "array"}')):
            with patch('jsonschema.validate') as mock_validate:
                mock_validate.return_value = None  # No validation errors

                self.assertTrue(serializer.is_valid())
                self.assertEqual(
                    serializer.validated_data['csl_data'], self.valid_csl_data
                )

    def test_serializer_rejects_missing_csl_data(self):
        """Test that serializer rejects data without csl_data field."""
        invalid_data = self.valid_reference_data.copy()
        del invalid_data['csl_data']

        serializer = ReferenceSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('csl_data', serializer.errors)
        self.assertIn('required', str(serializer.errors['csl_data']))

    def test_serializer_rejects_null_csl_data(self):
        """Test that serializer rejects null csl_data."""
        invalid_data = self.valid_reference_data.copy()
        invalid_data['csl_data'] = None

        serializer = ReferenceSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('csl_data', serializer.errors)

    def test_serializer_rejects_empty_csl_data(self):
        """Test that serializer rejects empty csl_data."""
        invalid_data = self.valid_reference_data.copy()
        invalid_data['csl_data'] = {}

        serializer = ReferenceSerializer(data=invalid_data)

        with patch('builtins.open', mock_open(read_data='{"type": "array"}')):
            with patch('jsonschema.validate') as mock_validate:
                mock_validate.side_effect = Exception('Validation failed')

                self.assertFalse(serializer.is_valid())
                self.assertIn('csl_data', serializer.errors)

    def test_validate_csl_data_with_schema_validation_error(self):
        """Test that validate_csl_data handles schema validation errors."""
        serializer = ReferenceSerializer()

        invalid_csl_data = {
            'type': 'invalid-type',  # Invalid type
            'id': 'test-001',
            'title': 'Test Title',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'date-parts': [[2023]]},
        }

        with patch('builtins.open', mock_open(read_data='{"type": "array"}')):
            with patch('jsonschema.validate') as mock_validate:
                from jsonschema import ValidationError as JSONSchemaValidationError

                mock_validate.side_effect = JSONSchemaValidationError('Invalid type')

                with self.assertRaises(ValidationError) as context:
                    serializer.validate_csl_data(invalid_csl_data)

                self.assertIn('CSL data validation failed', str(context.exception))

    def test_validate_csl_data_with_missing_schema_file(self):
        """Test that validate_csl_data handles missing schema file."""
        serializer = ReferenceSerializer()

        with patch(
            'builtins.open', side_effect=FileNotFoundError('Schema not found')
        ):
            with self.assertRaises(ValidationError) as context:
                serializer.validate_csl_data(self.valid_csl_data)

            self.assertIn('CSL schema not found', str(context.exception))

    def test_serializer_creates_reference_successfully(self):
        """Test that serializer creates Reference object successfully."""
        serializer = ReferenceSerializer(data=self.valid_reference_data)

        with patch('builtins.open', mock_open(read_data='{"type": "array"}')):
            with patch('jsonschema.validate') as mock_validate:
                mock_validate.return_value = None

                self.assertTrue(serializer.is_valid())
                reference = serializer.save()

                self.assertIsInstance(reference, Reference)
                self.assertEqual(reference.id, 'test-serializer-001')
                self.assertEqual(reference.csl_data, self.valid_csl_data)

                self.assertEqual(reference.title, 'Test Article for Serializer')
                self.assertEqual(reference.author, 'Smith and Doe')
                self.assertEqual(reference.year, 2023)

    def test_serializer_handles_optional_fields(self):
        """Test that serializer handles optional auto-populated fields correctly."""
        minimal_data = {
            'id': 'test-serializer-002',
            'csl_data': {
                'type': 'article-journal',
                'id': 'test-serializer-002',
                'title': 'Minimal Test Article',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2023]]},
            },
        }

        serializer = ReferenceSerializer(data=minimal_data)

        with patch('builtins.open', mock_open(read_data='{"type": "array"}')):
            with patch('jsonschema.validate') as mock_validate:
                mock_validate.return_value = None

                self.assertTrue(serializer.is_valid())
                reference = serializer.save()

                self.assertEqual(reference.title, 'Minimal Test Article')
                self.assertEqual(
                    reference.author, 'Smith'
                )  # Should use csl_data value
                self.assertEqual(reference.year, 2023)  # Should use csl_data value

    def test_serializer_with_explicit_title_field(self):
        """Test that serializer works when title field is explicitly provided."""
        data_with_title = self.valid_reference_data.copy()
        data_with_title['title'] = 'Explicit Title'

        serializer = ReferenceSerializer(data=data_with_title)

        with patch('builtins.open', mock_open(read_data='{"type": "array"}')):
            with patch('jsonschema.validate') as mock_validate:
                mock_validate.return_value = None

                self.assertTrue(serializer.is_valid())
                reference = serializer.save()

                self.assertEqual(reference.title, 'Test Article for Serializer')

    def test_serializer_with_complex_csl_data(self):
        """Test serializer with complex CSL data including all supported fields."""
        complex_csl_data = {
            'type': 'paper-conference',
            'id': 'test-complex-001',
            'title': 'Complex Conference Paper',
            'author': [
                {'family': 'Smith', 'given': 'John A.'},
                {'family': 'Johnson', 'given': 'Mary B.'},
                {'literal': 'Research Team'},
            ],
            'issued': {'date-parts': [[2023, 6, 15]]},
            'container-title': 'International Conference on Testing',
            'event-title': 'ICOT 2023',
            'event-place': 'New York, USA',
            'page': '123-145',
            'DOI': '10.1000/test.doi',
            'URL': 'https://example.com/paper',
            'note': 'Original citation text here',
        }

        complex_data = {
            'id': 'test-complex-001',
            'csl_data': complex_csl_data,
            'study_type': 'Experiment',
        }

        serializer = ReferenceSerializer(data=complex_data)

        with patch('builtins.open', mock_open(read_data='{"type": "array"}')):
            with patch('jsonschema.validate') as mock_validate:
                mock_validate.return_value = None

                self.assertTrue(serializer.is_valid())
                reference = serializer.save()

                self.assertEqual(reference.title, 'Complex Conference Paper')
                self.assertEqual(reference.author, 'Smith et al.')  # 3+ authors
                self.assertEqual(reference.year, 2023)
                self.assertEqual(reference.csl_data, complex_csl_data)

    def test_serializer_validation_with_real_schema(self):
        """Test serializer validation against the actual CSL schema."""
        serializer = ReferenceSerializer(data=self.valid_reference_data)

        self.assertTrue(serializer.is_valid())

        invalid_data = self.valid_reference_data.copy()
        invalid_data['csl_data'] = {
            'type': 'invalid-type',  # This should fail real schema validation
            'id': 'test-001',
        }

        invalid_serializer = ReferenceSerializer(data=invalid_data)
        self.assertFalse(invalid_serializer.is_valid())

    def test_serializer_meta_configuration(self):
        """Test that serializer Meta configuration is correct."""
        serializer = ReferenceSerializer()

        self.assertEqual(serializer.Meta.model, Reference)

        self.assertIn('csl_data', serializer.fields)
        self.assertIn('title', serializer.fields)
        self.assertIn('author', serializer.fields)
        self.assertIn('year', serializer.fields)

        self.assertFalse(serializer.fields['title'].required)
        self.assertFalse(serializer.fields['author'].required)
        self.assertFalse(serializer.fields['year'].required)

        self.assertTrue(serializer.fields['csl_data'].required)

    def test_validate_csl_data_rejects_missing_title(self):
        """Test that serializer rejects csl_data without title field."""
        invalid_data = self.valid_reference_data.copy()
        invalid_data['csl_data'] = {
            'type': 'article-journal',
            'id': 'test-no-title',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'date-parts': [[2023]]},
        }

        serializer = ReferenceSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('csl_data', serializer.errors)

    def test_validate_csl_data_rejects_empty_title(self):
        """Test that serializer rejects csl_data with empty title string."""
        invalid_data = self.valid_reference_data.copy()
        invalid_data['csl_data'] = {
            'type': 'article-journal',
            'id': 'test-empty-title',
            'title': '',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'date-parts': [[2023]]},
        }

        serializer = ReferenceSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('csl_data', serializer.errors)

    def test_validate_csl_data_rejects_missing_author(self):
        """Test that serializer rejects csl_data without author field."""
        invalid_data = self.valid_reference_data.copy()
        invalid_data['csl_data'] = {
            'type': 'article-journal',
            'id': 'test-no-author',
            'title': 'Test Article',
            'issued': {'date-parts': [[2023]]},
        }

        serializer = ReferenceSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('csl_data', serializer.errors)

    def test_validate_csl_data_rejects_missing_issued(self):
        """Test that serializer rejects csl_data without issued field."""
        invalid_data = self.valid_reference_data.copy()
        invalid_data['csl_data'] = {
            'type': 'article-journal',
            'id': 'test-no-issued',
            'title': 'Test Article',
            'author': [{'family': 'Smith', 'given': 'John'}],
        }

        serializer = ReferenceSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('csl_data', serializer.errors)

    def test_validate_csl_data_rejects_invalid_issued_structure(self):
        """Test that serializer rejects csl_data with issued missing date-parts."""
        invalid_data = self.valid_reference_data.copy()
        invalid_data['csl_data'] = {
            'type': 'article-journal',
            'id': 'test-invalid-issued',
            'title': 'Test Article',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'raw': '2023'},
        }

        serializer = ReferenceSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('csl_data', serializer.errors)

    def tearDown(self):
        """Clean up test data after each test."""
        Reference.objects.filter(id__startswith='test-').delete()


class ComponentSerializerTest(TestCase):
    """Test cases for the ComponentSerializer, focusing on validation and ID auto-generation."""

    def test_serializer_creates_component_with_auto_generated_id(self):
        """Test that serializer creates a component with auto-generated ID from component_id."""
        valid_data = {
            'component_id': 'A.10.1.1',
            'name': 'Test Component',
        }

        serializer = ComponentSerializer(data=valid_data)

        self.assertTrue(serializer.is_valid())
        component = serializer.save()

        self.assertIsNotNone(component)
        self.assertEqual(component.component_id, 'A.10.1.1')
        self.assertEqual(component.name, 'Test Component')
        self.assertEqual(component.id, 'A1011')

    def test_serializer_rejects_missing_component_id(self):
        """Test that serializer rejects data missing the required component_id field."""
        invalid_data = {
            'name': 'Test Component',
        }

        serializer = ComponentSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('component_id', serializer.errors)

        with self.assertRaises(ValidationError):
            if not serializer.is_valid():
                raise ValidationError(serializer.errors)

    def test_serializer_rejects_invalid_component_id_format(self):
        """Test that serializer rejects component_id with invalid NISTIR format."""
        invalid_data = {
            'component_id': 'A.10.1',
            'name': 'Test Component',
        }

        serializer = ComponentSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('component_id', serializer.errors)

        with self.assertRaises(ValidationError):
            if not serializer.is_valid():
                raise ValidationError(serializer.errors)

    def test_serializer_populates_denormalized_nistir_fields(self):
        """Test that serializer correctly populates denormalized NISTIR fields from nistir_labels.json."""
        valid_data = {
            'component_id': 'D.30.3.2.B',
            'name': 'Test Water Heater',
        }

        serializer = ComponentSerializer(data=valid_data)

        self.assertTrue(serializer.is_valid())
        component = serializer.save()

        self.assertEqual(component.major_group, 'D - Services')
        self.assertEqual(component.group, '30 - HVAC')
        self.assertEqual(component.element, '3 - Cooling Generating Systems')
        self.assertEqual(component.subelement, '2 - Direct Expansion Systems')


class FragilityModelSerializerTest(TestCase):
    """Test cases for the FragilityModelSerializer, focusing on foreign key validation."""

    def setUp(self):
        """Set up test data."""
        self.component = Component.objects.create(
            component_id='A.10.1.1',
            name='Test Component',
        )

    def test_serializer_creates_fragility_model_with_valid_component(self):
        """Test that serializer successfully validates and saves with a valid component ID."""
        valid_data = {
            'id': 'test-fm-001',
            'component': 'A.10.1.1',
            'comp_description': 'Test fragility model description',
        }

        serializer = FragilityModelSerializer(data=valid_data)

        self.assertTrue(serializer.is_valid())
        fragility_model = serializer.save()

        self.assertIsNotNone(fragility_model)
        self.assertEqual(fragility_model.id, 'test-fm-001')
        self.assertEqual(fragility_model.component.component_id, 'A.10.1.1')

    def test_serializer_rejects_nonexistent_component(self):
        """Test that serializer rejects data with a non-existent component ID."""
        invalid_data = {
            'id': 'test-fm-002',
            'component': 'Z.99.9.9',
            'comp_description': 'Test fragility model description',
        }

        serializer = FragilityModelSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('component', serializer.errors)

    def tearDown(self):
        """Clean up test data after each test."""
        FragilityModel.objects.filter(id__startswith='test-fm-').delete()
        Component.objects.filter(component_id='A.10.1.1').delete()


class ExperimentSerializerTest(TestCase):
    """Test cases for the ExperimentSerializer, focusing on foreign key validation."""

    def setUp(self):
        """Set up test data."""
        self.component = Component.objects.create(
            component_id='A.10.1.1',
            name='Test Component',
        )

        self.reference = Reference.objects.create(
            id='test-ref-001',
            csl_data={
                'type': 'article-journal',
                'id': 'test-ref-001',
                'title': 'Test Reference',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2023]]},
            },
        )

    def test_serializer_creates_experiment_with_valid_foreign_keys(self):
        """Test that serializer successfully validates and saves with valid component and reference IDs."""
        valid_data = {
            'id': 'test-exp-001',
            'reference': 'test-ref-001',
            'component': 'A.10.1.1',
            'test_type': 'Quasi-static Cyclic, uniaxial',
            'comp_description': 'Test component description',
            'ds_description': 'Test damage state description',
            'edp_metric': 'Story Drift Ratio',
            'edp_unit': 'Ratio',
            'ds_class': 'Consequential',
        }

        serializer = ExperimentSerializer(data=valid_data)

        self.assertTrue(serializer.is_valid())
        experiment = serializer.save()

        self.assertIsNotNone(experiment)
        self.assertEqual(experiment.id, 'test-exp-001')
        self.assertEqual(experiment.reference.id, 'test-ref-001')
        self.assertEqual(experiment.component.component_id, 'A.10.1.1')

    def test_serializer_rejects_nonexistent_reference(self):
        """Test that serializer rejects data with a non-existent reference ID."""
        invalid_data = {
            'id': 'test-exp-002',
            'reference': 'nonexistent-ref',
            'component': 'A.10.1.1',
        }

        serializer = ExperimentSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('reference', serializer.errors)

    def test_serializer_rejects_nonexistent_component(self):
        """Test that serializer rejects data with a non-existent component ID."""
        invalid_data = {
            'id': 'test-exp-003',
            'reference': 'test-ref-001',
            'component': 'Z.99.9.9',
        }

        serializer = ExperimentSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('component', serializer.errors)

    def tearDown(self):
        """Clean up test data after each test."""
        Experiment.objects.filter(id__startswith='test-exp-').delete()
        Reference.objects.filter(id__startswith='test-ref-').delete()
        Component.objects.filter(component_id='A.10.1.1').delete()


class ExperimentFragilityModelBridgeSerializerTest(TestCase):
    """Test cases for the ExperimentFragilityModelBridgeSerializer, focusing on foreign key validation."""

    def setUp(self):
        """Set up test data."""
        self.component = Component.objects.create(
            component_id='A.10.1.1',
            name='Test Component',
        )

        self.reference = Reference.objects.create(
            id='test-ref-001',
            csl_data={
                'type': 'article-journal',
                'id': 'test-ref-001',
                'title': 'Test Reference',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2023]]},
            },
        )

        self.experiment = Experiment.objects.create(
            id='test-exp-001',
            reference=self.reference,
            component=self.component,
        )

        self.fragility_model = FragilityModel.objects.create(
            id='test-fm-001',
            component=self.component,
            comp_description='Test fragility model',
        )

    def test_serializer_creates_bridge_with_valid_foreign_keys(self):
        """Test that serializer successfully validates and saves with valid experiment and fragility_model IDs."""
        valid_data = {
            'experiment': 'test-exp-001',
            'fragility_model': 'test-fm-001',
        }

        serializer = ExperimentFragilityModelBridgeSerializer(data=valid_data)

        self.assertTrue(serializer.is_valid())
        bridge = serializer.save()

        self.assertIsNotNone(bridge)
        self.assertEqual(bridge.experiment.id, 'test-exp-001')
        self.assertEqual(bridge.fragility_model.id, 'test-fm-001')

    def test_serializer_rejects_nonexistent_experiment(self):
        """Test that serializer rejects data with a non-existent experiment ID."""
        invalid_data = {
            'experiment': 'nonexistent-exp',
            'fragility_model': 'test-fm-001',
        }

        serializer = ExperimentFragilityModelBridgeSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('experiment', serializer.errors)

    def test_serializer_rejects_nonexistent_fragility_model(self):
        """Test that serializer rejects data with a non-existent fragility_model ID."""
        invalid_data = {
            'experiment': 'test-exp-001',
            'fragility_model': 'nonexistent-fm',
        }

        serializer = ExperimentFragilityModelBridgeSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('fragility_model', serializer.errors)

    def tearDown(self):
        """Clean up test data after each test."""
        ExperimentFragilityModelBridge.objects.all().delete()
        FragilityModel.objects.filter(id__startswith='test-fm-').delete()
        Experiment.objects.filter(id__startswith='test-exp-').delete()
        Reference.objects.filter(id__startswith='test-ref-').delete()
        Component.objects.filter(component_id='A.10.1.1').delete()


class FragilityCurveSerializerTest(TestCase):
    """Test cases for the FragilityCurveSerializer, focusing on foreign key validation."""

    def setUp(self):
        """Set up test data."""
        self.component = Component.objects.create(
            component_id='A.10.1.1',
            name='Test Component',
        )

        self.reference = Reference.objects.create(
            id='test-ref-001',
            csl_data={
                'type': 'article-journal',
                'id': 'test-ref-001',
                'title': 'Test Reference',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2023]]},
            },
        )

        self.fragility_model = FragilityModel.objects.create(
            id='test-fm-001',
            component=self.component,
            comp_description='Test fragility model',
        )

    def test_serializer_creates_fragility_curve_with_valid_foreign_keys(self):
        """Test that serializer successfully validates and saves with valid fragility_model and reference IDs."""
        valid_data = {
            'fragility_model': 'test-fm-001',
            'reference': 'test-ref-001',
            'edp_metric': 'Story Drift Ratio',
            'edp_unit': 'Ratio',
            'ds_description': 'Test damage state description',
            'median': 0.01,
            'beta': 0.5,
            'probability': 0.8,
        }

        serializer = FragilityCurveSerializer(data=valid_data)

        self.assertTrue(serializer.is_valid())
        fragility_curve = serializer.save()

        self.assertIsNotNone(fragility_curve)
        self.assertEqual(fragility_curve.fragility_model.id, 'test-fm-001')
        self.assertEqual(fragility_curve.reference.id, 'test-ref-001')

    def test_serializer_rejects_nonexistent_fragility_model(self):
        """Test that serializer rejects data with a non-existent fragility_model ID."""
        invalid_data = {
            'fragility_model': 'nonexistent-fm',
            'reference': 'test-ref-001',
            'edp_metric': 'Story Drift Ratio',
            'edp_unit': 'Ratio',
            'ds_description': 'Test damage state description',
            'median': 0.01,
            'beta': 0.5,
            'probability': 0.8,
        }

        serializer = FragilityCurveSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('fragility_model', serializer.errors)

    def test_serializer_rejects_nonexistent_reference(self):
        """Test that serializer rejects data with a non-existent reference ID."""
        invalid_data = {
            'fragility_model': 'test-fm-001',
            'reference': 'nonexistent-ref',
            'edp_metric': 'Story Drift Ratio',
            'edp_unit': 'Ratio',
            'ds_description': 'Test damage state description',
            'median': 0.01,
            'beta': 0.5,
            'probability': 0.8,
        }

        serializer = FragilityCurveSerializer(data=invalid_data)

        self.assertFalse(serializer.is_valid())
        self.assertIn('reference', serializer.errors)

    def tearDown(self):
        """Clean up test data after each test."""
        FragilityCurve.objects.all().delete()
        FragilityModel.objects.filter(id__startswith='test-fm-').delete()
        Reference.objects.filter(id__startswith='test-ref-').delete()
        Component.objects.filter(component_id='A.10.1.1').delete()
