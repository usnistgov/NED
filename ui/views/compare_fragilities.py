import streamlit as st

from db import (
    get_components,
    get_fragility_models,
    group_filter_options,
    resolve_group_filter,
)
from utils import FIELD_HELP, fmt
from views.fragility_model import render_model_body

_PICK_COMPONENT = 'Select a component…'
_PICK_FRAGILITY = 'Select a fragility model…'

_GROUP_FILTER_HELP = (
    f'{FIELD_HELP["major_group"]} {FIELD_HELP["group"]} Major groups are '
    'listed above their groups — pick one to filter to everything under '
    'it, or pick a specific group indented beneath it.'
)


def _label(*parts) -> str:
    """Join the meaningful parts of an option label with ' - ', dropping blanks."""
    return ' - '.join(v for v in (fmt(p) for p in parts) if v != '—')


def _panel(side: str) -> None:
    """Render one half of the comparison: a taxonomy → component → fragility
    drill-down, followed by the selected model's detail."""
    df_all = get_components()

    group_options, group_labels = group_filter_options()
    selected_option = st.selectbox(
        'Group',
        group_options,
        format_func=lambda v: group_labels.get(v, v),
        help=_GROUP_FILTER_HELP,
        key=f'cmp_group_{side}',
    )
    major_filter, group_filter = resolve_group_filter(selected_option)

    df_filt = df_all
    if major_filter:
        df_filt = df_filt[df_filt['major_group'] == major_filter]
    if group_filter:
        df_filt = df_filt[df_filt['Group'] == group_filter]

    # Label each component option as "ID - Element - Name".
    comp_labels = {
        row['ID']: _label(row['ID'], row['Element'], row['Name'])
        for _, row in df_filt.iterrows()
    }
    component_id = st.selectbox(
        'Component',
        [_PICK_COMPONENT] + df_filt['ID'].tolist(),
        format_func=lambda cid: cid
        if cid == _PICK_COMPONENT
        else comp_labels.get(cid, cid),
        key=f'cmp_comp_{side}',
    )

    # Full fragility list, narrowed by the same taxonomy as the component list,
    # and further to a single component when one is selected.
    df_fm = get_fragility_models()
    df_fm = df_fm[df_fm['comp_id'].isin(set(df_filt['ID']))]
    if component_id != _PICK_COMPONENT:
        df_fm = df_fm[df_fm['comp_id'] == component_id]
    df_fm = df_fm.drop_duplicates(subset=['fragility_model_id'])

    # Label each fragility option as "ID - Component Detail - Material".
    fm_labels = {
        row['fragility_model_id']: _label(
            row['fragility_model_id'], row['comp_detail'], row['material']
        )
        for _, row in df_fm.iterrows()
    }
    fragility_id = st.selectbox(
        'Fragility',
        [_PICK_FRAGILITY] + df_fm['fragility_model_id'].tolist(),
        format_func=lambda fid: fid
        if fid == _PICK_FRAGILITY
        else fm_labels.get(fid, fid),
        key=f'cmp_frag_{side}',
    )

    if fragility_id == _PICK_FRAGILITY:
        return

    st.markdown('---')
    render_model_body(fragility_id, key_prefix=f'cmp_{side}_', show_download=False)


def render() -> None:
    return_to_fragility = st.session_state.get('compare_return_to_fragility')
    if return_to_fragility:
        if st.button('← Back to Fragility Model'):
            st.session_state['selected_fragility_model_id'] = return_to_fragility
            st.session_state.pop('compare_return_to_fragility', None)
            st.session_state['page'] = 'Fragility Model Detail'
            st.query_params.clear()
            st.query_params['fragility_model'] = return_to_fragility
            st.rerun()

    st.markdown(
        '<div class="ned-header"><h1>Compare Fragilities</h1></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        'Drill down to a fragility model on each side to compare them side by side.'
    )
    st.markdown('---')

    left, right = st.columns(2, gap='large')
    with left:
        _panel('left')
    with right:
        _panel('right')
