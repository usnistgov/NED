import pandas as pd
import streamlit as st

from db import (
    get_component_detail,
    get_component_experiments,
    get_component_experiments_export,
    get_component_fragility_models,
    get_component_fragility_models_export,
)
from utils import (
    FIELD_HELP,
    attr,
    csv_safe,
    doi_url,
    esc,
    fmt,
    header_span,
    strip_prefix,
)
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


def render(pages: dict) -> None:
    component_id = st.query_params.get('component', '') or st.session_state.get(
        'selected_component_id', ''
    )
    st.session_state['selected_component_id'] = component_id

    st.page_link(pages['components'], label='← Back to Components')

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
        # The ID column is wide enough to hold a fragility model id on one
        # line: they run to ~24 characters for ~90% of models, and at the
        # previous 1.5 every id wrapped to two lines. The width comes out of
        # Material, Size Class and Component Description, which have slack —
        # measured against the components with the longest values in each,
        # this costs no extra table height.
        _FM_WIDTHS = [1, 2.5, 2, 1.3, 1.3, 3.4, 2]
        _FM_HEADERS = [
            '',
            'Fragility Model ID',
            'Component Detail',
            'Material',
            'Size Class',
            'Component Description',
            'Reference',
        ]
        _FM_HEADER_HELP = {
            'Component Detail': FIELD_HELP['comp_detail'],
            'Material': FIELD_HELP['material'],
            'Size Class': FIELD_HELP['size_class'],
        }

        h = st.columns(_FM_WIDTHS)
        for col, label in zip(h, _FM_HEADERS):
            col.markdown(
                header_span(label, _FM_HEADER_HELP.get(label)),
                unsafe_allow_html=True,
            )
        st.markdown(
            "<hr style='margin:0.25rem 0 0.1rem;border:none;border-top:2px solid #e0e0e0;'>",
            unsafe_allow_html=True,
        )

        for _, fmrow in df_fm.iterrows():
            c = st.columns(_FM_WIDTHS)
            c[0].page_link(
                pages['fragility_model'],
                label='View',
                query_params={
                    'fragility_model': fmrow['Fragility Model ID'],
                    'component': component_id,
                },
            )
            desc = str(fmrow['Component Description'])
            desc_short = desc[:80] + '…' if len(desc) > 80 else desc
            reference = esc(fmrow['Reference'])
            url = doi_url(fmrow['doi'])
            if url:
                reference = f'<a href="{esc(url)}" target="_blank">{reference}</a>'
            for ci, val in zip(
                c[1:],
                [
                    esc(fmrow['Fragility Model ID']),
                    esc(fmrow['Component Detail']),
                    esc(fmrow['Material']),
                    esc(fmrow['Size Class']),
                    esc(desc_short),
                    reference,
                ],
            ):
                ci.markdown(
                    f"<span style='font-size:0.88rem;'>{val}</span>",
                    unsafe_allow_html=True,
                )

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
