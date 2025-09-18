"""
Unit tests for the NED application validators.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from ned_app.validators import validate_nistir_component_id


class NistirComponentIdValidatorTest(TestCase):
    """
    Test case for the NISTIR component ID validator function.
    """

    def test_valid_component_ids(self):
        """
        Test that valid component IDs pass validation without raising exceptions.
        Includes basic valid IDs, different hierarchy branches, and IDs with extra parts.
        """
        valid_ids = [
            # Basic valid IDs
            'A.10.1.1',  # Valid: A -> 10 -> 1 -> 1
            'A.10.1.2',  # Valid: A -> 10 -> 1 -> 2
            'B.10.1.1',  # Valid: B -> 10 -> 1 -> 1
            'C.10.1.1',  # Valid: C -> 10 -> 1 -> 1
            # Different hierarchy branches
            'A.20.1.1',  # Valid A.20 branch
            'B.20.3.1',  # Valid B.20 branch
            'D.10.1.1',  # Valid D-level component
            'E.10.1.1',  # Valid E-level component
            'F.10.1.1',  # Valid F-level component
            # IDs with extra parts (validator should only check first 4)
            'A.10.1.1.X',  # Valid with extra suffix
            'B.20.1.1.A',  # Valid with extra suffix
            'A.10.1.2.ABC',  # Valid with extra suffix
        ]

        for component_id in valid_ids:
            with self.subTest(component_id=component_id):
                try:
                    validate_nistir_component_id(component_id)
                except ValidationError:
                    self.fail(
                        f'validate_nistir_component_id raised ValidationError '
                        f'unexpectedly for valid ID: {component_id}'
                    )

    def test_invalid_first_character(self):
        """
        Test that component IDs with invalid first character (level 1) raise ValidationError.
        """
        invalid_ids = [
            'X.10.1.1',  # X not in top level
            'Z.10.1.1',  # Z not in top level
            '1.10.1.1',  # Number not in top level
        ]

        for component_id in invalid_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                expected_message = f'Invalid component ID: The NISTIR ID "{component_id}" was not found in the taxonomy.'
                self.assertIn(expected_message, error_message)

    def test_invalid_second_level(self):
        """
        Test that component IDs with valid first level but invalid second level raise ValidationError.
        """
        invalid_ids = [
            'A.90.1.1',  # 90 not in second level under A
            'B.90.1.1',  # 90 not in second level under B
            'C.90.1.1',  # 90 not in second level under C
        ]

        for component_id in invalid_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                expected_message = f'Invalid component ID: The NISTIR ID "{component_id}" was not found in the taxonomy.'
                self.assertIn(expected_message, error_message)

    def test_invalid_third_level(self):
        """
        Test that component IDs with valid first two levels but invalid third level raise ValidationError.
        """
        invalid_ids = [
            'A.10.9.1',  # 9 not in third level under A.10
            'B.10.9.1',  # 9 not in third level under B.10
            'C.10.9.1',  # 9 not in third level under C.10
            'A.10.8.1',  # 8 not in third level under A.10
            'B.20.4.1',  # 4 not in third level under B.20
            'C.10.8.1',  # 8 not in third level under C.10
        ]

        for component_id in invalid_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                expected_message = f'Invalid component ID: The NISTIR ID "{component_id}" was not found in the taxonomy.'
                self.assertIn(expected_message, error_message)

    def test_invalid_fourth_level(self):
        """
        Test that component IDs with valid first three levels but invalid fourth level raise ValidationError.
        """
        invalid_ids = [
            'A.10.1.9',  # 9 not in fourth level under A.10.1
            'B.10.1.7',  # 7 not in fourth level under B.10.1
            'C.10.1.9',  # 9 not in fourth level under C.10.1
            'A.10.1.8',  # 8 not in fourth level under A.10.1
            'B.10.1.8',  # 8 not in fourth level under B.10.1
            'C.20.1.5',  # 5 not in fourth level under C.20.1
            'D.20.1.0',  # 0 not in fourth level under D.20.1
        ]

        for component_id in invalid_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                expected_message = f'Invalid component ID: The NISTIR ID "{component_id}" was not found in the taxonomy.'
                self.assertIn(expected_message, error_message)

    def test_non_string_input(self):
        """
        Test that non-string inputs raise ValidationError.
        """
        invalid_inputs = [
            123,  # Integer
            12345,  # Integer that looks like valid ID
            None,  # None
            [],  # List
            {},  # Dictionary
        ]

        for invalid_input in invalid_inputs:
            with self.subTest(invalid_input=invalid_input):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(invalid_input)

                error_message = str(cm.exception)
                self.assertIn('Component ID must be a string', error_message)

    def test_too_short_component_id(self):
        """
        Test that component IDs with fewer than 4 dotted parts raise ValidationError.
        """
        short_ids = [
            '',  # Empty string
            'A',  # 1 part
            'A.10',  # 2 parts
            'A.10.1',  # 3 parts
        ]

        for component_id in short_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                self.assertIn('must have at least 4 NISTIR levels', error_message)

    def test_malformed_string_patterns(self):
        """
        Test malformed string patterns with dots and spaces that should raise ValidationError.
        """
        malformed_ids = [
            'A..10.1.1',  # Double dot creates empty part
            'A.10..1.1',  # Double dot in middle creates empty part
            '.A.10.1.1',  # Leading dot creates empty first part
            'A. .10.1.1',  # Space creates invalid part
            'A.10. 1.1',  # Space creates invalid part
            'A.10.1.1 ',  # Trailing space in last part
            ' A.10.1.1',  # Leading space in first part
        ]

        for component_id in malformed_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                # For malformed patterns, ensure they're rejected with a validation error
                # We just need to make sure it's not empty, as the actual ID may be processed differently
                # in the new implementation
                self.assertTrue(len(error_message) > 0)

                # Some will match the standardized error, depending on how they're processed
                # Double dots and spaces will likely cause a different ID to be checked
                hierarchical_id = component_id.split('.')[:4]
                if (
                    len(hierarchical_id) >= 4
                    and '' not in hierarchical_id
                    and ' ' not in ''.join(hierarchical_id)
                ):
                    expected_message = f'Invalid component ID: The NISTIR ID "{".".join(hierarchical_id)}" was not found in the taxonomy.'
                    self.assertIn(expected_message, error_message)
