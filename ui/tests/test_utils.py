import math

import pandas as pd

from utils import build_citation, csv_safe, doi_link, doi_url, esc, fmt, strip_prefix


class TestFmt:
    def test_none_becomes_em_dash(self):
        assert fmt(None) == '—'

    def test_nan_becomes_em_dash(self):
        assert fmt(math.nan) == '—'

    def test_blank_string_becomes_em_dash(self):
        assert fmt('   ') == '—'

    def test_strips_whitespace(self):
        assert fmt('  hello  ') == 'hello'

    def test_non_string_value(self):
        assert fmt(42) == '42'


class TestEsc:
    def test_escapes_html(self):
        assert esc('<script>alert(1)</script>') == (
            '&lt;script&gt;alert(1)&lt;/script&gt;'
        )

    def test_escapes_quotes(self):
        assert esc('"quoted"') == '&quot;quoted&quot;'

    def test_none_becomes_em_dash(self):
        assert esc(None) == '—'


class TestStripPrefix:
    def test_strips_nistir_code_prefix(self):
        assert strip_prefix('10 - Standard Foundations') == 'Standard Foundations'

    def test_no_prefix_returned_unchanged(self):
        assert strip_prefix('Standard Foundations') == 'Standard Foundations'

    def test_none_becomes_em_dash(self):
        assert strip_prefix(None) == '—'

    def test_only_splits_on_first_separator(self):
        assert strip_prefix('10 - Foo - Bar') == 'Foo - Bar'


class TestDoiUrl:
    def test_valid_doi(self):
        assert doi_url('10.1000/xyz123') == 'https://doi.org/10.1000/xyz123'

    def test_valid_https_url_passed_through(self):
        assert doi_url('https://example.com/paper') == 'https://example.com/paper'

    def test_valid_http_url_passed_through(self):
        assert doi_url('http://example.com/paper') == 'http://example.com/paper'

    def test_none_returns_none(self):
        assert doi_url(None) is None

    def test_empty_string_returns_none(self):
        assert doi_url('') is None

    def test_garbage_string_returns_none(self):
        assert doi_url('not a doi or url') is None

    def test_url_with_space_returns_none(self):
        assert doi_url('https://example.com/has space') is None


class TestDoiLink:
    def test_builds_markdown_link_for_doi(self):
        assert doi_link('10.1000/xyz123') == (
            '[https://doi.org/10.1000/xyz123](https://doi.org/10.1000/xyz123)'
        )

    def test_none_for_invalid_doi(self):
        assert doi_link('garbage') is None

    def test_escapes_markdown_in_display_text(self):
        # doi_link() uses the URL as both target and display text, and
        # doi_url() only accepts recognized DOI/http(s) forms, so this
        # exercises the parens-in-target encoding rather than markdown
        # escaping of arbitrary text.
        link = doi_link('https://example.com/paper(v2)')
        assert link == (
            '[https://example.com/paper(v2)](https://example.com/paper%28v2%29)'
        )


class TestBuildCitation:
    def test_non_dict_returns_empty_string(self):
        assert build_citation(None) == ''
        assert build_citation('not a dict') == ''

    def test_full_citation_markdown(self):
        csl = {
            'author': [{'family': 'Smith', 'given': 'Jane'}],
            'issued': {'date-parts': [[2020]]},
            'title': 'A Study of Things',
            'container-title': 'Journal of Studies',
            'DOI': '10.1000/xyz123',
        }
        result = build_citation(csl)
        assert result.startswith('Smith, J. (2020). A Study of Things.')
        assert '*Journal of Studies*.' in result
        assert '[https://doi.org/10.1000/xyz123]' in result

    def test_plain_text_mode_has_no_markdown(self):
        csl = {
            'author': [{'family': 'Smith', 'given': 'Jane'}],
            'issued': {'date-parts': [[2020]]},
            'title': 'A Study of Things',
            'container-title': 'Journal of Studies',
        }
        result = build_citation(csl, markdown=False)
        # markdown=True would wrap the venue in *asterisks*; markdown=False
        # should leave it bare.
        assert '*' not in result
        assert 'Journal of Studies.' in result

    def test_two_authors_joined_with_ampersand(self):
        csl = {
            'author': [
                {'family': 'Smith', 'given': 'Jane'},
                {'family': 'Doe', 'given': 'John'},
            ],
            'issued': {'date-parts': [[2020]]},
            'title': 'Two Authors',
        }
        result = build_citation(csl)
        assert result.startswith('Smith, J. & Doe, J. (2020).')

    def test_three_authors_uses_oxford_comma_and(self):
        csl = {
            'author': [
                {'family': 'Smith', 'given': 'Jane'},
                {'family': 'Doe', 'given': 'John'},
                {'family': 'Lee', 'given': 'Amy'},
            ],
            'issued': {'date-parts': [[2020]]},
            'title': 'Three Authors',
        }
        result = build_citation(csl)
        assert result.startswith('Smith, J., Doe, J., & Lee, A. (2020).')

    def test_missing_fields_produce_empty_string(self):
        assert build_citation({}) == ''

    def test_venue_falls_back_through_alternatives(self):
        csl = {'title': 'X', 'event-title': 'Some Conference'}
        assert '*Some Conference*' in build_citation(csl)


class TestCsvSafe:
    def test_prefixes_formula_trigger_characters(self):
        df = pd.DataFrame({'col': ['=cmd', '+cmd', '-cmd', '@cmd', 'safe']})
        out = csv_safe(df)
        assert out['col'].tolist() == [
            "'=cmd",
            "'+cmd",
            "'-cmd",
            "'@cmd",
            'safe',
        ]

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({'col': ['=cmd']})
        csv_safe(df)
        assert df['col'].tolist() == ['=cmd']

    def test_leaves_non_string_and_numeric_columns_alone(self):
        df = pd.DataFrame({'n': [1, 2, 3]})
        out = csv_safe(df)
        assert out['n'].tolist() == [1, 2, 3]

    def test_ignores_empty_strings_and_none(self):
        df = pd.DataFrame({'col': ['', None]})
        out = csv_safe(df)
        assert out['col'].iloc[0] == ''
        assert pd.isna(out['col'].iloc[1])
