"""
Custom validators for the NED application.
"""

import json
import os
from django.conf import settings
from django.core.exceptions import ValidationError


# Global variable to cache the schema for efficiency
_nistir_schema = None


def _load_nistir_schema():
    """
    Load the NISTIR schema from disk. Cache it globally for efficiency.

    Returns:
        dict: The NISTIR schema dictionary
    """
    global _nistir_schema

    if _nistir_schema is None:
        schema_path = os.path.join(
            settings.BASE_DIR, 'ned_app', 'schemas', 'nistir_schema.json'
        )

        try:
            with open(schema_path, 'r') as f:
                _nistir_schema = json.load(f)
        except FileNotFoundError:
            raise ValidationError(f'NISTIR schema file not found at {schema_path}')
        except json.JSONDecodeError as e:
            raise ValidationError(f'Invalid JSON in NISTIR schema file: {e}')

    return _nistir_schema


def validate_nistir_component_id(component_id):
    """
    Validate a NISTIR component ID against the hierarchical schema.

    The validation follows this specific hierarchical logic:
    1. The first character must exist as a top-level key
    2. The first three characters must exist as a key within the first level's object
    3. The first four characters plus a "0" must exist as a key within the second level's object
    4. The first five characters must exist as a key within the third level's object

    Args:
        component_id (str): The component ID to validate

    Raises:
        ValidationError: If the component ID is invalid at any hierarchical level
    """
    if not isinstance(component_id, str):
        raise ValidationError('Component ID must be a string')

    if len(component_id) < 5:
        raise ValidationError(
            f'Component ID "{component_id}" must be at least 5 characters long'
        )

    # Load the schema
    schema = _load_nistir_schema()

    # Step 1: Check first character (top-level key)
    first_char = component_id[0]
    if first_char not in schema:
        raise ValidationError(
            f'Invalid component ID "{component_id}": '
            f'first character "{first_char}" not found in NISTIR taxonomy'
        )

    # Step 2: Check first three characters (second level)
    first_three = component_id[:3]
    if first_three not in schema[first_char]:
        raise ValidationError(
            f'Invalid component ID "{component_id}": '
            f'group element "{first_three}" not found in NISTIR taxonomy'
        )

    # Step 3: Check first four characters plus "0" (third level)
    first_four_plus_zero = component_id[:4] + '0'
    if first_four_plus_zero not in schema[first_char][first_three]:
        raise ValidationError(
            f'Invalid component ID "{component_id}": '
            f'individual element "{first_four_plus_zero}" not found in NISTIR taxonomy'
        )

    # Step 4: Check first five characters (fourth level)
    first_five = component_id[:5]
    if first_five not in schema[first_char][first_three][first_four_plus_zero]:
        raise ValidationError(
            f'Invalid component ID "{component_id}": '
            f'sub-element "{first_five}" not found in NISTIR taxonomy'
        )
