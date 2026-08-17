import pandas as pd

from db import _shape_components_df


class TestShapeComponentsDf:
    """Pure DataFrame-transform tests for the post-processing step split out
    of get_components() -- no DB/fixture involved."""

    def test_strips_code_prefix_from_element_and_subelement(self):
        df = pd.DataFrame({
            'Element': ['1 - Exterior Walls'],
            'Subelement': ['1 - Curtain Walls'],
            'major_group': ['B - SHELL'],
            'Group': ['20 - Exterior Enclosure'],
        })
        out = _shape_components_df(df)
        assert out['Element'].tolist() == ['Exterior Walls']
        assert out['Subelement'].tolist() == ['Curtain Walls']

    def test_missing_subelement_becomes_em_dash(self):
        df = pd.DataFrame({
            'Element': ['1 - Roof Coverings'],
            'Subelement': [None],
            'major_group': ['B - SHELL'],
            'Group': ['30 - Roofing'],
        })
        out = _shape_components_df(df)
        assert out['Subelement'].tolist() == ['—']

    def test_missing_major_group_becomes_em_dash(self):
        df = pd.DataFrame({
            'Element': ['1 - Foo'],
            'Subelement': ['1 - Bar'],
            'major_group': [None],
            'Group': [None],
        })
        out = _shape_components_df(df)
        assert out['major_group'].tolist() == ['—']

    def test_group_gets_major_group_letter_prefixed(self):
        df = pd.DataFrame({
            'Element': ['1 - Foo'],
            'Subelement': ['1 - Bar'],
            'major_group': ['B - SHELL'],
            'Group': ['20 - Exterior Enclosure'],
        })
        out = _shape_components_df(df)
        assert out['Group'].tolist() == ['B20 - Exterior Enclosure']

    def test_does_not_mutate_input_dataframe(self):
        df = pd.DataFrame({
            'Element': ['1 - Foo'],
            'Subelement': ['1 - Bar'],
            'major_group': ['B - SHELL'],
            'Group': ['20 - Exterior Enclosure'],
        })
        _shape_components_df(df)
        assert df['Element'].tolist() == ['1 - Foo']
        assert df['Group'].tolist() == ['20 - Exterior Enclosure']


class TestGetComponents:
    def test_returns_one_row_per_component(self, db_module):
        df = db_module.get_components()
        assert sorted(df['ID'].tolist()) == ['B2011', 'B2012', 'B3010', 'D2010']

    def test_test_and_fragility_model_counts(self, db_module):
        df = db_module.get_components().set_index('ID')
        # B2011 has one experiment (EXP-001) and one fragility model,
        # linked through both bridge tables.
        assert df.loc['B2011', '# Tests'] == 1
        assert df.loc['B2011', '# Fragility Models'] == 1
        # B3010 has neither.
        assert df.loc['B3010', '# Tests'] == 0
        assert df.loc['B3010', '# Fragility Models'] == 0

    def test_group_letter_prefix_applied_through_full_query(self, db_module):
        df = db_module.get_components().set_index('ID')
        assert df.loc['B2011', 'Group'] == 'B20 - Exterior Enclosure'
        assert df.loc['B3010', 'Group'] == 'B30 - Roofing'

    def test_result_is_cached_across_calls(self, db_module):
        first = db_module.get_components()
        second = db_module.get_components()
        assert first is not second  # cache_data returns copies
        pd.testing.assert_frame_equal(first, second)


class TestGetMajorGroups:
    def test_returns_sorted_unique_major_groups(self, db_module):
        assert db_module.get_major_groups() == ['B - SHELL', 'D - SERVICES']


class TestGetGroups:
    def test_no_filter_returns_all_groups(self, db_module):
        groups = db_module.get_groups()
        assert groups == [
            'B20 - Exterior Enclosure',
            'B30 - Roofing',
            'D20 - Plumbing',
        ]

    def test_filtered_by_major_group(self, db_module):
        groups = db_module.get_groups('B - SHELL')
        assert groups == ['B20 - Exterior Enclosure', 'B30 - Roofing']

    def test_all_groups_sentinel_returns_everything(self, db_module):
        assert db_module.get_groups('All groups') == db_module.get_groups()


class TestGetComponentDetail:
    def test_returns_single_row_for_id(self, db_module):
        df = db_module.get_component_detail('B2011')
        assert len(df) == 1
        assert df.iloc[0]['name'] == 'Curtain Wall'
        assert df.iloc[0]['component_id'] == 'B.20.1.1'

    def test_unknown_id_returns_empty(self, db_module):
        df = db_module.get_component_detail('nope')
        assert df.empty


class TestGetComponentFragilityModels:
    def test_returns_linked_models_with_doi(self, db_module):
        df = db_module.get_component_fragility_models('B2011')
        assert df['fragility_model_id'].tolist() == ['Smith-2020|M1']
        assert df.iloc[0]['doi'] == '10.1000/xyz123'

    def test_component_without_models_returns_empty(self, db_module):
        df = db_module.get_component_fragility_models('B3010')
        assert df.empty


class TestGetFragilityModels:
    def test_returns_all_models_with_component_id(self, db_module):
        df = db_module.get_fragility_models()
        assert len(df) == 1
        assert df.iloc[0]['fragility_model_id'] == 'Smith-2020|M1'
        assert df.iloc[0]['comp_id'] == 'B2011'


class TestGetReference:
    def test_returns_reference_row(self, db_module):
        df = db_module.get_reference('Smith-2020')
        assert df.iloc[0]['title'] == 'A Study of Curtain Walls'
        assert df.iloc[0]['year'] == 2020

    def test_csl_data_falls_back_to_url_when_no_doi(self, db_module):
        df = db_module.get_reference('Jones-2021')
        assert '"URL"' in df.iloc[0]['csl_data']


class TestGetFragilityModelDetail:
    def test_returns_model_row(self, db_module):
        df = db_module.get_fragility_model_detail('Smith-2020|M1')
        assert df.iloc[0]['model_id'] == 'M1'
        assert df.iloc[0]['reference_id'] == 'Smith-2020'


class TestGetFragilityCurves:
    def test_returns_curves_ordered_by_ds_rank(self, db_module):
        df = db_module.get_fragility_curves('Smith-2020|M1')
        assert df['DS Rank'].tolist() == [1]
        assert float(df.iloc[0]['Median']) == 0.02


class TestGetFragilityModelExperiments:
    def test_returns_experiments_linked_via_bridge(self, db_module):
        df = db_module.get_fragility_model_experiments('Smith-2020|M1')
        assert df['experiment_id'].tolist() == ['EXP-001']
        assert df.iloc[0]['Source'] == 'Smith, 2020'


class TestGetExperimentFragilityModels:
    def test_reverse_lookup_from_experiment(self, db_module):
        df = db_module.get_experiment_fragility_models('EXP-001')
        assert df['fragility_model_id'].tolist() == ['Smith-2020|M1']

    def test_experiment_without_models_returns_empty(self, db_module):
        df = db_module.get_experiment_fragility_models('EXP-002')
        assert df.empty


class TestGetComponentExperiments:
    def test_returns_experiments_for_component(self, db_module):
        df = db_module.get_component_experiments('B2011')
        assert df['experiment_id'].tolist() == ['EXP-001']
        assert df.iloc[0]['NISTIR Subelement'] == '1 - Curtain Walls'


class TestGetComponentExperimentsExport:
    def test_includes_citation_fields(self, db_module):
        df = db_module.get_component_experiments_export('B2011')
        row = df.iloc[0]
        assert row['author'] == 'Smith'
        assert row['year'] == 2020
        assert row['title'] == 'A Study of Curtain Walls'
        assert row['Test Type'] == 'Dynamic, uniaxial'


class TestGetExperimentDetail:
    def test_returns_full_experiment_row(self, db_module):
        df = db_module.get_experiment_detail('EXP-001')
        row = df.iloc[0]
        assert row['Specimen'] == 'S1'
        assert row['reference_id'] == 'Smith-2020'
        assert row['DS Class'] == 'Consequential'
