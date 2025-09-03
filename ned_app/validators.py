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

    The validator parses the 4-level NISTIR portion of a dotted ID string and
    traverses the NISTIR schema structure. For example, from 'B.20.1.1.A',
    it isolates the parts ['B', '20', '1', '1'] and validates each level exists.

    Args:
        component_id (str): The component ID to validate (e.g., 'A.10.1.1')

    Raises:
        ValidationError: If the component ID is invalid at any hierarchical level
    """
    if not isinstance(component_id, str):
        raise ValidationError('Component ID must be a string')

    # Parse the dotted ID to get the 4-level NISTIR parts
    parts = component_id.split('.')

    # We need at least 4 parts for a complete NISTIR ID
    if len(parts) < 4:
        raise ValidationError(
            f'Component ID "{component_id}" must have at least 4 NISTIR levels (e.g., A.10.1.1)'
        )

    # Extract the first 4 parts (NISTIR hierarchy)
    nistir_parts = parts[:4]

    # Load the schema
    schema = _load_nistir_schema()

    # Step 1: Check Level 1 (major group, e.g., 'A')
    level1_key = nistir_parts[0]
    if level1_key not in schema:
        raise ValidationError(
            f'Invalid component ID "{component_id}": '
            f'major group "{level1_key}" not found in NISTIR taxonomy'
        )

    # Step 2: Check Level 2 (group, e.g., '10')
    level2_key = nistir_parts[1]
    if level2_key not in schema[level1_key]:
        raise ValidationError(
            f'Invalid component ID "{component_id}": '
            f'group "{level2_key}" not found under major group "{level1_key}" in NISTIR taxonomy'
        )

    # Step 3: Check Level 3 (element, e.g., '1')
    level3_key = nistir_parts[2]
    if level3_key not in schema[level1_key][level2_key]:
        raise ValidationError(
            f'Invalid component ID "{component_id}": '
            f'element "{level3_key}" not found under group "{level1_key}.{level2_key}" in NISTIR taxonomy'
        )

    # Step 4: Check Level 4 (subelement, e.g., '1')
    level4_key = nistir_parts[3]
    if level4_key not in schema[level1_key][level2_key][level3_key]:
        raise ValidationError(
            f'Invalid component ID "{component_id}": '
            f'subelement "{level4_key}" not found under element "{level1_key}.{level2_key}.{level3_key}" in NISTIR taxonomy'
        )
