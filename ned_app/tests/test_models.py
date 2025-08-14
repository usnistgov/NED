from django.test import TestCase
from django.core.exceptions import ValidationError
from ned_app.models import Reference


class ReferenceModelTest(TestCase):
    """Test cases for the Reference model, focusing on the save() method logic."""

    def test_save_populates_title_from_csl_data(self):
        """Test that save() populates title field from csl_data."""
        csl_data = {
            "type": "article-journal",
            "id": "test-001",
            "title": "Test Article Title",
            "author": [{"family": "Smith", "given": "John"}],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-001", csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.title, "Test Article Title")

    def test_save_populates_year_from_csl_data(self):
        """Test that save() populates year field from csl_data issued date-parts."""
        csl_data = {
            "type": "article-journal",
            "id": "test-002",
            "title": "Test Article",
            "author": [{"family": "Smith", "given": "John"}],
            "issued": {"date-parts": [[2022]]}
        }

        ref = Reference(id="test-002", csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.year, 2022)

    def test_save_populates_author_single_author(self):
        """Test that save() populates author field correctly for single author."""
        csl_data = {
            "type": "article-journal",
            "id": "test-003",
            "title": "Single Author Paper",
            "author": [{"family": "Johnson", "given": "Alice"}],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-003", csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.author, "Johnson")

    def test_save_populates_author_two_authors(self):
        """Test that save() populates author field correctly for two authors."""
        csl_data = {
            "type": "article-journal",
            "id": "test-004",
            "title": "Two Authors Paper",
            "author": [
                {"family": "Smith", "given": "John"},
                {"family": "Doe", "given": "Jane"}
            ],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-004", csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.author, "Smith and Doe")

    def test_save_populates_author_three_or_more_authors(self):
        """Test that save() populates author field correctly for three or more authors."""
        csl_data = {
            "type": "article-journal",
            "id": "test-005",
            "title": "Multiple Authors Paper",
            "author": [
                {"family": "Smith", "given": "John"},
                {"family": "Doe", "given": "Jane"},
                {"family": "Johnson", "given": "Bob"},
                {"family": "Brown", "given": "Alice"}
            ],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-005", csl_data=csl_data)
        ref.save()

        self.assertEqual(ref.author, "Smith et al.")

    def test_save_handles_literal_author_names(self):
        """Test that save() handles literal author names correctly."""
        csl_data = {
            "type": "report",
            "id": "test-006",
            "title": "Report with Literal Author",
            "author": [{"literal": "John Smith"}],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-006", csl_data=csl_data)
        ref.save()

        # Should extract last word from literal name
        self.assertEqual(ref.author, "Smith")

    def test_save_handles_mixed_author_formats(self):
        """Test that save() handles mixed author formats (family/given and literal)."""
        csl_data = {
            "type": "article-journal",
            "id": "test-007",
            "title": "Mixed Author Formats",
            "author": [
                {"family": "Smith", "given": "John"},
                {"literal": "Jane Doe"},
                {"family": "Johnson", "given": "Bob"}
            ],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-007", csl_data=csl_data)
        ref.save()

        # Should use "et al." for 3+ authors
        self.assertEqual(ref.author, "Smith et al.")

    def test_save_handles_missing_csl_data(self):
        """Test that save() raises ValidationError for missing csl_data."""
        ref = Reference(id="test-008")

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn("csl_data is required and cannot be empty", str(context.exception))

    def test_save_handles_empty_csl_data(self):
        """Test that save() raises ValidationError for empty csl_data."""
        ref = Reference(id="test-009", csl_data={})

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn("csl_data is required and cannot be empty", str(context.exception))

    def test_save_handles_missing_title_in_csl_data(self):
        """Test that save() raises ValidationError for missing title in csl_data."""
        csl_data = {
            "type": "article-journal",
            "id": "test-010",
            "author": [{"family": "Smith", "given": "John"}],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-010", csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn("csl_data must contain a non-empty 'title' field", str(context.exception))

    def test_save_handles_missing_authors_in_csl_data(self):
        """Test that save() raises ValidationError for missing authors in csl_data."""
        csl_data = {
            "type": "article-journal",
            "id": "test-011",
            "title": "No Authors Paper",
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-011", csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn("csl_data must contain a non-empty 'author' field", str(context.exception))

    def test_save_handles_empty_authors_list(self):
        """Test that save() raises ValidationError for empty authors list in csl_data."""
        csl_data = {
            "type": "article-journal",
            "id": "test-012",
            "title": "Empty Authors List",
            "author": [],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-012", csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn("csl_data must contain a non-empty 'author' field", str(context.exception))

    def test_save_handles_malformed_date_parts(self):
        """Test that save() raises ValidationError for malformed date-parts in csl_data."""
        csl_data = {
            "type": "article-journal",
            "id": "test-013",
            "title": "Malformed Date",
            "author": [{"family": "Smith", "given": "John"}],
            "issued": {"date-parts": [[]]}  # Empty date parts
        }

        ref = Reference(id="test-013", csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn("csl_data 'issued' field must contain valid date-parts with at least a year", str(context.exception))

    def test_save_handles_missing_issued_in_csl_data(self):
        """Test that save() raises ValidationError for missing issued field in csl_data."""
        csl_data = {
            "type": "article-journal",
            "id": "test-014",
            "title": "No Issued Date",
            "author": [{"family": "Smith", "given": "John"}]
        }

        ref = Reference(id="test-014", csl_data=csl_data)

        with self.assertRaises(ValidationError) as context:
            ref.save()

        self.assertIn("csl_data must contain an 'issued' field", str(context.exception))

    def test_save_handles_authors_without_family_or_literal(self):
        """Test that save() handles authors without family or literal names."""
        csl_data = {
            "type": "article-journal",
            "id": "test-015",
            "title": "Authors Without Family Names",
            "author": [
                {"given": "John"},  # Only given name
                {"family": "Smith", "given": "Jane"}  # Normal author
            ],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-015", csl_data=csl_data)
        ref.save()

        # Should only use authors with family names
        self.assertEqual(ref.author, "Smith")

    def test_str_method_returns_title(self):
        """Test that __str__ method returns the title field."""
        csl_data = {
            "type": "article-journal",
            "id": "test-016",
            "title": "Test String Representation",
            "author": [{"family": "Smith", "given": "John"}],
            "issued": {"date-parts": [[2023]]}
        }

        ref = Reference(id="test-016", csl_data=csl_data)
        ref.save()

        self.assertEqual(str(ref), "Test String Representation")

    def tearDown(self):
        """Clean up test data after each test."""
        Reference.objects.filter(id__startswith="test-").delete()
