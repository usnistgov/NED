"""
Custom validators for the NED application.
"""

import json
import os
import re
from django.conf import settings
from django.core.exceptions import ValidationError


def validate_reference_label(value):
    """
    Validate an optional reference label used to build a reference id.

    When set, the label replaces the first-author surname when deriving the
    reference id (e.g. 'FEMA_P58' -> 'FEMA_P58-2018'). Rules for a non-empty
    label: letters, digits, and underscores only -- no hyphens (the hyphen
    separates the label from the year) and no leading or trailing underscore;
    it must not be a bare year (the year is appended automatically); and it is
    capped at 100 characters (the same bound as the model column). An empty
    value is allowed; the normalized first-author surname is used instead.

    Args:
        value (str): The reference label to validate.

    Raises:
        ValidationError: If a non-empty label violates the rules.
    """
    if not value:
        return
    if not re.fullmatch(r'[A-Za-z0-9_]+', value):
        raise ValidationError(
            f'reference_label "{value}" may contain only letters, digits, and '
            f'underscores (no hyphens or spaces).'
        )
    if value.startswith('_') or value.endswith('_'):
        raise ValidationError(
            f'reference_label "{value}" must not start or end with an underscore.'
        )
    if re.fullmatch(r'[0-9]+', value):
        raise ValidationError(
            f'reference_label "{value}" must not be a bare year; the year is '
            f'appended automatically to form the reference id.'
        )
    if len(value) > 100:
        raise ValidationError(
            f'reference_label must be at most 100 characters (got {len(value)}).'
        )


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


def validate_positive(value):
    """
    Validate that a numeric value is strictly positive.

    Intended for physical quantities that cannot be zero or negative, such as a
    lognormal dispersion (beta). ``None`` is allowed so the check does not
    interfere with optional fields.

    Args:
        value: The numeric value to validate.

    Raises:
        ValidationError: If the value is not strictly greater than zero.
    """
    if value is not None and value <= 0:
        raise ValidationError(f'Value must be greater than zero, got {value}.')


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
