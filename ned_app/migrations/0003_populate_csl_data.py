# Generated manually for data migration

import json
import re
import os
import jsonschema
from django.db import migrations
from django.conf import settings


def parse_single_author_name(name_string):
    """Parse a single author name string into CSL-JSON author format.

    Args:
        name_string (str): A single author name string

    Returns:
        dict: CSL-JSON author dictionary with 'family' and optionally 'given' keys
    """
    words = name_string.split()
    if len(words) >= 2:
        family = words[-1]
        given = ' '.join(words[:-1])
        return {'family': family, 'given': given}
    elif len(words) == 1:
        return {'family': name_string}
    else:
        return {'family': name_string}  # Fallback for empty strings


def parse_authors(author_string):
    """Parse author string into CSL-JSON author format."""
    if not author_string:
        return []

    authors = []

    # Handle "et al." cases
    if 'et al.' in author_string:
        # Extract the first author before "et al."
        first_author = author_string.split('et al.')[0].strip()
        if first_author.endswith(','):
            first_author = first_author[:-1].strip()

        # Parse the first author
        authors.append(parse_single_author_name(first_author))
        return authors

    # Split by " and " first, then handle commas within each part
    and_parts = re.split(r'\s+and\s+', author_string)

    for and_part in and_parts:
        and_part = and_part.strip()
        if not and_part:
            continue

        # Check if this part contains multiple comma-separated authors
        # Look for pattern: "Last1, First1, Last2, First2" vs "Last, First"
        comma_parts = [part.strip() for part in and_part.split(',')]

        if len(comma_parts) == 2:
            # Simple "Last, First" format
            family = comma_parts[0].strip()
            given = comma_parts[1].strip()
            authors.append({'family': family, 'given': given})
        elif len(comma_parts) > 2:
            # Multiple authors separated by commas
            # Try to pair them as "First Last, First Last, ..."
            for comma_part in comma_parts:
                comma_part = comma_part.strip()
                if not comma_part:
                    continue

                authors.append(parse_single_author_name(comma_part))
        else:
            # Single part, parse as "First Last" format
            authors.append(parse_single_author_name(and_part))

    return authors


def extract_authors_from_citation(citation):
    """Extract authors from citation string using various patterns."""
    if not citation:
        return []

    authors = []

    # Pattern 1: "Author1, Author2, and Author3. (Year)"
    # Pattern 2: "Author1, Author2, Author3 (Year)"
    # Pattern 3: "Author1 et al. (Year)"

    # Look for author pattern at the beginning of citation
    # Authors typically come before year in parentheses
    year_match = re.search(r'\((\d{4})\)', citation)
    if year_match:
        # Extract text before the year
        author_text = citation[: year_match.start()].strip()

        # Remove trailing punctuation
        author_text = re.sub(r'[.,;:]+$', '', author_text)

        # Parse the extracted author text
        authors = parse_authors(author_text)
    else:
        # Try to extract authors from the beginning of citation
        # Look for patterns like "Author. (Year)" or "Author (Year)"
        match = re.match(r'^([^.]+(?:\.|$))', citation)
        if match:
            potential_authors = match.group(1).strip()
            # Remove trailing period
            potential_authors = re.sub(r'\.$', '', potential_authors)
            authors = parse_authors(potential_authors)

    return authors


def compare_and_choose_authors(field_authors, citation_authors):
    """Compare authors from field vs citation and choose the richer source."""
    if not field_authors and not citation_authors:
        return []

    if not field_authors:
        return citation_authors

    if not citation_authors:
        return field_authors

    # Count total information richness (given names, full names, etc.)
    def count_richness(authors):
        richness = 0
        for author in authors:
            if 'given' in author and author['given']:
                richness += 2  # Given name adds more value
            if 'family' in author and author['family']:
                richness += 1
        return richness

    field_richness = count_richness(field_authors)
    citation_richness = count_richness(citation_authors)

    if citation_richness >= field_richness:
        return citation_authors
    else:
        return field_authors


def parse_conference_details(citation, pub_type):
    """Extract conference name and location from citation."""
    details = {}

    if not citation or pub_type != 'paper-conference':
        return details

    # Pattern: "Conference Name, Location" or "Conference Name. Location"
    # Look for conference patterns with flexible separators
    conference_patterns = [
        r'([^,.]+Conference[^,.]*)[.,]\s*([^.]+)',
        r'([^,.]+Symposium[^,.]*)[.,]\s*([^.]+)',
        r'([^,.]+Workshop[^,.]*)[.,]\s*([^.]+)',
    ]

    for pattern in conference_patterns:
        match = re.search(pattern, citation, re.IGNORECASE)
        if match:
            details['event-title'] = match.group(1).strip()
            details['event-place'] = match.group(2).strip()
            break

    return details


def parse_journal_details(citation, pub_type):
    """Extract journal name, volume, issue, and pages from citation."""
    details = {}

    if not citation or pub_type != 'article-journal':
        return details

    # Pattern: "Journal Name, Volume(Issue), Pages" or "Journal Name. Volume(Issue). Pages"
    # Pattern: "Journal Name, Volume, Pages" or "Journal Name. Volume. Pages"
    journal_patterns = [
        r'([^,.]+)[.,]\s*(\d+)\((\d+)\)[.,]\s*(\d+(?:-\d+)?)',  # Journal[.,] Vol(Issue)[.,] Pages
        r'([^,.]+)[.,]\s*(\d+)[.,]\s*(\d+(?:-\d+)?)',  # Journal[.,] Vol[.,] Pages
        r'([^,.]+)[.,]\s*(\d+)\((\d+)\):\s*(\d+(?:-\d+)?)',  # Journal[.,] Vol(Issue): Pages
    ]

    for pattern in journal_patterns:
        match = re.search(pattern, citation)
        if match:
            details['container-title'] = match.group(1).strip()
            details['volume'] = match.group(2)
            if len(match.groups()) == 4:
                if match.group(3).isdigit():
                    details['issue'] = match.group(3)
                    details['page'] = match.group(4)
                else:
                    details['page'] = match.group(3)
            break

    return details


def parse_report_details(citation, pub_type):
    """Extract report type, publisher, and location from citation."""
    details = {}

    if not citation or pub_type != 'report':
        return details

    # Pattern: "Report No. XXX, Institution, Location" or "Report No. XXX. Institution. Location"
    # Pattern: "Technical Report, Institution" or "Technical Report. Institution"
    report_patterns = [
        r'(Technical Report|Report No\.[^,.]+)[.,]\s*([^,.]+)[.,]?\s*([^.]+)?',
        r'(NEES[^,.]+)[.,]\s*([^,.]+)',
        r'(MCEER[^,.]+)[.,]\s*([^,.]+)',
        r'(CUREE[^,.]+)',
    ]

    for pattern in report_patterns:
        match = re.search(pattern, citation, re.IGNORECASE)
        if match:
            details['genre'] = match.group(1).strip()
            if len(match.groups()) >= 2:
                details['publisher'] = match.group(2).strip()
            if len(match.groups()) >= 3 and match.group(3):
                details['publisher-place'] = match.group(3).strip()
            break

    return details


def parse_thesis_details(citation, pub_type):
    """Extract university name and location from thesis citation."""
    details = {}

    if not citation or pub_type != 'thesis':
        return details

    # Pattern: "Thesis Type, University Name, Location" or "Thesis Type. University Name. Location"
    # Pattern: "University Name"
    thesis_patterns = [
        r'(?:Master\'s Thesis|PhD Thesis|Dissertation)[.,]\s*([^,.]+)[.,]?\s*([^.]+)?',
        r'([^,.]+University[^,.]*)[.,]?\s*([^.]+)?',
        r'([^,.]+College[^,.]*)[.,]?\s*([^.]+)?',
    ]

    for pattern in thesis_patterns:
        match = re.search(pattern, citation, re.IGNORECASE)
        if match:
            details['publisher'] = match.group(1).strip()
            if len(match.groups()) >= 2 and match.group(2):
                details['publisher-place'] = match.group(2).strip()
            break

    return details


def determine_publication_type(publication_type, citation):
    """Map publication_type to CSL type."""
    type_mapping = {
        'Journal Article': 'article-journal',
        'Journal article': 'article-journal',
        'Conference paper': 'paper-conference',
        'Conference Paper': 'paper-conference',
        'Technical Report': 'report',
        "Master's Thesis": 'thesis',
        'PhD Thesis': 'thesis',
        'Dissertation': 'thesis',
        'Book': 'book',
        'Chapter': 'chapter',
        'Book Chapter': 'chapter',
        'FEMA P-58/BD-3.9.1': 'report',  # FEMA publications are technical reports
        'FEMA P-58/BD-3.9.32': 'report',
        'Unknown': 'document',  # Explicitly handle Unknown
    }

    if publication_type in type_mapping:
        return type_mapping[publication_type]

    # Try to infer from citation
    if citation:
        citation_lower = citation.lower()
        if 'conference' in citation_lower:
            return 'paper-conference'
        elif 'journal' in citation_lower:
            return 'article-journal'
        elif 'thesis' in citation_lower:
            return 'thesis'
        elif 'report' in citation_lower:
            return 'report'

    return 'document'  # Default fallback


def reverse_publication_type(csl_type):
    """Reverse map CSL type back to publication_type."""
    reverse_mapping = {
        'article-journal': 'Journal Article',
        'paper-conference': 'Conference paper',
        'report': 'Technical Report',
        'thesis': 'PhD Thesis',  # Default to PhD for thesis
        'book': 'Book',
        'chapter': 'Chapter',
        'document': 'Unknown',  # Default fallback
    }

    return reverse_mapping.get(csl_type, 'Unknown')


def forwards_func(apps, schema_editor):
    """Populate csl_data field from existing Reference fields."""
    Reference = apps.get_model('ned_app', 'Reference')

    # Load CSL schema for validation - fail if not available
    schema_path = os.path.join(
        settings.BASE_DIR, 'ned_app', 'schemas', 'csl-data.json'
    )
    try:
        with open(schema_path, 'r') as f:
            csl_schema = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f'CSL schema not found at {schema_path}. Migration cannot proceed without schema validation.'
        )

    processed_count = 0
    error_count = 0

    for ref in Reference.objects.all():
        try:
            # Determine publication type
            pub_type = determine_publication_type(ref.publication_type, ref.citation)

            # Construct CSL-JSON dictionary
            csl_data = {
                'type': pub_type,
                'id': ref.id,
                'title': ref.name,
            }

            # Enhanced author parsing - compare field vs citation authors
            field_authors = parse_authors(ref.author) if ref.author else []
            citation_authors = (
                extract_authors_from_citation(ref.citation) if ref.citation else []
            )

            # Choose the richer author source
            final_authors = compare_and_choose_authors(
                field_authors, citation_authors
            )
            if final_authors:
                csl_data['author'] = final_authors

            # Add year if available
            if ref.year:
                csl_data['issued'] = {'date-parts': [[ref.year]]}

            # Add DOI if available
            if ref.doi:
                csl_data['DOI'] = ref.doi
                csl_data['URL'] = ref.doi

            # Type-specific data extraction from citation
            if ref.citation:
                # Conference papers
                if pub_type == 'paper-conference':
                    conference_details = parse_conference_details(
                        ref.citation, pub_type
                    )
                    csl_data.update(conference_details)

                # Journal articles
                elif pub_type == 'article-journal':
                    journal_details = parse_journal_details(ref.citation, pub_type)
                    csl_data.update(journal_details)

                # Technical reports
                elif pub_type == 'report':
                    report_details = parse_report_details(ref.citation, pub_type)
                    csl_data.update(report_details)

                # Theses
                elif pub_type == 'thesis':
                    thesis_details = parse_thesis_details(ref.citation, pub_type)
                    csl_data.update(thesis_details)

            # Always store original citation in note field for reversibility
            if ref.citation:
                csl_data['note'] = ref.citation

            # Validate against schema
            try:
                # Wrap in array as schema expects array of items
                jsonschema.validate([csl_data], csl_schema)
            except jsonschema.ValidationError as e:
                print(f'Warning: Validation failed for reference {ref.id}: {e}')
                error_count += 1
                continue

            # Save the CSL data
            ref.csl_data = csl_data
            ref.save(update_fields=['csl_data'])
            processed_count += 1

        except Exception as e:
            print(f'Error processing reference {ref.id}: {e}')
            error_count += 1

    print(
        f'Data migration completed. Processed: {processed_count}, Errors: {error_count}'
    )


def reverse_func(apps, schema_editor):
    """Restore original field values from csl_data."""
    Reference = apps.get_model('ned_app', 'Reference')

    restored_count = 0

    for ref in Reference.objects.filter(csl_data__isnull=False):
        try:
            csl_data = ref.csl_data

            # Restore id from CSL id field
            if 'id' in csl_data:
                ref.id = csl_data['id']

            # Restore name from CSL title field
            if 'title' in csl_data:
                ref.name = csl_data['title']

            # Restore publication_type from CSL type field
            if 'type' in csl_data:
                ref.publication_type = reverse_publication_type(csl_data['type'])

            # Restore citation from note field
            if 'note' in csl_data:
                ref.citation = csl_data['note']

            # Restore author from CSL author data
            if 'author' in csl_data:
                authors = csl_data['author']
                author_strings = []
                for author in authors:
                    if 'given' in author and 'family' in author:
                        author_strings.append(
                            f"{author['given']} {author['family']}"
                        )
                    elif 'family' in author:
                        author_strings.append(author['family'])
                ref.author = ', '.join(author_strings)

            # Restore year from issued date
            if 'issued' in csl_data and 'date-parts' in csl_data['issued']:
                date_parts = csl_data['issued']['date-parts']
                if date_parts and len(date_parts[0]) > 0:
                    ref.year = date_parts[0][0]

            # Restore DOI
            if 'DOI' in csl_data:
                ref.doi = csl_data['DOI']

            ref.save(
                update_fields=[
                    'id',
                    'name',
                    'publication_type',
                    'citation',
                    'author',
                    'year',
                    'doi',
                ]
            )
            restored_count += 1

        except Exception as e:
            print(f'Error restoring reference {ref.id}: {e}')

    print(f'Reverse migration completed. Restored: {restored_count} references')


class Migration(migrations.Migration):
    dependencies = [
        ('ned_app', '0002_reference_csl_data'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
