import json
import os
from django.test import TestCase
from django.conf import settings


class NistirConfigurationTest(TestCase):
    """
    Test case to verify the hierarchical integrity of the NISTIR labels configuration.
    """

    def test_nistir_labels_hierarchical_integrity(self):
        """
        Verify that for every dotted key in nistir_labels.json, all ancestor keys exist.
        For example, for key 'A.10.1.1', the keys 'A.10.1', 'A.10', and 'A' must also exist.
        """
        labels_path = os.path.join(
            settings.BASE_DIR, 'ned_app', 'schemas', 'nistir_labels.json'
        )

        self.assertTrue(
            os.path.exists(labels_path), f'Labels file not found: {labels_path}'
        )

        with open(labels_path, 'r') as f:
            labels_data = json.load(f)

        labels_keys = set(labels_data.keys())

        self.assertGreater(
            len(labels_keys), 0, 'Labels should contain at least one key'
        )

        # For each key, validate that all ancestor keys exist
        for key in labels_keys:
            if '.' not in key:
                continue

            parts = key.split('.')
            # Check all ancestors from immediate parent up to the root
            for i in range(len(parts) - 1, 0, -1):
                parent_key = '.'.join(parts[:i])
                self.assertIn(
                    parent_key,
                    labels_keys,
                    f"Missing ancestor key '{parent_key}' for '{key}'",
                )
