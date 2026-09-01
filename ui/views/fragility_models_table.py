import pandas as pd
import streamlit as st

from utils import FIELD_HELP, clamp_cell, esc, fmt, header_span

_FM_COLUMN_WIDTHS = {
    '': 1,
    'Fragility Model ID': 2.5,
    'Component Type': 1.8,
    'Component Detail': 1.8,
    'Material': 1.3,
    'Size Class': 1.3,
    'Component Description': 2.6,
    'Number of Tests': 1.3,
}
_FM_HEADER_HELP = {
    'Component Detail': FIELD_HELP['comp_detail'],
    'Material': FIELD_HELP['material'],
    'Size Class': FIELD_HELP['size_class'],
    'Number of Tests': FIELD_HELP['number_of_tests'],
}


def _has_values(series: pd.Series) -> bool:
    """Whether at least one entry in ``series`` has a real (non-blank) value,
    using the same notion of "blank" as the rest of the table (``fmt()``
    turns ``None``/``NaN``/empty strings into '—')."""
    return series.apply(fmt).ne('—').any()


def render_fragility_models_table(
    df_fm: pd.DataFrame,
    pages: dict,
    component_id: str = '',
    key_prefix: str = '',
) -> None:
    """Render the Fragility Models summary table (header row, one row per
    model with a View button). Shared by the Component and Experiment detail
    views, which both list the fragility models linked to their record.
    Material and Size Class are subcategory fields that are often left blank
    on a given model, so each is only shown as a column when at least one row
    of ``df_fm`` actually has a value — an all-blank column would otherwise
    take up table width on every page for nothing."""
    headers = ['', 'Fragility Model ID', 'Component Type', 'Component Detail']
    if _has_values(df_fm['Material']):
        headers.append('Material')
    if _has_values(df_fm['Size Class']):
        headers.append('Size Class')
    headers += ['Component Description', 'Number of Tests']
    widths = [_FM_COLUMN_WIDTHS[h] for h in headers]

    h = st.columns(widths)
    for col, label in zip(h, headers):
        col.markdown(
            header_span(label, _FM_HEADER_HELP.get(label)),
            unsafe_allow_html=True,
        )
    st.markdown(
        "<hr style='margin:0.25rem 0 0.1rem;border:none;border-top:2px solid #e0e0e0;'>",
        unsafe_allow_html=True,
    )

    for i, (_, fmrow) in enumerate(df_fm.iterrows()):
        c = st.columns(widths)
        query_params = {'fragility_model': fmrow['Fragility Model ID']}
        if component_id:
            query_params['component'] = component_id
        with c[0].container(key=f'view-link-fm-{key_prefix}{i}'):
            st.page_link(
                pages['fragility_model'], label='View', query_params=query_params
            )
        values = [
            esc(fmrow['Fragility Model ID']),
            esc(fmrow['Component Type']),
            esc(fmrow['Component Detail']),
        ]
        if 'Material' in headers:
            values.append(esc(fmrow['Material']))
        if 'Size Class' in headers:
            values.append(esc(fmrow['Size Class']))
        values += [
            clamp_cell(fmrow['Component Description']),
            esc(fmrow['Number of Tests']),
        ]

        for ci, val in zip(c[1:], values):
            ci.markdown(
                f"<span style='font-size:0.88rem;'>{val}</span>",
                unsafe_allow_html=True,
            )
