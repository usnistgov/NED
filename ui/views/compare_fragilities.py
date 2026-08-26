import streamlit as st

from db import (
    get_components,
    get_fragility_model_detail,
    get_fragility_models,
    get_groups,
    get_major_groups,
)
from utils import fmt
from views.fragility_model import render_model_body

_PICK_COMPONENT = 'Select a component…'
_PICK_FRAGILITY = 'Select a fragility model…'
_DIFFERENT_EDPS_MESSAGE = (
    'The selected fragility models have different EDPs; Could not directly '
    'compare fragility curves.'
)


def _label(*parts) -> str:
    """Join the meaningful parts of an option label with ' - ', dropping blanks."""
    return ' - '.join(v for v in (fmt(p) for p in parts) if v != '—')


def _edp_of(fragility_id: str) -> tuple[str, str] | None:
    """Return a fragility model's (EDP metric, EDP unit), or None if the
    model can't be found."""
    df_detail = get_fragility_model_detail(fragility_id)
    if df_detail.empty:
        return None
    row = df_detail.iloc[0]
    return fmt(row['edp_metric']), fmt(row['edp_unit'])


def _panel(side: str) -> str | None:
    """Render one half of the comparison: a taxonomy → component → fragility
    drill-down. Returns the selected fragility model id, or None if nothing
    is selected yet."""
    df_all = get_components()

    major_groups = ['All groups'] + get_major_groups()
    selected_group = st.selectbox(
        'NISTIR Major Group', major_groups, key=f'cmp_major_{side}'
    )

    groups = ['All groups'] + get_groups(selected_group)
    selected_subgroup = st.selectbox('NISTIR Group', groups, key=f'cmp_group_{side}')

    df_filt = df_all
    if selected_group != 'All groups':
        df_filt = df_filt[df_filt['major_group'] == selected_group]
    if selected_subgroup != 'All groups':
        df_filt = df_filt[df_filt['Group'] == selected_subgroup]

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
        return None

    return fragility_id


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
        left_id = _panel('left')
    with right:
        right_id = _panel('right')

    edps_differ = False
    if left_id and right_id:
        left_edp = _edp_of(left_id)
        right_edp = _edp_of(right_id)
        edps_differ = (
            left_edp is not None and right_edp is not None and left_edp != right_edp
        )
    plot_message = _DIFFERENT_EDPS_MESSAGE if edps_differ else None

    with left:
        if left_id:
            st.markdown('---')
            render_model_body(
                left_id,
                key_prefix='cmp_left_',
                show_download=False,
                plot_unavailable_message=plot_message,
            )
    with right:
        if right_id:
            st.markdown('---')
            render_model_body(
                right_id,
                key_prefix='cmp_right_',
                show_download=False,
                plot_unavailable_message=plot_message,
            )
