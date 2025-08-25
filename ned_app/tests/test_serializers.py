import json
import os
from unittest.mock import patch, mock_open
from django.test import TestCase
from django.conf import settings
from rest_framework.exceptions import ValidationError
from ned_app.serialization.serializer import ReferenceSerializer
from ned_app.models import Reference


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

                # Check that fields are auto-populated from csl_data
                self.assertEqual(reference.title, 'Test Article for Serializer')
                self.assertEqual(reference.author, 'Smith and Doe')
                self.assertEqual(reference.year, 2023)

    def test_serializer_handles_optional_fields(self):
        """Test that serializer handles optional auto-populated fields correctly."""
        # Test data with required fields
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

                # The model's save() method should override with csl_data title
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

        # This should work with the real schema
        self.assertTrue(serializer.is_valid())

        # Test with invalid data against real schema
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

        # Check that the serializer is configured for the Reference model
        self.assertEqual(serializer.Meta.model, Reference)

        # Check that required fields are properly configured
        self.assertIn('csl_data', serializer.fields)
        self.assertIn('title', serializer.fields)
        self.assertIn('author', serializer.fields)
        self.assertIn('year', serializer.fields)

        # Check that auto-populated fields are optional
        self.assertFalse(serializer.fields['title'].required)
        self.assertFalse(serializer.fields['author'].required)
        self.assertFalse(serializer.fields['year'].required)

        # Check that csl_data field is required
        self.assertTrue(serializer.fields['csl_data'].required)

    def tearDown(self):
        """Clean up test data after each test."""
        Reference.objects.filter(id__startswith='test-').delete()
