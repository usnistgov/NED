import json
import os
from unittest.mock import patch, mock_open, MagicMock
from django.test import TestCase
from ned_app.serialization.data_files_processor import (
    load_data,
    import_avail_data,
    REFERENCES_DATA_FILENAME,
)
from ned_app.serialization.custom_exceptions import (
    DataFileLoadError,
    DataFileDeserializationError,
)
from ned_app.models import Reference


class DataFilesProcessorTest(TestCase):
    """Test cases for data_files_processor.py functions."""

    def setUp(self):
        """Set up test data."""
        self.valid_reference_data = [
            {
                'id': 'test-data-001',
                'study_type': 'Experiment',
                'comp_type': 'Test Component',
                'pdf_saved': True,
                'csl_data': {
                    'type': 'article-journal',
                    'id': 'test-data-001',
                    'title': 'Test Article 1',
                    'author': [{'family': 'Smith', 'given': 'John'}],
                    'issued': {'date-parts': [[2023]]},
                },
            },
            {
                'id': 'test-data-002',
                'study_type': 'Analytical Study',
                'comp_type': 'Another Component',
                'pdf_saved': False,
                'csl_data': {
                    'type': 'paper-conference',
                    'id': 'test-data-002',
                    'title': 'Test Conference Paper',
                    'author': [
                        {'family': 'Doe', 'given': 'Jane'},
                        {'family': 'Johnson', 'given': 'Bob'},
                    ],
                    'issued': {'date-parts': [[2022]]},
                },
            },
        ]

    def test_load_data_success(self):
        """Test that load_data successfully loads valid JSON data."""
        json_data = json.dumps(self.valid_reference_data)

        with patch(
            'ned_app.serialization.data_files_processor.build_json_data_file_path'
        ) as mock_path:
            mock_path.return_value = '/fake/path/reference.json'

            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=json_data)):
                    result = load_data(REFERENCES_DATA_FILENAME)

                    self.assertEqual(result, self.valid_reference_data)

    def test_load_data_file_not_found(self):
        """Test that load_data handles missing files correctly."""
        with patch(
            'ned_app.serialization.data_files_processor.build_json_data_file_path'
        ) as mock_path:
            mock_path.return_value = '/fake/path/reference.json'

            with patch('os.path.exists', return_value=False):
                result = load_data(REFERENCES_DATA_FILENAME)
                self.assertIsNone(result)

    def test_load_data_json_decode_error(self):
        """Test that load_data handles invalid JSON gracefully."""
        invalid_json = '{ invalid json content'

        with patch(
            'ned_app.serialization.data_files_processor.build_json_data_file_path'
        ) as mock_path:
            mock_path.return_value = '/fake/path/reference.json'

            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=invalid_json)):
                    with self.assertRaises(DataFileLoadError) as context:
                        load_data(REFERENCES_DATA_FILENAME)

                    self.assertIn('JSONDecodeError', str(context.exception))

    def test_load_data_file_read_error(self):
        """Test that load_data handles file read errors."""
        with patch(
            'ned_app.serialization.data_files_processor.build_json_data_file_path'
        ) as mock_path:
            mock_path.return_value = '/fake/path/reference.json'

            with patch('os.path.exists', return_value=True):
                with patch(
                    'builtins.open', side_effect=FileNotFoundError('File not found')
                ):
                    with self.assertRaises(DataFileLoadError) as context:
                        load_data(REFERENCES_DATA_FILENAME)

                    self.assertIn('FileNotFoundError', str(context.exception))

    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_CURVES', False
    )
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS',
        False,
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_EXPERIMENTS', False)
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_MODELS', False
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_COMPONENTS', False)
    @patch('ned_app.serialization.data_files_processor.PROCESS_REFERENCES', True)
    def test_import_avail_data_success_with_csl_data(self):
        """Test that import_avail_data successfully processes data with csl_data."""
        with patch(
            'ned_app.serialization.data_files_processor.load_data'
        ) as mock_load:
            mock_load.return_value = self.valid_reference_data

            with patch(
                'ned_app.serialization.data_files_processor.ReferenceSerializer'
            ) as mock_serializer_class:
                # Mock serializer instance
                mock_serializer = MagicMock()
                mock_serializer.is_valid.return_value = True
                mock_reference = MagicMock()
                mock_reference.id = 'test-data-001'
                mock_serializer.save.return_value = mock_reference
                mock_serializer_class.return_value = mock_serializer

                # Mock schema validation
                with patch(
                    'builtins.open', mock_open(read_data='{"type": "array"}')
                ):
                    with patch('jsonschema.validate'):
                        import_avail_data()

                        # Verify that serializer was called for each reference
                        self.assertEqual(mock_serializer_class.call_count, 2)
                        self.assertEqual(mock_serializer.is_valid.call_count, 2)
                        self.assertEqual(mock_serializer.save.call_count, 2)

    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_CURVES', False
    )
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS',
        False,
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_EXPERIMENTS', False)
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_MODELS', False
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_COMPONENTS', False)
    @patch('ned_app.serialization.data_files_processor.PROCESS_REFERENCES', True)
    def test_import_avail_data_missing_csl_data_field(self):
        """Test that import_avail_data raises error when csl_data field is missing."""
        invalid_data = [
            {
                'id': 'test-invalid-001',
                'study_type': 'Experiment',
                'comp_type': 'Test Component',
                'pdf_saved': True,
                # Missing csl_data field
            }
        ]

        with patch(
            'ned_app.serialization.data_files_processor.load_data'
        ) as mock_load:
            mock_load.return_value = invalid_data

            with self.assertRaises(DataFileDeserializationError) as context:
                import_avail_data()

            self.assertIn(
                "missing required 'csl_data' field", str(context.exception)
            )
            self.assertIn('test-invalid-001', str(context.exception))

    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_CURVES', False
    )
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS',
        False,
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_EXPERIMENTS', False)
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_MODELS', False
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_COMPONENTS', False)
    @patch('ned_app.serialization.data_files_processor.PROCESS_REFERENCES', True)
    def test_import_avail_data_missing_id_field(self):
        """Test that import_avail_data handles missing id field gracefully."""
        invalid_data = [
            {
                # Missing id field
                'study_type': 'Experiment',
                'comp_type': 'Test Component',
                'pdf_saved': True,
                'csl_data': {'type': 'article-journal', 'title': 'Test Article'},
            }
        ]

        with patch(
            'ned_app.serialization.data_files_processor.load_data'
        ) as mock_load:
            mock_load.return_value = invalid_data

            with self.assertRaises(DataFileDeserializationError) as context:
                import_avail_data()

            self.assertIn(
                'Reference item missing required "id" field', str(context.exception)
            )

    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_CURVES', False
    )
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS',
        False,
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_EXPERIMENTS', False)
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_MODELS', False
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_COMPONENTS', False)
    @patch('ned_app.serialization.data_files_processor.PROCESS_REFERENCES', True)
    def test_import_avail_data_serializer_validation_error(self):
        """Test that import_avail_data handles serializer validation errors."""
        with patch(
            'ned_app.serialization.data_files_processor.load_data'
        ) as mock_load:
            mock_load.return_value = self.valid_reference_data

            with patch(
                'ned_app.serialization.data_files_processor.ReferenceSerializer'
            ) as mock_serializer_class:
                # Mock serializer with validation error
                mock_serializer = MagicMock()
                mock_serializer.is_valid.return_value = False
                mock_serializer.errors = {'csl_data': ['Invalid CSL data']}
                mock_serializer_class.return_value = mock_serializer

                with self.assertRaises(DataFileDeserializationError) as context:
                    import_avail_data()

                self.assertIn('validation error', str(context.exception))
                self.assertIn('Invalid CSL data', str(context.exception))

    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_CURVES', False
    )
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS',
        False,
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_EXPERIMENTS', False)
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_MODELS', False
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_COMPONENTS', False)
    @patch('ned_app.serialization.data_files_processor.PROCESS_REFERENCES', False)
    def test_import_avail_data_references_processing_disabled(self):
        """Test that import_avail_data skips processing when PROCESS_REFERENCES is False."""
        with patch(
            'ned_app.serialization.data_files_processor.load_data'
        ) as mock_load:
            with patch('builtins.print') as mock_print:
                import_avail_data()

                # Should not call load_data when processing is disabled
                mock_load.assert_not_called()

                # Should print bypass message
                mock_print.assert_any_call('processing references bypassed')

    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_CURVES', False
    )
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS',
        False,
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_EXPERIMENTS', False)
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_MODELS', False
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_COMPONENTS', False)
    @patch('ned_app.serialization.data_files_processor.PROCESS_REFERENCES', True)
    def test_import_avail_data_with_complex_csl_data(self):
        """Test import_avail_data with complex CSL data structures."""
        complex_data = [
            {
                'id': 'test-complex-001',
                'study_type': 'Experiment',
                'comp_type': 'Complex Component',
                'pdf_saved': True,
                'csl_data': {
                    'type': 'paper-conference',
                    'id': 'test-complex-001',
                    'title': 'Complex Conference Paper',
                    'author': [
                        {'family': 'Smith', 'given': 'John A.'},
                        {'family': 'Johnson', 'given': 'Mary B.'},
                        {'literal': 'Research Team'},
                    ],
                    'issued': {'date-parts': [[2023, 6, 15]]},
                    'container-title': 'International Conference',
                    'event-title': 'ICOT 2023',
                    'event-place': 'New York, USA',
                    'page': '123-145',
                    'DOI': '10.1000/test.doi',
                    'URL': 'https://example.com/paper',
                    'note': 'Original citation text',
                },
            }
        ]

        with patch(
            'ned_app.serialization.data_files_processor.load_data'
        ) as mock_load:
            mock_load.return_value = complex_data

            with patch(
                'ned_app.serialization.data_files_processor.ReferenceSerializer'
            ) as mock_serializer_class:
                mock_serializer = MagicMock()
                mock_serializer.is_valid.return_value = True
                mock_reference = MagicMock()
                mock_reference.id = 'test-complex-001'
                mock_serializer.save.return_value = mock_reference
                mock_serializer_class.return_value = mock_serializer

                with patch(
                    'builtins.open', mock_open(read_data='{"type": "array"}')
                ):
                    with patch('jsonschema.validate') as mock_validate:
                        mock_validate.return_value = None
                        import_avail_data()

                        # Verify serializer was called with complex data
                        mock_serializer_class.assert_called_once_with(
                            data=complex_data[0]
                        )
                        mock_serializer.is_valid.assert_called_once()
                        mock_serializer.save.assert_called_once()

    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_CURVES', False
    )
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS',
        False,
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_EXPERIMENTS', False)
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_MODELS', False
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_COMPONENTS', False)
    @patch('ned_app.serialization.data_files_processor.PROCESS_REFERENCES', True)
    def test_import_avail_data_empty_csl_data(self):
        """Test that import_avail_data handles empty csl_data."""
        data_with_empty_csl = [
            {
                'id': 'test-empty-001',
                'study_type': 'Experiment',
                'comp_type': 'Test Component',
                'pdf_saved': True,
                'csl_data': {},  # Empty csl_data
            }
        ]

        with patch(
            'ned_app.serialization.data_files_processor.load_data'
        ) as mock_load:
            mock_load.return_value = data_with_empty_csl

            with patch(
                'ned_app.serialization.data_files_processor.ReferenceSerializer'
            ) as mock_serializer_class:
                mock_serializer = MagicMock()
                mock_serializer.is_valid.return_value = False
                mock_serializer.errors = {'csl_data': ['Empty CSL data']}
                mock_serializer_class.return_value = mock_serializer

                with self.assertRaises(DataFileDeserializationError) as context:
                    import_avail_data()

                self.assertIn('validation error', str(context.exception))

    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_CURVES', False
    )
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS',
        False,
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_EXPERIMENTS', False)
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_MODELS', False
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_COMPONENTS', False)
    @patch('ned_app.serialization.data_files_processor.PROCESS_REFERENCES', True)
    def test_import_avail_data_integration_with_real_serializer(self):
        """Integration test with real ReferenceSerializer."""
        with patch(
            'ned_app.serialization.data_files_processor.load_data'
        ) as mock_load:
            mock_load.return_value = self.valid_reference_data

            # This should work with real serializer and schema
            try:
                import_avail_data()

                # Verify that references were created
                created_refs = Reference.objects.filter(id__startswith='test-data-')
                self.assertEqual(created_refs.count(), 2)

                # Verify field population
                ref1 = Reference.objects.get(id='test-data-001')
                self.assertEqual(ref1.title, 'Test Article 1')
                self.assertEqual(ref1.author, 'Smith')
                self.assertEqual(ref1.year, 2023)

                ref2 = Reference.objects.get(id='test-data-002')
                self.assertEqual(ref2.title, 'Test Conference Paper')
                self.assertEqual(ref2.author, 'Doe and Johnson')
                self.assertEqual(ref2.year, 2022)

            except Exception as e:
                self.fail(f'Integration test failed: {e}')

    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_CURVES', False
    )
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_EXPERIMENT_FRAGILITY_PAIRS',
        False,
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_EXPERIMENTS', False)
    @patch(
        'ned_app.serialization.data_files_processor.PROCESS_FRAGILITY_MODELS', False
    )
    @patch('ned_app.serialization.data_files_processor.PROCESS_COMPONENTS', False)
    def test_csl_data_field_requirement_enforcement(self):
        """Test that the csl_data field requirement is properly enforced."""
        test_cases = [
            # Case 1: Missing csl_data key entirely
            {
                'data': {'id': 'test-001', 'study_type': 'Experiment'},
                'should_fail': True,
                'error_contains': "missing required 'csl_data' field",
            },
            # Case 2: csl_data is None
            {
                'data': {'id': 'test-002', 'csl_data': None},
                'should_fail': True,
                'error_contains': "missing required 'csl_data' field",
            },
            # Case 3: Valid csl_data
            {
                'data': {
                    'id': 'test-003',
                    'csl_data': {
                        'type': 'article-journal',
                        'id': 'test-003',
                        'title': 'Valid Article',
                    },
                },
                'should_fail': False,
                'error_contains': None,
            },
        ]

        for i, case in enumerate(test_cases):
            with self.subTest(case=i):
                with patch(
                    'ned_app.serialization.data_files_processor.load_data'
                ) as mock_load:
                    mock_load.return_value = [case['data']]

                    with patch(
                        'ned_app.serialization.data_files_processor.PROCESS_REFERENCES',
                        True,
                    ):
                        if case['should_fail']:
                            with self.assertRaises(
                                DataFileDeserializationError
                            ) as context:
                                import_avail_data()

                            if case['error_contains']:
                                self.assertIn(
                                    case['error_contains'], str(context.exception)
                                )
                        else:
                            # Mock successful serializer for valid case
                            with patch(
                                'ned_app.serialization.data_files_processor.ReferenceSerializer'
                            ) as mock_serializer_class:
                                mock_serializer = MagicMock()
                                mock_serializer.is_valid.return_value = True
                                mock_reference = MagicMock()
                                mock_reference.id = case['data']['id']
                                mock_serializer.save.return_value = mock_reference
                                mock_serializer_class.return_value = mock_serializer

                                with patch(
                                    'builtins.open',
                                    mock_open(read_data='{"type": "array"}'),
                                ):
                                    with patch('jsonschema.validate'):
                                        # Should not raise an exception
                                        import_avail_data()

    def tearDown(self):
        """Clean up test data after each test."""
        Reference.objects.filter(id__startswith='test-').delete()
