import json
import math

import pandas as pd
import streamlit as st

from utils import FIELD_HELP, build_citation, csv_safe, doi_url, esc, fmt

# Rows shown per page. Rendering every experiment at once makes the heavily
# referenced models (200+ experiments) slow to build on each rerun and slow
# to paint in the browser, so long tables are paginated.
_PAGE_SIZE = 50

_EXP_WIDTHS = [1.5, 2, 1.5, 2, 1, 1.5, 1]
_EXP_HEADERS = [
    'Reference',
    'Test Type',
    'Location',
    'EDP Metric',
    'EDP Value',
    'DS Class',
    '',
]
_EXP_HEADER_HELP = {
    'DS Class': FIELD_HELP['ds_class'],
}


def plain_citation(row: pd.Series) -> str:
    """Plain-text citation from a row carrying 'csl_data', 'author', 'year',
    and 'title' columns, matching the citation shown on the detail pages."""
    try:
        csl = json.loads(row['csl_data']) if row['csl_data'] else {}
    except (ValueError, TypeError):
        csl = {}
    cite = build_citation(csl, markdown=False)
    if not cite and not (pd.isna(row['author']) and pd.isna(row['title'])):
        cite = f'{fmt(row["author"])} ({fmt(row["year"])}). {fmt(row["title"])}.'
    return cite


def with_reference(df: pd.DataFrame) -> pd.DataFrame:
    """Replace the raw reference columns with a 'Reference' citation column
    placed just before 'Study Type'."""
    df.insert(
        df.columns.get_loc('Study Type'),
        'Reference',
        df.apply(plain_citation, axis=1),
    )
    return df.drop(columns=['author', 'year', 'title', 'csl_data'])


def render_experiments_table(
    df_exp: pd.DataFrame,
    df_export: pd.DataFrame,
    file_name: str,
    key_prefix: str = '',
) -> None:
    """Render the experiments summary table (header row, one row per
    experiment with a View button, and a CSV download of ``df_export``).
    Shared by the component detail and fragility model views; ``key_prefix``
    keeps widget keys unique across pages. Tables longer than ``_PAGE_SIZE``
    are paginated; the CSV download always contains every experiment."""
    n = len(df_exp)
    if n > _PAGE_SIZE:
        n_pages = math.ceil(n / _PAGE_SIZE)
        page_key = f'{key_prefix}exp_page'
        # Clamp state left over from a longer table viewed earlier so the
        # widget doesn't raise when its max shrinks.
        if st.session_state.get(page_key, 1) > n_pages:
            st.session_state[page_key] = n_pages
        c_info, c_page = st.columns([5, 1], vertical_alignment='bottom')
        page = c_page.number_input(
            'Page', min_value=1, max_value=n_pages, key=page_key
        )
        start = (page - 1) * _PAGE_SIZE
        stop = min(start + _PAGE_SIZE, n)
        c_info.caption(
            f'Showing experiments {start + 1}–{stop} of {n} '
            f'(page {page} of {n_pages}). The CSV download includes all '
            'experiments.'
        )
        df_exp = df_exp.iloc[start:stop]

    h = st.columns(_EXP_WIDTHS)
    for col, label in zip(h, _EXP_HEADERS):
        col.markdown(
            f"<span style='font-size:0.8rem;font-weight:600;color:#555;"
            f"text-transform:uppercase;letter-spacing:0.04em;'>{label}</span>",
            unsafe_allow_html=True,
            help=_EXP_HEADER_HELP.get(label),
        )
    st.markdown(
        "<hr style='margin:0.25rem 0 0.1rem;border:none;border-top:2px solid #e0e0e0;'>",
        unsafe_allow_html=True,
    )

    for _, erow in df_exp.iterrows():
        c = st.columns(_EXP_WIDTHS)
        source = esc(erow['Source'])
        url = doi_url(erow['doi'])
        if url:
            source = f'<a href="{esc(url)}" target="_blank">{source}</a>'
        for ci, val in zip(
            c[:6],
            [
                source,
                esc(erow['Test Type']),
                esc(erow['Location']),
                esc(erow['EDP Metric']),
                esc(erow['EDP Value']),
                esc(erow['DS Class']),
            ],
        ):
            ci.markdown(
                f"<span style='font-size:0.88rem;'>{val}</span>",
                unsafe_allow_html=True,
            )
        if c[6].button('View', key=f'{key_prefix}exp_{erow["experiment_id"]}'):
            st.session_state['selected_experiment_id'] = erow['experiment_id']
            st.session_state['page'] = 'Experiment Detail'
            st.query_params['experiment'] = erow['experiment_id']
            st.rerun()

    st.download_button(
        'Download Experiments as CSV',
        csv_safe(df_export).to_csv(index=False),
        file_name=file_name,
        mime='text/csv',
        key=f'{key_prefix}exp_csv',
    )
