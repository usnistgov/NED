import json
import os
from django.test import TestCase
from django.conf import settings


class NistirConfigurationTest(TestCase):
    """
    Test case to verify the integrity and synchronization of NISTIR configuration files.
    """

    def test_nistir_schema_and_labels_synchronization(self):
        """
        Test that nistir_schema.json and nistir_labels.json are perfectly synchronized.

        This test verifies that:
        1. Both files can be loaded successfully
        2. The complete set of keys from the nested schema structure matches
           the set of keys from the flat labels structure
        """
        # Define file paths
        schema_path = os.path.join(
            settings.BASE_DIR, 'ned_app', 'schemas', 'nistir_schema.json'
        )
        labels_path = os.path.join(
            settings.BASE_DIR, 'ned_app', 'data', 'nistir_labels.json'
        )

        # Verify files exist
        self.assertTrue(
            os.path.exists(schema_path), f'Schema file not found: {schema_path}'
        )
        self.assertTrue(
            os.path.exists(labels_path), f'Labels file not found: {labels_path}'
        )

        # Load both files
        with open(schema_path, 'r') as f:
            schema_data = json.load(f)

        with open(labels_path, 'r') as f:
            labels_data = json.load(f)

        # Extract all keys from the nested schema structure
        schema_keys = self._extract_all_keys_from_schema(schema_data)

        # Extract all keys from the flat labels structure
        labels_keys = set(labels_data.keys())

        # Assert that the key sets are identical
        self.assertEqual(
            schema_keys,
            labels_keys,
            f'Schema keys and labels keys are not synchronized.\n'
            f'Keys in schema but not in labels: {schema_keys - labels_keys}\n'
            f'Keys in labels but not in schema: {labels_keys - schema_keys}',
        )

        # Additional verification: ensure we have a reasonable number of keys
        self.assertGreater(
            len(schema_keys), 0, 'Schema should contain at least one key'
        )
        self.assertGreater(
            len(labels_keys), 0, 'Labels should contain at least one key'
        )

    def _extract_all_keys_from_schema(
        self, schema_dict, keys_set=None, path_parts=None
    ):
        """
        Recursively extract all dotted keys from the schema structure.

        Args:
            schema_dict (dict): The schema dictionary to traverse
            keys_set (set): Accumulator for keys (used in recursion)
            path_parts (list): Current path components for building dotted keys

        Returns:
            set: All dotted keys found in the nested structure
        """
        if keys_set is None:
            keys_set = set()
        if path_parts is None:
            path_parts = []

        for key, value in schema_dict.items():
            # Build the current path
            current_path = path_parts + [key]

            # Create dotted key from current path
            dotted_key = '.'.join(current_path)
            keys_set.add(dotted_key)

            # If the value is a dictionary, recursively process it
            if isinstance(value, dict) and value:
                self._extract_all_keys_from_schema(value, keys_set, current_path)

        return keys_set
