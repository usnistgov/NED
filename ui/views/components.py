import pandas as pd
import streamlit as st

from db import get_components, get_groups, get_major_groups
from utils import esc, fmt

# Synonym groups for component search.
#
# Each inner list is a set of interchangeable practitioner terms. When a
# search matches any term in a group, every other term in that group is
# searched too — so field vocabulary ("riser", "gypsum", "glazing") reaches
# the canonical component names, elements, and sub-elements stored in the
# database, even when the typed word never appears in the data verbatim.
#
# To extend: add a term to an existing group, or append a new group. No other
# code changes are required — this is the single source of truth for synonyms.
_SEARCH_SYNONYMS: list[list[str]] = [
    [
        'sprinkler',
        'sprinkler drop',
        'riser',
        'branch line',
        'standpipe',
        'fire suppression',
    ],
    ['pipe', 'piping', 'plumbing', 'conduit'],
    ['glass', 'glazing', 'glazed', 'curtain wall', 'storefront', 'window'],
    ['partition', 'drywall', 'gypsum', 'gyp board', 'wall board', 'stud wall'],
    ['hvac', 'duct', 'ductwork', 'diffuser', 'air handler', 'air distribution'],
]


def _expand_search_terms(query: str) -> list[str]:
    """Return the search query plus any synonymous terms.

    A synonym group is pulled in when the query matches one of its terms in
    either substring direction, so both "riser" -> "sprinkler" and
    "sprinkler" -> "riser" expansions resolve. The original query is always
    included so exact matching behavior is never lost.
    """
    q = query.strip().lower()
    terms = {q}
    for group in _SEARCH_SYNONYMS:
        if any(q in term or term in q for term in group):
            terms.update(group)
    return [t for t in terms if t]


def _filter_by_search(df: pd.DataFrame, search: str) -> pd.DataFrame:
    """Return the rows of `df` matching `search`, or all rows if it is blank.

    The guard is on `search.strip()`, not on `search`. A whitespace-only
    query is truthy but _expand_search_terms strips it to '', which is a
    substring of every synonym term, so every group is pulled in while the
    query itself is dropped from the returned list. Filtering on that gives
    an OR over every synonym with nothing that matches everything, silently
    hiding any row that mentions no synonym -- so blank input has to skip
    filtering entirely rather than fall through to the mask.
    """
    if not search.strip():
        return df

    terms = _expand_search_terms(search)
    search_cols = ['ID', 'Name', 'Element', 'Subelement']
    mask = pd.Series(False, index=df.index)
    for term in terms:
        for col in search_cols:
            mask |= df[col].str.contains(term, case=False, na=False, regex=False)
    return df[mask]


def render() -> None:
    st.markdown(
        '<div class="ned-header"><h1>Components</h1></div>',
        unsafe_allow_html=True,
    )

    df_all = get_components()
    total_components = len(df_all)

    st.markdown('---')

    major_groups = ['All groups'] + get_major_groups()
    selected_group = st.selectbox('NISTIR Major Group', major_groups)

    groups = ['All groups'] + get_groups(selected_group)
    selected_subgroup = st.selectbox('NISTIR Group', groups)

    search = st.text_input(
        'Search',
        placeholder='Search by name, ID, element, sub-element, or keyword…',
        label_visibility='collapsed',
    )

    df_display = df_all.copy()

    if selected_group != 'All groups':
        df_display = df_display[df_display['major_group'] == selected_group]

    if selected_subgroup != 'All groups':
        df_display = df_display[df_display['Group'] == selected_subgroup]

    df_display = _filter_by_search(df_display, search)

    df_display = df_display.drop(
        columns=['major_group', 'Group', 'Subelement']
    ).reset_index(drop=True)

    if df_display.empty:
        st.info('No components match the current filters.')
    else:
        _WIDTHS = [1, 1.2, 2.5, 5, 1, 1.5]

        h = st.columns(_WIDTHS)
        for col, label in zip(
            h, ['', 'ID', 'Element', 'Name', '# Tests', '# Fragility Models']
        ):
            col.markdown(
                f"<span style='font-size:0.8rem;font-weight:600;color:#555;"
                f"text-transform:uppercase;letter-spacing:0.04em;'>{label}</span>",
                unsafe_allow_html=True,
            )

        st.markdown(
            "<hr style='margin:0.25rem 0 0.1rem;border:none;border-top:2px solid #e0e0e0;'>",
            unsafe_allow_html=True,
        )

        for _, row in df_display.iterrows():
            c = st.columns(_WIDTHS)
            if c[0].button('View', key=f'comp_{row["ID"]}'):
                st.session_state['selected_component_id'] = row['ID']
                st.session_state['page'] = 'Component Detail'
                st.query_params['component'] = row['ID']
                st.rerun()
            c[1].markdown(
                f"<span style='font-size:0.88rem;'>{esc(row['ID'])}</span>",
                unsafe_allow_html=True,
            )
            c[2].markdown(
                f"<span style='font-size:0.88rem;'>{esc(row['Element'])}</span>",
                unsafe_allow_html=True,
            )
            c[3].markdown(
                f"<span style='font-size:0.88rem;'>{esc(row['Name'])}</span>",
                unsafe_allow_html=True,
            )
            c[4].markdown(
                f"<span style='font-size:0.88rem;'>{int(row['# Tests'])}</span>",
                unsafe_allow_html=True,
            )
            c[5].markdown(
                f"<span style='font-size:0.88rem;'>{int(row['# Fragility Models'])}</span>",
                unsafe_allow_html=True,
            )

        st.caption(f'Showing {len(df_display)} of {total_components} components')
