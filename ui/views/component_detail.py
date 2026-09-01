import pandas as pd
import streamlit as st

from db import (
    get_component_detail,
    get_component_experiments,
    get_component_experiments_export,
    get_component_fragility_models,
    get_component_fragility_models_export,
)
from utils import attr, csv_safe, fmt, strip_prefix
from views.components import last_filters_query_params
from views.experiments_table import render_experiments_table, with_reference
from views.fragility_models_table import render_fragility_models_table


def _experiments_export(component_id: str) -> pd.DataFrame:
    """Experiments export with the same fields shown on the Experiment view
    page, including the reference citation and study type."""
    return with_reference(get_component_experiments_export(component_id))


def _fragilities_export(component_id: str) -> pd.DataFrame:
    """Fragility models export with the same fields shown on the Fragility
    Model view page, including the reference citation and study type — one
    row per fragility curve (damage state)."""
    return with_reference(get_component_fragility_models_export(component_id))


def render(pages: dict) -> None:
    component_id = st.query_params.get('component', '') or st.session_state.get(
        'selected_component_id', ''
    )
    st.session_state['selected_component_id'] = component_id

    st.page_link(
        pages['components'],
        label='← Back to Components',
        query_params=last_filters_query_params(),
    )

    df_comp = get_component_detail(component_id)

    if df_comp.empty:
        st.warning(f"Component '{component_id}' not found.")
        return

    row = df_comp.iloc[0]

    st.markdown(
        '<div class="ned-header"><h1>Component View</h1></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'**{row["id"]}**')
    st.markdown('---')

    attr('Id', fmt(row['id']))
    attr('Component type name', fmt(row['name']))
    attr('Major Group', strip_prefix(row['major_group']))
    attr('Group', strip_prefix(row['group']))
    attr('Element', strip_prefix(row['element']))
    attr('NISTIR Sub Element', strip_prefix(row['subelement']))

    st.markdown('---')

    # ── Fragility Models ──
    st.markdown('## Fragility Models')
    df_fm = get_component_fragility_models(component_id)

    if df_fm.empty:
        st.info('No fragility models are associated with this component.')
    else:
        render_fragility_models_table(df_fm, pages, component_id=component_id)

        st.download_button(
            'Download Fragilities as CSV',
            csv_safe(_fragilities_export(component_id))
            .to_csv(index=False)
            .encode('utf-8-sig'),
            file_name=f'{component_id}_fragility_models.csv',
            mime='text/csv',
            key='fm_csv',
        )

    st.markdown('---')

    # ── Experiments ──
    st.markdown('## Experiments')
    df_exp = get_component_experiments(component_id)

    if df_exp.empty:
        st.info('No experiments are associated with this component.')
    else:
        render_experiments_table(
            df_exp,
            _experiments_export(component_id),
            file_name=f'{component_id}_experiments.csv',
            pages=pages,
            component_id=component_id,
            page_id=component_id,
        )
