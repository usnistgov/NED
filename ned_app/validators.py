"""
Custom validators for the NED application.
"""

import json
import os
from django.conf import settings
from django.core.exceptions import ValidationError


# Global variable to cache the labels for efficiency
_nistir_labels = None


def _load_nistir_labels():
    """
    Load the NISTIR labels from disk. Cache it globally for efficiency.

    Returns:
        dict: The NISTIR labels dictionary
    """
    global _nistir_labels

    if _nistir_labels is None:
        labels_path = os.path.join(
            settings.BASE_DIR, 'ned_app', 'schemas', 'nistir_labels.json'
        )

        try:
            with open(labels_path, 'r') as f:
                _nistir_labels = json.load(f)
        except FileNotFoundError:
            raise ValidationError(f'NISTIR labels file not found at {labels_path}')
        except json.JSONDecodeError as e:
            raise ValidationError(f'Invalid JSON in NISTIR labels file: {e}')

    return _nistir_labels


def validate_nistir_component_id(component_id):
    """
    Validate a NISTIR component ID against the flat labels dictionary.

    The validator checks if the 4-level hierarchical portion of a component ID
    (e.g., 'B.20.1.1') exists as a key in the labels dictionary.

    Args:
        component_id (str): The component ID to validate (e.g., 'A.10.1.1' or 'A.10.1.1.A')

    Raises:
        ValidationError: If the hierarchical ID is not found in the labels dictionary.
    """
    if not isinstance(component_id, str):
        raise ValidationError('Component ID must be a string')

    parts = component_id.split('.')

    if len(parts) < 4:
        raise ValidationError(
            f'Component ID "{component_id}" must have at least 4 NISTIR levels (e.g., A.10.1.1)'
        )

    # Construct the 4-level ID to check against the labels
    hierarchical_id = '.'.join(parts[:4])

    # Load the labels from the cache
    labels = _load_nistir_labels()

    # Perform a single, efficient check for the key's existence
    if hierarchical_id not in labels:
        raise ValidationError(
            f'Invalid component ID: The NISTIR ID "{hierarchical_id}" was not found in the taxonomy.'
        )
