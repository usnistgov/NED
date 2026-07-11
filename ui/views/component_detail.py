import pandas as pd
import streamlit as st

from db import (
    get_component_detail,
    get_component_experiments,
    get_component_experiments_export,
    get_component_fragility_models,
    get_component_fragility_models_export,
)
from utils import FIELD_HELP, attr, csv_safe, doi_url, esc, fmt, strip_prefix
from views.experiments_table import render_experiments_table, with_reference


def _experiments_export(component_id: str) -> pd.DataFrame:
    """Experiments export with the same fields shown on the Experiment view
    page, including the reference citation and study type."""
    return with_reference(get_component_experiments_export(component_id))


def _fragilities_export(component_id: str) -> pd.DataFrame:
    """Fragility models export with the same fields shown on the Fragility
    Model view page, including the reference citation and study type — one
    row per fragility curve (damage state)."""
    return with_reference(get_component_fragility_models_export(component_id))


def render() -> None:
    component_id = st.session_state.get('selected_component_id', '')

    if st.button('← Back to Components'):
        st.query_params.clear()
        st.session_state['page'] = 'Components'
        st.rerun()

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
        _FM_WIDTHS = [2, 1.5, 2, 1.5, 1.5, 4, 1]
        _FM_HEADERS = [
            'Reference',
            'Model ID',
            'Component Detail',
            'Material',
            'Size Class',
            'Component Description',
            '',
        ]
        _FM_HEADER_HELP = {
            'Component Detail': FIELD_HELP['comp_detail'],
            'Material': FIELD_HELP['material'],
            'Size Class': FIELD_HELP['size_class'],
        }

        h = st.columns(_FM_WIDTHS)
        for col, label in zip(h, _FM_HEADERS):
            col.markdown(
                f"<span style='font-size:0.8rem;font-weight:600;color:#555;"
                f"text-transform:uppercase;letter-spacing:0.04em;'>{label}</span>",
                unsafe_allow_html=True,
                help=_FM_HEADER_HELP.get(label),
            )
        st.markdown(
            "<hr style='margin:0.25rem 0 0.1rem;border:none;border-top:2px solid #e0e0e0;'>",
            unsafe_allow_html=True,
        )

        for _, fmrow in df_fm.iterrows():
            c = st.columns(_FM_WIDTHS)
            desc = str(fmrow['Component Description'])
            desc_short = desc[:80] + '…' if len(desc) > 80 else desc
            reference = esc(fmrow['Reference'])
            url = doi_url(fmrow['doi'])
            if url:
                reference = f'<a href="{esc(url)}" target="_blank">{reference}</a>'
            for ci, val in zip(
                c[:6],
                [
                    reference,
                    esc(fmrow['Model ID']),
                    esc(fmrow['Component Detail']),
                    esc(fmrow['Material']),
                    esc(fmrow['Size Class']),
                    esc(desc_short),
                ],
            ):
                ci.markdown(
                    f"<span style='font-size:0.88rem;'>{val}</span>",
                    unsafe_allow_html=True,
                )
            if c[6].button('View', key=f'fm_{fmrow["fragility_model_id"]}'):
                st.session_state['selected_fragility_model_id'] = fmrow[
                    'fragility_model_id'
                ]
                st.session_state['page'] = 'Fragility Model Detail'
                st.query_params['fragility_model'] = fmrow['fragility_model_id']
                st.rerun()

        st.download_button(
            'Download Fragilities as CSV',
            csv_safe(_fragilities_export(component_id)).to_csv(index=False),
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
        )
