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
        Test that known-valid component IDs pass validation without raising exceptions.
        """
        valid_ids = [
            'A1011',  # Valid: A -> A10 -> A1010 -> A1011
            'A1012',  # Valid: A -> A10 -> A1010 -> A1012
            'A1013',  # Valid: A -> A10 -> A1010 -> A1013
            'A2021',  # Valid: A -> A20 -> A2020 -> A2021
            'B1011',  # Valid: B -> B10 -> B1010 -> B1011
            'B2031',  # Valid: B -> B20 -> B2030 -> B2031
            'C1011',  # Valid: C -> C10 -> C1010 -> C1011
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
            'X1011',  # X not in top level
            'Z1011',  # Z not in top level
            '11011',  # Number not in top level
        ]

        for component_id in invalid_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                self.assertIn('first character', error_message)
                self.assertIn('not found in NISTIR taxonomy', error_message)

    def test_invalid_second_level(self):
        """
        Test that component IDs with valid first level but invalid second level raise ValidationError.
        """
        invalid_ids = [
            'A9011',  # A90 not in second level under A
            'B9011',  # B90 not in second level under B
            'C9011',  # C90 not in second level under C
        ]

        for component_id in invalid_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                self.assertIn('group element', error_message)
                self.assertIn('not found in NISTIR taxonomy', error_message)

    def test_invalid_third_level(self):
        """
        Test that component IDs with valid first two levels but invalid third level raise ValidationError.
        """
        invalid_ids = [
            'A1091',  # A1090 not in third level under A10
            'B1091',  # B1090 not in third level under B10
            'C1091',  # C1090 not in third level under C10
        ]

        for component_id in invalid_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                self.assertIn('individual element', error_message)
                self.assertIn('not found in NISTIR taxonomy', error_message)

    def test_invalid_fourth_level(self):
        """
        Test that component IDs with valid first three levels but invalid fourth level raise ValidationError.
        """
        invalid_ids = [
            'A1019',  # A1019 not in fourth level under A1010
            'B1017',  # B1017 not in fourth level under B1010
            'C1019',  # C1019 not in fourth level under C1010
        ]

        for component_id in invalid_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                self.assertIn('sub-element', error_message)
                self.assertIn('not found in NISTIR taxonomy', error_message)

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
        Test that component IDs shorter than 5 characters raise ValidationError.
        """
        short_ids = [
            '',  # Empty string
            'A',  # 1 character
            'A1',  # 2 characters
            'A10',  # 3 characters
            'A101',  # 4 characters
        ]

        for component_id in short_ids:
            with self.subTest(component_id=component_id):
                with self.assertRaises(ValidationError) as cm:
                    validate_nistir_component_id(component_id)

                error_message = str(cm.exception)
                self.assertIn('must be at least 5 characters long', error_message)

    def test_longer_component_ids(self):
        """
        Test that component IDs longer than 5 characters work correctly.
        The validator should only check the first 5 characters.
        """
        longer_valid_ids = [
            'A1011X',  # Valid first 5 chars: A1011
            'A1012ABC',  # Valid first 5 chars: A1012
            'B1011123',  # Valid first 5 chars: B1011
        ]

        for component_id in longer_valid_ids:
            with self.subTest(component_id=component_id):
                try:
                    validate_nistir_component_id(component_id)
                except ValidationError:
                    self.fail(
                        f'validate_nistir_component_id raised ValidationError '
                        f'unexpectedly for longer valid ID: {component_id}'
                    )
