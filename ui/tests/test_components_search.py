from views.components import _SEARCH_SYNONYMS, _expand_search_terms


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
        # membership check passes. render() only calls this under
        # `if search:`, so an empty query is never reached in practice --
        # this documents the function's actual behavior in isolation rather
        # than the guarded call site.
        terms = set(_expand_search_terms(''))
        expected = {term for group in _SEARCH_SYNONYMS for term in group}
        assert terms == expected

    def test_whitespace_only_query_behaves_like_empty(self):
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
