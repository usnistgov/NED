import pandas as pd

from views.components import (
    _SEARCH_SYNONYMS,
    _expand_search_terms,
    _filter_by_search,
)


class TestExpandSearchTerms:
    def test_query_with_no_synonym_match_returns_only_itself(self):
        assert _expand_search_terms('concrete') == ['concrete']

    def test_query_is_lowercased_and_stripped(self):
        assert _expand_search_terms('  Concrete  ') == ['concrete']

    def test_exact_synonym_term_pulls_in_whole_group(self):
        terms = set(_expand_search_terms('riser'))
        assert terms == {
            'sprinkler',
            'sprinkler drop',
            'riser',
            'branch line',
            'standpipe',
            'fire suppression',
        }

    def test_substring_of_synonym_term_pulls_in_group(self):
        # 'gyp' is a substring of both 'gypsum' and 'gyp board', and the
        # group-membership check matches in either substring direction, so
        # it pulls in the whole partition group.
        terms = set(_expand_search_terms('gyp'))
        assert terms == {
            'gyp',
            'partition',
            'drywall',
            'gypsum',
            'gyp board',
            'wall board',
            'stud wall',
        }

    def test_query_containing_synonym_term_pulls_in_group(self):
        # 'glazing' is itself a term in the glass group; a longer query that
        # contains it as a substring should still match.
        terms = set(_expand_search_terms('impact glazing'))
        assert 'glass' in terms
        assert 'curtain wall' in terms

    def test_original_query_always_included(self):
        terms = _expand_search_terms('sprinkler')
        assert 'sprinkler' in terms

    def test_empty_query_matches_every_synonym_group(self):
        # An empty string is a substring of every term, so every group's
        # membership check passes. _filter_by_search only calls this once
        # search.strip() is non-empty, so a blank query never reaches it in
        # practice -- this documents the function's behavior in isolation
        # rather than the guarded call site.
        terms = set(_expand_search_terms(''))
        expected = {term for group in _SEARCH_SYNONYMS for term in group}
        assert terms == expected

    def test_whitespace_only_query_expands_to_every_synonym_group(self):
        # Same mechanism as the empty case: the query is stripped to ''
        # before the membership check. Note the stripped query itself is
        # dropped by the final filter, so nothing in the returned list
        # matches every row -- see TestFilterBySearch for why that makes
        # the call-site guard load-bearing.
        terms = set(_expand_search_terms('   '))
        expected = {term for group in _SEARCH_SYNONYMS for term in group}
        assert terms == expected

    def test_every_synonym_group_is_reachable_from_each_of_its_terms(self):
        # Every term in every group should, on its own, expand to the whole
        # group -- this is what makes the search "any synonym reaches all
        # synonyms" claim in the module docstring actually true.
        for group in _SEARCH_SYNONYMS:
            for term in group:
                assert set(group).issubset(set(_expand_search_terms(term)))

    def test_result_has_no_duplicates(self):
        terms = _expand_search_terms('pipe')
        assert len(terms) == len(set(terms))


class TestFilterBySearch:
    """Search filtering, including the blank-query guard that decides
    whether filtering runs at all."""

    @staticmethod
    def _df() -> pd.DataFrame:
        return pd.DataFrame({
            'ID': ['B2011', 'B3010', 'D2010'],
            'Name': ['Curtain Wall', 'Built-Up Roofing', 'Sprinkler Riser'],
            'Element': ['Exterior Walls', 'Roof Coverings', 'Fire Protection'],
            'Subelement': ['Curtain Walls', '—', '—'],
        })

    def test_empty_query_returns_every_row(self):
        df = self._df()
        assert _filter_by_search(df, '')['ID'].tolist() == df['ID'].tolist()

    def test_whitespace_only_query_returns_every_row(self):
        # Regression: '   ' is truthy, so guarding on `search` rather than
        # `search.strip()` let filtering run. The expansion is an OR over
        # every synonym with no catch-all term, so rows mentioning no
        # synonym -- here 'Built-Up Roofing' -- silently disappeared.
        df = self._df()
        assert _filter_by_search(df, '   ')['ID'].tolist() == df['ID'].tolist()

    def test_whitespace_only_query_returns_every_row_from_real_query(
        self, db_module
    ):
        # Same assertion against the columns get_components() actually
        # emits, so a renamed alias in _COMPONENTS_QUERY is caught too.
        df = db_module.get_components()
        assert len(_filter_by_search(df, '   ')) == len(df)

    def test_matches_are_case_insensitive_and_span_searchable_columns(self):
        df = self._df()
        assert _filter_by_search(df, 'ROOF')['ID'].tolist() == ['B3010']
        assert _filter_by_search(df, 'b2011')['ID'].tolist() == ['B2011']

    def test_synonym_expansion_widens_the_match(self):
        # 'standpipe' appears nowhere in the data, but it shares a
        # synonym group with 'sprinkler', which matches D2010's Name.
        df = self._df()
        assert _filter_by_search(df, 'standpipe')['ID'].tolist() == ['D2010']

    def test_query_matching_nothing_returns_empty(self):
        assert _filter_by_search(self._df(), 'zzzz').empty

    def test_does_not_mutate_input_dataframe(self):
        df = self._df()
        _filter_by_search(df, 'roof')
        assert len(df) == 3
