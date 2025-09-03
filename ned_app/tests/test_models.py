from django.test import TestCase
from django.core.exceptions import ValidationError
from ned_app.models import Reference, Component


class ReferenceModelTest(TestCase):
    """Test cases for the Reference model, focusing on the save() method logic."""

    def test_save_populates_title_from_csl_data(self):
        """Test that save() populates title field from csl_data."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-001',
            'title': 'Test Article Title',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-001', csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.title, 'Test Article Title')

    def test_save_populates_year_from_csl_data(self):
        """Test that save() populates year field from csl_data issued date-parts."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-002',
            'title': 'Test Article',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'date-parts': [[2022]]},
        }

        ref = Reference(id='test-002', csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.year, 2022)

    def test_save_populates_author_single_author(self):
        """Test that save() populates author field correctly for single author."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-003',
            'title': 'Single Author Paper',
            'author': [{'family': 'Johnson', 'given': 'Alice'}],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-003', csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.author, 'Johnson')

    def test_save_populates_author_two_authors(self):
        """Test that save() populates author field correctly for two authors."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-004',
            'title': 'Two Authors Paper',
            'author': [
                {'family': 'Smith', 'given': 'John'},
                {'family': 'Doe', 'given': 'Jane'},
            ],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-004', csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.author, 'Smith and Doe')

    def test_save_populates_author_three_or_more_authors(self):
        """Test that save() populates author field correctly for three or more authors."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-005',
            'title': 'Multiple Authors Paper',
            'author': [
                {'family': 'Smith', 'given': 'John'},
                {'family': 'Doe', 'given': 'Jane'},
                {'family': 'Johnson', 'given': 'Bob'},
                {'family': 'Brown', 'given': 'Alice'},
            ],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-005', csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.author, 'Smith et al.')

    def test_save_handles_literal_author_names(self):
        """Test that save() handles literal author names correctly."""
        csl_data = {
            'type': 'report',
            'id': 'test-006',
            'title': 'Report with Literal Author',
            'author': [{'literal': 'John Smith'}],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-006', csl_data=csl_data)
        ref.save()

        # Should extract last word from literal name
        self.assertEqual(ref.author, 'Smith')

    def test_save_handles_mixed_author_formats(self):
        """Test that save() handles mixed author formats (family/given and literal)."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-007',
            'title': 'Mixed Author Formats',
            'author': [
                {'family': 'Smith', 'given': 'John'},
                {'literal': 'Jane Doe'},
                {'family': 'Johnson', 'given': 'Bob'},
            ],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-007', csl_data=csl_data)
        ref.save()

        # Should use "et al." for 3+ authors
        self.assertEqual(ref.author, 'Smith et al.')

    def test_save_handles_missing_csl_data(self):
        """Test that save() raises ValidationError for missing csl_data."""
        ref = Reference(id='test-008')

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn(
            'csl_data is required and cannot be empty', str(context.exception)
        )

    def test_save_handles_empty_csl_data(self):
        """Test that save() raises ValidationError for empty csl_data."""
        ref = Reference(id='test-009', csl_data={})

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn(
            'csl_data is required and cannot be empty', str(context.exception)
        )

    def test_save_handles_missing_title_in_csl_data(self):
        """Test that save() raises ValidationError for missing title in csl_data."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-010',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-010', csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn(
            "csl_data must contain a non-empty 'title' field", str(context.exception)
        )

    def test_save_handles_missing_authors_in_csl_data(self):
        """Test that save() raises ValidationError for missing authors in csl_data."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-011',
            'title': 'No Authors Paper',
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-011', csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn(
            "csl_data must contain a non-empty 'author' field",
            str(context.exception),
        )

    def test_save_handles_empty_authors_list(self):
        """Test that save() raises ValidationError for empty authors list in csl_data."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-012',
            'title': 'Empty Authors List',
            'author': [],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-012', csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn(
            "csl_data must contain a non-empty 'author' field",
            str(context.exception),
        )

    def test_save_handles_malformed_date_parts(self):
        """Test that save() raises ValidationError for malformed date-parts in csl_data."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-013',
            'title': 'Malformed Date',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'date-parts': [[]]},  # Empty date parts
        }

        ref = Reference(id='test-013', csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn(
            "csl_data 'issued' field must contain valid date-parts with at least a year",
            str(context.exception),
        )

    def test_save_handles_missing_issued_in_csl_data(self):
        """Test that save() raises ValidationError for missing issued field in csl_data."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-014',
            'title': 'No Issued Date',
            'author': [{'family': 'Smith', 'given': 'John'}],
        }

        ref = Reference(id='test-014', csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn(
            "csl_data must contain an 'issued' field", str(context.exception)
        )

    def test_save_handles_authors_without_family_or_literal(self):
        """Test that save() handles authors without family or literal names."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-015',
            'title': 'Authors Without Family Names',
            'author': [
                {'given': 'John'},  # Only given name
                {'family': 'Smith', 'given': 'Jane'},  # Normal author
            ],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-015', csl_data=csl_data)
        ref.save()

        # Should only use authors with family names
        self.assertEqual(ref.author, 'Smith')

    def test_str_method_returns_title(self):
        """Test that __str__ method returns the title field."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-016',
            'title': 'Test String Representation',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(id='test-016', csl_data=csl_data)
        ref.save()

        self.assertEqual(str(ref), 'Test String Representation')

    def tearDown(self):
        """Clean up test data after each test."""
        Reference.objects.filter(id__startswith='test-').delete()


class ComponentModelTest(TestCase):
    """Test cases for the Component model."""

    def test_successful_component_creation(self):
        """Test that a Component can be successfully created with valid id and name."""
        component = Component(id='A.10.1.1', name='Wall Foundations')
        component.full_clean()  # This will run validation
        component.save()

        # Verify the component was saved correctly
        self.assertEqual(component.id, 'A.10.1.1')
        self.assertEqual(component.name, 'Wall Foundations')

        # Verify it can be retrieved from database
        saved_component = Component.objects.get(id='A.10.1.1')
        self.assertEqual(saved_component.name, 'Wall Foundations')

    def test_invalid_component_id_raises_validation_error(self):
        """Test that creating a Component with invalid id raises ValidationError."""
        component = Component(id='Z.99.9.9', name='Invalid Component')

        with self.assertRaises(ValidationError) as context:
            component.full_clean()

        # Check that the error message mentions the invalid ID
        error_message = str(context.exception)
        self.assertIn('Z.99.9.9', error_message)
        self.assertIn('not found in NISTIR taxonomy', error_message)

    def test_component_id_too_short_raises_validation_error(self):
        """Test that Component with ID with fewer than 4 NISTIR levels raises ValidationError."""
        component = Component(id='A.10.1', name='Short ID Component')

        with self.assertRaises(ValidationError) as context:
            component.full_clean()

        error_message = str(context.exception)
        self.assertIn('must have at least 4 NISTIR levels', error_message)

    def test_component_str_method_returns_id(self):
        """Test that __str__ method returns the component ID."""
        component = Component(id='A.10.1.1', name='Wall Foundations')
        self.assertEqual(str(component), 'A.10.1.1')

    def test_component_name_required(self):
        """Test that Component name field is required."""
        component = Component(id='A.10.1.1', name='')

        with self.assertRaises(ValidationError) as context:
            component.full_clean()

        error_message = str(context.exception)
        self.assertIn('name', error_message)

    def test_multiple_valid_component_ids(self):
        """Test creation of multiple components with different valid NISTIR IDs."""
        valid_components = [
            ('A.10.1.1', 'Wall Foundations'),
            ('A.10.1.2', 'Column Foundations & Pile Caps'),
            ('B.10.1.1', 'Suspended Basement Floors Construction'),
            ('C.10.1.1', 'Fixed Partitions'),
        ]

        for component_id, name in valid_components:
            with self.subTest(component_id=component_id):
                component = Component(id=component_id, name=name)
                component.full_clean()  # Should not raise ValidationError
                component.save()

                # Verify it was saved correctly
                saved_component = Component.objects.get(id=component_id)
                self.assertEqual(saved_component.name, name)

    def test_component_id_validation_levels(self):
        """Test that validation fails at different hierarchical levels."""
        invalid_ids_and_expected_errors = [
            ('X.10.1.1', 'major group'),  # Invalid major group
            ('A.90.1.1', 'group'),  # Invalid group
            ('A.10.9.1', 'element'),  # Invalid element
            ('A.10.1.9', 'subelement'),  # Invalid subelement
        ]

        for invalid_id, expected_error_type in invalid_ids_and_expected_errors:
            with self.subTest(invalid_id=invalid_id):
                component = Component(id=invalid_id, name='Test Component')

                with self.assertRaises(ValidationError) as context:
                    component.full_clean()

                error_message = str(context.exception)
                self.assertIn(expected_error_type, error_message)
                self.assertIn('not found', error_message)

    def test_save_method_populates_hierarchy_fields(self):
        """Test that the save() method correctly populates hierarchy fields from component_id."""
        component = Component(
            id='A.10.1.1', component_id='A.10.1.1', name='Wall Foundations'
        )
        component.save()

        # Verify hierarchy fields are populated with correct format
        self.assertEqual(component.major_group, 'A - Substructure')
        self.assertEqual(component.group, '10 - Foundation')
        self.assertEqual(component.element, '1 - Standard Foundations')
        self.assertEqual(component.subelement, '1 - Wall Foundations')

    def test_save_method_populates_hierarchy_fields_different_component(self):
        """Test hierarchy field population with a different component ID."""
        component = Component(id='B.20.2.1', component_id='B.20.2.1', name='Windows')
        component.save()

        # Verify hierarchy fields match expected values from nistir_labels.json
        self.assertEqual(component.major_group, 'B - Shell')
        self.assertEqual(component.group, '20 - Exterior Enclosure')
        self.assertEqual(component.element, '2 - Exterior Windows')
        self.assertEqual(component.subelement, '1 - Windows')

    def test_save_method_handles_missing_component_id(self):
        """Test that save() method handles missing component_id gracefully."""
        component = Component(
            id='A.10.1.1', component_id=None, name='Test Component'
        )
        component.save()

        # Hierarchy fields should remain None when component_id is None
        self.assertIsNone(component.major_group)
        self.assertIsNone(component.group)
        self.assertIsNone(component.element)
        self.assertIsNone(component.subelement)

    def test_save_method_id_description_format(self):
        """Test that hierarchy fields use the correct 'ID - Description' format."""
        test_cases = [
            {
                'component_id': 'C.10.1.1',
                'expected_major_group': 'C - Interiors',
                'expected_group': '10 - Interior Construction',
                'expected_element': '1 - Partitions',
                'expected_subelement': '1 - Fixed Partitions',
            },
            {
                'component_id': 'D.20.1.1',
                'expected_major_group': 'D - Services',
                'expected_group': '20 - Plumbing',
                'expected_element': '1 - Plumbing Fixtures',
                'expected_subelement': '1 - Water Closets',
            },
        ]

        for i, test_case in enumerate(test_cases):
            with self.subTest(component_id=test_case['component_id']):
                component = Component(
                    id=f'test-{i}',
                    component_id=test_case['component_id'],
                    name=f'Test Component {i}',
                )
                component.save()

                self.assertEqual(
                    component.major_group, test_case['expected_major_group']
                )
                self.assertEqual(component.group, test_case['expected_group'])
                self.assertEqual(component.element, test_case['expected_element'])
                self.assertEqual(
                    component.subelement, test_case['expected_subelement']
                )

    def tearDown(self):
        """Clean up test data after each test."""
        Component.objects.filter(
            id__in=[
                'A.10.1.1',
                'A.10.1.2',
                'B.10.1.1',
                'C.10.1.1',
                'B.20.2.1',
                'test-0',
                'test-1',
            ]
        ).delete()
