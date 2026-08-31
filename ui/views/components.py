import pandas as pd
import streamlit as st

from db import get_components, group_filter_options, resolve_group_filter
from utils import FIELD_HELP, esc, header_span

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

_GROUP_FILTER_HELP = (
    f'{FIELD_HELP["major_group"]} {FIELD_HELP["group"]} Major groups are '
    'listed above their groups — pick one to filter to everything under '
    'it, or pick a specific group indented beneath it.'
)

_WIDTHS = [1.1, 1, 2, 2.3, 3.1, 1, 1.6]
_HEADERS = [
    '',
    'ID',
    'Group',
    'Subelement',
    'Component',
    '# Tests',
    '# Fragility Models',
]
_COLUMN_HELP = {'Group': FIELD_HELP['group'], 'Subelement': FIELD_HELP['subelement']}

# Session-state key the current Group/Search filters are mirrored into,
# alongside the URL, so the "Back to Components" link on the detail page can
# still send the user back to them — that link sets an explicit target URL
# rather than inheriting the one being left, so the URL alone isn't enough
# there the way it is for a real browser Back/Forward press.
_FILTER_STATE_KEY = 'components_last_filters'


def last_filters_query_params() -> dict[str, str]:
    """The Group/Search filters last applied on this page, as page_link
    query params, for the detail pages' "Back to Components" link."""
    return dict(st.session_state.get(_FILTER_STATE_KEY, {}))


def _sync_filters(selected_option: str, search: str, all_groups_option: str) -> None:
    """Mirror the current filters into the URL — so a real browser
    Back/Forward restores them and the view can be bookmarked/shared — and
    into session_state (see `_FILTER_STATE_KEY`). Only non-default values are
    written, keeping the URL clean when no filter is active."""
    active: dict[str, str] = {}
    if selected_option != all_groups_option:
        active['group'] = selected_option
    if search:
        active['search'] = search

    for name in ('group', 'search'):
        if name in active:
            st.query_params[name] = active[name]
        elif name in st.query_params:
            del st.query_params[name]

    st.session_state[_FILTER_STATE_KEY] = active


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


def _cell(col, value) -> None:
    """Render one cell's text at the table's body font size."""
    col.markdown(
        f"<span style='font-size:0.88rem;'>{value}</span>",
        unsafe_allow_html=True,
    )


def _render_table(df: pd.DataFrame, pages: dict) -> None:
    """Render the header row plus one plain row per component."""
    h = st.columns(_WIDTHS)
    for col, label in zip(h, _HEADERS):
        col.markdown(
            header_span(label, _COLUMN_HELP.get(label)),
            unsafe_allow_html=True,
        )

    st.markdown(
        "<hr style='margin:0.25rem 0 0.1rem;border:none;border-top:2px solid #e0e0e0;'>",
        unsafe_allow_html=True,
    )

    for i, (_, row) in enumerate(df.iterrows()):
        c = st.columns(_WIDTHS)
        with c[0].container(key=f'view-link-comp-{i}'):
            st.page_link(
                pages['component_detail'],
                label='View',
                query_params={'component': row['ID']},
            )
        _cell(c[1], esc(row['ID']))
        _cell(c[2], esc(row['Group']))
        _cell(c[3], esc(row['Subelement']))
        _cell(c[4], esc(row['Name']))
        _cell(c[5], int(row['# Tests']))
        _cell(c[6], int(row['# Fragility Models']))


def render(pages: dict) -> None:
    st.markdown(
        '<div class="ned-header"><h1>Components</h1></div>',
        unsafe_allow_html=True,
    )

    df_all = get_components()
    total_components = len(df_all)

    st.markdown('---')

    group_options, group_labels = group_filter_options()
    saved_filters = st.session_state.get(_FILTER_STATE_KEY, {})
    default_group = st.query_params.get('group') or saved_filters.get('group')
    if default_group not in group_options:
        default_group = group_options[0]
    default_search = st.query_params.get('search') or saved_filters.get('search', '')

    selected_option = st.selectbox(
        'Group',
        group_options,
        index=group_options.index(default_group),
        format_func=lambda v: group_labels.get(v, v),
        help=_GROUP_FILTER_HELP,
        key='components_group_filter',
    )
    major_filter, group_filter = resolve_group_filter(selected_option)

    search = st.text_input(
        'Search',
        value=default_search,
        placeholder='Search by name, ID, element, sub-element, or keyword…',
        label_visibility='collapsed',
        key='components_search',
    )

    _sync_filters(selected_option, search, group_options[0])

    df_display = df_all.copy()

    if major_filter:
        df_display = df_display[df_display['major_group'] == major_filter]
    if group_filter:
        df_display = df_display[df_display['Group'] == group_filter]

    if search:
        terms = _expand_search_terms(search)
        search_cols = ['ID', 'Name', 'Element', 'Subelement']
        mask = pd.Series(False, index=df_display.index)
        for term in terms:
            for col in search_cols:
                mask |= df_display[col].str.contains(
                    term, case=False, na=False, regex=False
                )
        df_display = df_display[mask]

    if df_display.empty:
        st.info('No components match the current filters.')
        return

    _render_table(df_display, pages)

    st.caption(f'Showing {len(df_display)} of {total_components} components')
