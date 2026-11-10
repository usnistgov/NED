from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from ned_app.models import (
    Component,
    Facility,
    Observation,
    ObservationFragilityModelBridge,
    Program,
    Reference,
    Specimen,
    Test,
    derive_reference_id,
    normalize_author_token,
)


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

        ref = Reference(csl_data=csl_data)
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

        ref = Reference(csl_data=csl_data)
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

        ref = Reference(csl_data=csl_data)
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

        ref = Reference(csl_data=csl_data)
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

        ref = Reference(csl_data=csl_data)
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

        ref = Reference(csl_data=csl_data)
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

        ref = Reference(csl_data=csl_data)
        ref.save()

        # Should use "et al." for 3+ authors
        self.assertEqual(ref.author, 'Smith et al.')

    def test_save_handles_missing_csl_data(self):
        """Test that save() raises ValidationError for missing csl_data."""
        ref = Reference()

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn(
            'csl_data is required and cannot be empty', str(context.exception)
        )

    def test_save_handles_empty_csl_data(self):
        """Test that save() raises ValidationError for empty csl_data."""
        ref = Reference(csl_data={})

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

        ref = Reference(csl_data=csl_data)

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

        ref = Reference(csl_data=csl_data)

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

        ref = Reference(csl_data=csl_data)

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

        ref = Reference(csl_data=csl_data)

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

        ref = Reference(csl_data=csl_data)

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

        ref = Reference(csl_data=csl_data)
        ref.save()

        # Should only use authors with family names
        self.assertEqual(ref.author, 'Smith')

    def test_str_method_returns_reference_id(self):
        """Test that __str__ method returns the reference_id field."""
        csl_data = {
            'type': 'article-journal',
            'id': 'test-016',
            'title': 'Test String Representation',
            'author': [{'family': 'Smith', 'given': 'John'}],
            'issued': {'date-parts': [[2023]]},
        }

        ref = Reference(csl_data=csl_data)
        ref.save()

        self.assertEqual(str(ref), 'Smith-2023')


class ReferenceIdDerivationTest(TestCase):
    """Tests for reference_id derivation from label / first-author surname + year."""

    @staticmethod
    def _csl(family=None, year=2023, literal=None):
        author = [{'literal': literal}] if literal else [{'family': family}]
        return {
            'type': 'article-journal',
            'id': 'x',
            'title': 'Test Title',
            'author': author,
            'issued': {'date-parts': [[year]]},
        }

    def test_normalize_strips_punctuation_and_diacritics(self):
        """Normalization drops non-alphanumerics and diacritics, keeps case."""
        self.assertEqual(normalize_author_token('Smith'), 'Smith')
        self.assertEqual(normalize_author_token("O'Brien"), 'OBrien')
        self.assertEqual(normalize_author_token('Araya-Letelier'), 'ArayaLetelier')
        self.assertEqual(normalize_author_token('García'), 'Garcia')
        self.assertEqual(normalize_author_token(''), '')

    def test_derive_uses_label_when_set(self):
        """A reference_label replaces the surname token in the derived id."""
        self.assertEqual(
            derive_reference_id('FEMA_P58', self._csl(literal='FEMA', year=2018)),
            'FEMA_P58-2018',
        )

    def test_derive_uses_first_author_surname_without_label(self):
        """Without a label, the (first) author's surname is used."""
        csl = self._csl(family='Zaghi', year=2012)
        csl['author'].append({'family': 'Maragakis'})
        self.assertEqual(derive_reference_id('', csl), 'Zaghi-2012')

    def test_derive_normalizes_surname(self):
        """A surname with punctuation is normalized in the derived id."""
        self.assertEqual(
            derive_reference_id('', self._csl(family='Araya-Letelier', year=2012)),
            'ArayaLetelier-2012',
        )

    def test_derive_falls_back_to_literal_author(self):
        """An institutional (literal) author is used when there is no family."""
        self.assertEqual(
            derive_reference_id('', self._csl(literal='FEMA', year=2018)),
            'FEMA-2018',
        )

    def test_save_derives_reference_id_from_author(self):
        """Reference.save() derives reference_id from the surname when unset."""
        ref = Reference(csl_data=self._csl(family='Cook', year=2024))
        ref.save()
        self.assertEqual(ref.reference_id, 'Cook-2024')

    def test_save_derives_reference_id_from_label(self):
        """Reference.save() derives reference_id from reference_label when set."""
        ref = Reference(
            reference_label='Bhatta_TwoStoryCladding',
            csl_data=self._csl(family='Bhatta', year=2022),
        )
        ref.save()
        self.assertEqual(ref.reference_id, 'Bhatta_TwoStoryCladding-2022')

    def test_save_overrides_explicitly_set_reference_id(self):
        """An explicitly provided reference_id is replaced by the derived one."""
        ref = Reference(
            reference_id='Explicit-1', csl_data=self._csl(family='Smith', year=2023)
        )
        ref.save()
        self.assertEqual(ref.reference_id, 'Smith-2023')

    def test_save_rederives_reference_id_after_an_edit(self):
        """Changing the label or the year re-derives a saved reference's id."""
        ref = Reference(csl_data=self._csl(family='Smith', year=2023))
        ref.save()
        ref.reference_label = 'Smith_Walls'
        ref.save()
        self.assertEqual(ref.reference_id, 'Smith_Walls-2023')

    def tearDown(self):
        """Clean up test data after each test."""
        Reference.objects.all().delete()


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

        # Check for the new generic error message format
        error_dict = context.exception.message_dict
        self.assertIn('id', error_dict)

        expected_msg = 'Invalid component ID: The NISTIR ID "Z.99.9.9" was not found in the taxonomy.'
        self.assertIn(expected_msg, error_dict['id'])

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
        """Test that validation fails correctly for various invalid hierarchical levels."""
        invalid_ids = [
            'X.10.1.1',  # Invalid major group
            'A.90.1.1',  # Invalid group
            'A.10.9.1',  # Invalid element
            'A.10.1.9',  # Invalid subelement
        ]

        for invalid_id in invalid_ids:
            with self.subTest(invalid_id=invalid_id):
                component = Component(id=invalid_id, name='Test Component')

                with self.assertRaises(ValidationError) as context:
                    component.full_clean()

                error_dict = context.exception.message_dict
                self.assertIn('id', error_dict)
                expected_msg = f'Invalid component ID: The NISTIR ID "{invalid_id}" was not found in the taxonomy.'
                self.assertIn(expected_msg, error_dict['id'])

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


class ProgramModelTest(TestCase):
    """Test cases for Program, focusing on the derived program_id."""

    def setUp(self):
        self.reference = Reference.objects.create(
            reference_id='Smith-2020',
            csl_data={
                'type': 'article-journal',
                'id': 'smith-2020',
                'title': 'Test Article',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2020]]},
            },
        )

    def test_program_id_defaults_to_reference_id(self):
        program = Program.objects.create(reference=self.reference)
        self.assertEqual(program.program_id, 'Smith-2020')

    def test_program_id_uses_label_when_set(self):
        program = Program.objects.create(reference=self.reference, label='CFS10')
        self.assertEqual(program.program_id, 'CFS10')

    def test_program_id_is_recomputed_on_every_save(self):
        program = Program.objects.create(reference=self.reference)
        program.label = 'CFS10'
        program.save()
        self.assertEqual(Program.objects.get(pk=program.pk).program_id, 'CFS10')

    def test_program_id_differing_only_in_case_is_rejected(self):
        Program.objects.create(reference=self.reference, label='CFS10')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Program.objects.create(reference=self.reference, label='cfs10')


class FacilityModelTest(TestCase):
    """Test cases for Facility."""

    def test_label_differing_only_in_case_is_rejected(self):
        Facility.objects.create(label='UB_NCS')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Facility.objects.create(label='ub_ncs')


class SpecimenAndTestModelTest(TestCase):
    """Test cases for Specimen, Test and Observation derived ids and constraints."""

    def setUp(self):
        self.reference = reference = Reference.objects.create(
            reference_id='Smith-2020',
            csl_data={
                'type': 'article-journal',
                'id': 'smith-2020',
                'title': 'Test Article',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2020]]},
            },
        )
        self.component = Component.objects.create(
            component_id='C.10.1.1', name='Fixed Partitions'
        )
        self.program = Program.objects.create(reference=reference)
        self.facility = Facility.objects.create(label='UB_NCS')
        self.specimen = self.make_specimen('S1')

    def make_specimen(self, label):
        return Specimen.objects.create(
            program=self.program,
            facility=self.facility,
            component=self.component,
            label=label,
            comp_description='Partition wall',
        )

    def make_test(self, label, test_order=None):
        return Test.objects.create(
            specimen=self.specimen,
            label=label,
            test_order=test_order,
            test_type='Quasi-static Cyclic, uniaxial',
        )

    def make_observation(self, test, label):
        return Observation.objects.create(
            ds_description='Crack',
            edp_metric='Story Drift Ratio',
            edp_unit='Ratio',
            ds_class='Inconsequential',
            test=test,
            label=label,
        )

    def test_ids_are_derived(self):
        test = self.make_test('7', test_order=7)
        observation = self.make_observation(test, '01')
        self.assertEqual(self.specimen.specimen_id, 'Smith-2020|S1')
        self.assertEqual(test.test_id, 'Smith-2020|S1|7')
        self.assertEqual(observation.observation_id, 'Smith-2020|S1|7|01')
        self.assertEqual(str(observation), 'Smith-2020|S1|7|01')
        # The primary key is an internal integer.
        self.assertIsInstance(observation.pk, int)

    def test_relabelling_updates_the_id_on_the_same_row(self):
        # Only for a row with no children; relabelling a parent is rename_identity's job.
        test = self.make_test('a')
        test.label = 'b'
        test.save()
        self.assertEqual(Test.objects.get(pk=test.pk).test_id, 'Smith-2020|S1|b')
        self.assertEqual(Test.objects.count(), 1)

        specimen = self.make_specimen('S2')
        specimen.label = 'S3'
        specimen.save()
        self.assertEqual(
            Specimen.objects.get(pk=specimen.pk).specimen_id, 'Smith-2020|S3'
        )

        observation = self.make_observation(test, '01')
        observation.label = '02'
        observation.save()
        self.assertEqual(
            Observation.objects.get(pk=observation.pk).observation_id,
            'Smith-2020|S1|b|02',
        )
        self.assertEqual(Observation.objects.count(), 1)

    def test_specimen_label_differing_only_in_case_is_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_specimen('s1')

    def test_test_label_differing_only_in_case_is_rejected(self):
        self.make_test('A')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_test('a')

    def test_observation_label_differing_only_in_case_is_rejected(self):
        test = self.make_test('a')
        self.make_observation(test, 'x01')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_observation(test, 'X01')

    def test_duplicate_test_order_is_rejected(self):
        self.make_test('7', test_order=7)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_test('x', test_order=7)

    def test_two_null_test_orders_are_accepted(self):
        self.make_test('a')
        self.make_test('b')
        self.assertEqual(self.specimen.number_of_tests, 2)

    def test_effective_reference_falls_back_to_program(self):
        self.assertEqual(self.specimen.effective_reference_id, 'Smith-2020')


class DamagedByEarlierTestTest(TestCase):
    """Test cases for Test.damaged_by_earlier_test, in every case of design 2.2."""

    def setUp(self):
        self.reference = Reference.objects.create(
            reference_id='Smith-2020',
            csl_data={
                'type': 'article-journal',
                'id': 'smith-2020',
                'title': 'Test Article',
                'author': [{'family': 'Smith', 'given': 'John'}],
                'issued': {'date-parts': [[2020]]},
            },
        )
        self.component = Component.objects.create(
            component_id='C.10.1.1', name='Fixed Partitions'
        )
        self.specimen = Specimen.objects.create(
            program=Program.objects.create(reference=self.reference),
            facility=Facility.objects.create(label='UB_NCS'),
            component=self.component,
            label='S1',
            comp_description='Partition wall',
        )

    def make_test(self, label, test_order=None):
        return Test.objects.create(
            specimen=self.specimen,
            label=label,
            test_order=test_order,
            test_type='Quasi-static Cyclic, uniaxial',
        )

    def observe(self, test):
        Observation.objects.create(
            ds_description='Crack',
            edp_metric='Story Drift Ratio',
            edp_unit='Ratio',
            ds_class='Inconsequential',
            test=test,
            label='01',
        )

    def test_true_when_an_earlier_test_holds_observations(self):
        first = self.make_test('1', test_order=1)
        second = self.make_test('2', test_order=2)
        self.observe(first)
        self.assertIs(second.damaged_by_earlier_test, True)

    def test_true_wins_over_an_unordered_sibling(self):
        first = self.make_test('1', test_order=1)
        second = self.make_test('2', test_order=2)
        self.make_test('a')
        self.observe(first)
        self.assertIs(second.damaged_by_earlier_test, True)

    def test_false_for_a_lone_test(self):
        self.assertIs(self.make_test('a').damaged_by_earlier_test, False)

    def test_false_for_the_lowest_ordered_test(self):
        first = self.make_test('7', test_order=7)
        self.observe(self.make_test('8', test_order=8))
        self.assertIs(first.damaged_by_earlier_test, False)

    def test_false_when_earlier_tests_hold_no_observations(self):
        self.make_test('1', test_order=1)
        self.assertIs(
            self.make_test('2', test_order=2).damaged_by_earlier_test, False
        )

    def test_none_when_the_order_is_not_recorded(self):
        ordered = self.make_test('1', test_order=1)
        unordered = self.make_test('a')
        self.observe(unordered)
        # Neither side can rule out earlier damage.
        self.assertIsNone(unordered.damaged_by_earlier_test)
        self.assertIsNone(ordered.damaged_by_earlier_test)


class SchemaTest(TestCase):
    """The schema matches design 2.1 and 2.2, and the migrations match the models."""

    # Design 2.2's Observation table. None of the columns that moved to the
    # hierarchy, nor reference, may come back.
    OBSERVATION_FIELDS = (
        'id',
        'observation_id',
        'test',
        'label',
        'damage_location',
        'ds_description',
        'ds_class',
        'edp_metric',
        'edp_unit',
        'edp_value',
        'alt_edp_metric',
        'alt_edp_unit',
        'alt_edp_value',
        'notes',
        'legacy_prior_damage',
        'legacy_prior_damage_repaired',
        'legacy_ds_rank',
    )

    # Design 2.1's FK table: (model, field, parent model, the parent field it
    # points at).
    HIERARCHY_FKS = (
        (Program, 'reference', Reference, 'reference_id'),
        (Specimen, 'program', Program, 'program_id'),
        (Specimen, 'facility', Facility, 'label'),
        (Specimen, 'reference', Reference, 'reference_id'),
        (Specimen, 'component', Component, 'component_id'),
        (Test, 'specimen', Specimen, 'specimen_id'),
        (Observation, 'test', Test, 'test_id'),
        (
            ObservationFragilityModelBridge,
            'observation',
            Observation,
            'observation_id',
        ),
    )

    def test_observation_fields_are_the_declared_list(self):
        self.assertCountEqual(
            [f.name for f in Observation._meta.concrete_fields],
            self.OBSERVATION_FIELDS,
        )

    def test_hierarchy_fks_point_at_the_parent_derived_id_or_label(self):
        for model, name, parent, to_field in self.HIERARCHY_FKS:
            with self.subTest(fk=f'{model.__name__}.{name}'):
                field = model._meta.get_field(name)
                self.assertTrue(field.many_to_one)
                self.assertIs(field.related_model, parent)
                self.assertEqual(field.target_field.name, to_field)

    def test_hierarchy_fks_are_all_declared(self):
        # A new FK on a hierarchy model must be added to the table above.
        declared = {(m, name) for m, name, _, _ in self.HIERARCHY_FKS}
        for model in (Facility, Program, Specimen, Test, Observation):
            for field in model._meta.concrete_fields:
                if field.is_relation:
                    self.assertIn(
                        (model, field.name),
                        declared,
                        f'{model.__name__}.{field.name} is not in HIERARCHY_FKS',
                    )

    def test_migrations_match_the_models(self):
        # makemigrations --check exits non-zero when a model change has no
        # migration; --noinput stops a rename question waiting for an answer.
        out = StringIO()
        try:
            call_command(
                'makemigrations',
                '--check',
                '--dry-run',
                '--noinput',
                stdout=out,
                stderr=out,
            )
        except SystemExit:
            self.fail(
                f'The models have changes with no migration:\n{out.getvalue()}'
            )
