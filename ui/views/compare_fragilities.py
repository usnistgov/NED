import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import (
    get_components,
    get_fragility_curves,
    get_fragility_models,
    group_filter_options,
    resolve_group_filter,
)
from utils import FIELD_HELP, clamp_cell, esc, fmt
from views.fragility_model import (
    get_model_attributes,
    lognormal_curves,
    median_display,
)

_PICK_COMPONENT = 'Select a component…'
_PICK_FRAGILITY = 'Select a fragility model…'
_DIFFERENT_EDPS_MESSAGE = (
    'The selected fragility models have different EDPs; Could not directly '
    'compare fragility curves.'
)

_DS_ATTRS = ['DS Description', 'Median', 'Beta', 'Probability']
_DS_ATTR_FORMATS = {'Median': '{:.4f}', 'Beta': '{:.3f}', 'Probability': '{:.2f}'}
_SIDE_COLORS = (px.colors.qualitative.Plotly[0], px.colors.qualitative.Plotly[1])
_DASH_PATTERNS = ['solid', 'dash', 'dot', 'dashdot', 'longdash', 'longdashdot']
_ATTR_WIDTHS = [1, 2, 2]

_GROUP_FILTER_HELP = (
    f'{FIELD_HELP["major_group"]} {FIELD_HELP["group"]} Major groups are '
    'listed above their groups — pick one to filter to everything under '
    'it, or pick a specific group indented beneath it.'
)


def _label(*parts) -> str:
    """Join the meaningful parts of an option label with ' - ', dropping blanks."""
    return ' - '.join(v for v in (fmt(p) for p in parts) if v != '—')


def _is_blank(v) -> bool:
    if pd.isna(v):
        return True
    return isinstance(v, str) and (not v.strip() or v == '—')


def _render_table_header() -> None:
    """Render the shared 'Baseline'/'Comparison' header row that sits above
    both the taxonomy picker rows and the model-attribute rows below them, so
    the two blocks read as one continuous table."""
    header = st.columns(_ATTR_WIDTHS)
    header[1].markdown('**Baseline**')
    with header[2].container(key='cmp-attr-right-header'):
        st.markdown('**Comparison**')


def _render_picker_row(
    row_key: str,
    label: str,
    options_left: list,
    options_right: list,
    key_left: str,
    key_right: str,
    format_left=None,
    format_right=None,
    help_text: str | None = None,
) -> tuple:
    """Render one taxonomy-picker row: a bold label on the left, and a
    baseline/comparison selectbox pair on the right, laid out with the same
    column widths (and the same comparison-column divider styling) as the
    model-attribute rows below, so the pickers read as the table's first
    rows rather than a separate section."""
    row = st.columns(_ATTR_WIDTHS)
    row[0].markdown(f'**{label}**', help=help_text)

    kwargs_left = {'label_visibility': 'collapsed'}
    if format_left is not None:
        kwargs_left['format_func'] = format_left
    val_left = row[1].selectbox(label, options_left, key=key_left, **kwargs_left)

    kwargs_right = {'label_visibility': 'collapsed'}
    if format_right is not None:
        kwargs_right['format_func'] = format_right
    with row[2].container(key=f'cmp-attr-right-sel-{row_key}'):
        val_right = st.selectbox(label, options_right, key=key_right, **kwargs_right)

    return val_left, val_right


def _render_selection_rows() -> tuple[str | None, str | None]:
    """Render the group / component / fragility drill-down as the first
    three rows of the merged model-attributes table — a baseline
    and a comparison selectbox side by side for each — replacing the old
    separate 'Select baseline/comparison fragility' sections. Returns the
    selected fragility model id for each side, or None if not yet selected."""
    df_all = get_components()
    group_options, group_labels = group_filter_options()

    def _group_format(v):
        return group_labels.get(v, v)

    group_left, group_right = _render_picker_row(
        'group',
        'Group',
        group_options,
        group_options,
        'cmp_group_left',
        'cmp_group_right',
        _group_format,
        _group_format,
        help_text=_GROUP_FILTER_HELP,
    )

    def _filtered(option: str) -> pd.DataFrame:
        major_filter, group_filter = resolve_group_filter(option)
        df = df_all
        if major_filter:
            df = df[df['major_group'] == major_filter]
        if group_filter:
            df = df[df['Group'] == group_filter]
        return df

    df_filt_left = _filtered(group_left)
    df_filt_right = _filtered(group_right)

    def _comp_format(df: pd.DataFrame):
        # Label each component option as "ID - Element - Name".
        labels = {
            row['ID']: _label(row['ID'], row['Element'], row['Name'])
            for _, row in df.iterrows()
        }
        return lambda cid: cid if cid == _PICK_COMPONENT else labels.get(cid, cid)

    component_left, component_right = _render_picker_row(
        'comp',
        'Component',
        [_PICK_COMPONENT] + df_filt_left['ID'].tolist(),
        [_PICK_COMPONENT] + df_filt_right['ID'].tolist(),
        'cmp_comp_left',
        'cmp_comp_right',
        _comp_format(df_filt_left),
        _comp_format(df_filt_right),
    )

    def _fragility_options(df_filt: pd.DataFrame, component_id: str) -> pd.DataFrame:
        # Full fragility list, narrowed by the same taxonomy as the component
        # list, and further to a single component when one is selected.
        df_fm = get_fragility_models()
        df_fm = df_fm[df_fm['comp_id'].isin(set(df_filt['ID']))]
        if component_id != _PICK_COMPONENT:
            df_fm = df_fm[df_fm['comp_id'] == component_id]
        return df_fm.drop_duplicates(subset=['fragility_model_id'])

    df_fm_left = _fragility_options(df_filt_left, component_left)
    df_fm_right = _fragility_options(df_filt_right, component_right)

    def _fm_format(df: pd.DataFrame):
        # Label each fragility option as "ID - Component Detail - Material".
        labels = {
            row['fragility_model_id']: _label(
                row['fragility_model_id'], row['comp_detail'], row['material']
            )
            for _, row in df.iterrows()
        }
        return lambda fid: fid if fid == _PICK_FRAGILITY else labels.get(fid, fid)

    fragility_left, fragility_right = _render_picker_row(
        'frag',
        'Fragility',
        [_PICK_FRAGILITY] + df_fm_left['fragility_model_id'].tolist(),
        [_PICK_FRAGILITY] + df_fm_right['fragility_model_id'].tolist(),
        'cmp_frag_left',
        'cmp_frag_right',
        _fm_format(df_fm_left),
        _fm_format(df_fm_right),
    )

    return (
        None if fragility_left == _PICK_FRAGILITY else fragility_left,
        None if fragility_right == _PICK_FRAGILITY else fragility_right,
    )


def _rank_dashes(plot_dfs: list[pd.DataFrame | None]) -> dict[int, str]:
    """Assign a stable dash style per damage-state rank, shared across both
    sides so the same damage state reads with the same line style regardless
    of which fragility it belongs to (color is reserved for the fragility)."""
    ranks = sorted({
        int(r) for df in plot_dfs if df is not None for r in df['_rank'].unique()
    })
    return {
        rank: _DASH_PATTERNS[i % len(_DASH_PATTERNS)] for i, rank in enumerate(ranks)
    }


def _add_curve_traces(
    fig: go.Figure,
    plot_df: pd.DataFrame | None,
    x_title: str,
    color: str,
    rank_dashes: dict[int, str],
    side_label: str,
) -> None:
    if plot_df is None:
        return
    for _, group in plot_df.sort_values(['_rank', 'EDP']).groupby(
        'Damage State', sort=False
    ):
        rank = int(group['_rank'].iloc[0])
        fig.add_trace(
            go.Scatter(
                x=group['EDP'],
                y=group['Probability'],
                mode='lines',
                name=f'{side_label} — DS {rank}',
                line=dict(color=color, dash=rank_dashes.get(rank, 'solid')),
                hovertemplate=(
                    f'{x_title}: %{{x:.3f}}<br>Probability: %{{y:.2f}}<extra></extra>'
                ),
            )
        )


def _render_comparison_chart(
    curves_left: pd.DataFrame | None,
    curves_right: pd.DataFrame | None,
    x_title_left: str,
    x_title_right: str,
    label_left: str,
    label_right: str,
) -> None:
    plot_left = lognormal_curves(curves_left) if curves_left is not None else None
    plot_right = lognormal_curves(curves_right) if curves_right is not None else None

    if plot_left is None and plot_right is None:
        st.info('No fragility curves with usable median/beta values to plot.')
        return

    # Both x titles carry the side's EDP metric and unit, so an unequal pair
    # means the two sets of curves live on different x axes and overlaying
    # them wouldn't be a valid comparison. The damage-state table below still
    # renders — only the shared chart is withheld.
    if plot_left is not None and plot_right is not None:
        if x_title_left != x_title_right:
            st.info(_DIFFERENT_EDPS_MESSAGE)
            return

    x_title = x_title_left if plot_left is not None else x_title_right

    rank_dashes = _rank_dashes([plot_left, plot_right])
    fig = go.Figure()
    _add_curve_traces(
        fig, plot_left, x_title, _SIDE_COLORS[0], rank_dashes, label_left
    )
    _add_curve_traces(
        fig, plot_right, x_title, _SIDE_COLORS[1], rank_dashes, label_right
    )

    fig.update_layout(
        height=420,
        autosize=True,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(title=x_title, showgrid=False),
        yaxis=dict(
            title='Probability of Exceedance',
            range=[0, 1],
            showgrid=True,
            gridcolor='#e0e0e0',
        ),
        hovermode='closest',
        hoverdistance=12,
        legend=dict(
            orientation='v',
            x=1.02,
            y=1,
            xanchor='left',
            yanchor='top',
            font=dict(size=11),
        ),
    )
    st.plotly_chart(fig, width='stretch', key='cmp_curves_chart')
    st.caption(
        f'Color = fragility ({label_left} vs {label_right}). '
        'Line style = damage state.'
    )


def _attribute_rows(
    items_left: list[tuple[str, str, str | None]] | None,
    items_right: list[tuple[str, str, str | None]] | None,
) -> list[tuple[str, str | None, str, str]]:
    """Build one row per identity/reference attribute as
    ``(label, help_text, left value, right value)``, defaulting a missing
    value to '—'. Yields no rows at all if neither side is selected yet."""
    values_left = (
        {label: value for label, value, _ in items_left} if items_left else {}
    )
    values_right = (
        {label: value for label, value, _ in items_right} if items_right else {}
    )
    help_by_label: dict[str, str | None] = {}
    for items in (items_left, items_right):
        for label, _, help_text in items or []:
            help_by_label.setdefault(label, help_text)
    order = [label for label, _, _ in (items_left or items_right or [])]

    return [
        (
            label,
            help_by_label.get(label),
            values_left.get(label, '—'),
            values_right.get(label, '—'),
        )
        for label in order
    ]


def _render_attributes_table(
    items_left: list[tuple[str, str, str | None]] | None,
    items_right: list[tuple[str, str, str | None]] | None,
) -> None:
    """Render the remaining identity/reference attributes (everything besides
    the fragility model id, which the taxonomy picker rows above already
    convey) as one row per attribute — bold attribute name on the left, the
    baseline and comparison values next to each other on the right — instead
    of a literal table widget. Both columns always render (even if a side
    hasn't been selected yet, as '—') since the picker rows above already
    establish the baseline/comparison layout; the comparison column is
    separated from the baseline column by a vertical divider (via a keyed
    container styled globally in styles.py)."""
    for i, (label, help_text, value_left, value_right) in enumerate(
        _attribute_rows(items_left, items_right)
    ):
        row = st.columns(_ATTR_WIDTHS)
        row[0].markdown(f'**{label}**', help=help_text)
        row[1].markdown(value_left)
        with row[2].container(key=f'cmp-attr-right-{i}'):
            st.markdown(value_right)


def _damage_state_table(
    curves_left: pd.DataFrame | None,
    curves_right: pd.DataFrame | None,
    label_left: str,
    label_right: str,
) -> pd.DataFrame:
    """Build a damage-state comparison with one baseline/comparison column
    pair per damage-state rank, and one row per attribute (DS Description,
    Median, Beta, Probability) — so a description that differs between the
    two models shows both instead of only one being kept. Ranks/attributes
    with nothing on either side are omitted."""
    cols = ['DS Rank', *_DS_ATTRS]

    def indexed(curves: pd.DataFrame | None) -> pd.DataFrame:
        if curves is None or curves.empty:
            return pd.DataFrame(columns=_DS_ATTRS)
        df = curves[cols].copy()
        df['DS Rank'] = df['DS Rank'].astype(int)
        return df.set_index('DS Rank')

    left = indexed(curves_left)
    right = indexed(curves_right)
    ranks = sorted(set(left.index) | set(right.index))
    if not ranks:
        return pd.DataFrame()

    left = left.reindex(ranks)
    right = right.reindex(ranks)

    columns = []
    rows = []
    for rank in ranks:
        for side_df, side_label in ((left, label_left), (right, label_right)):
            columns.append((f'DS {rank}', side_label))
            rows.append(side_df.loc[rank])

    table = pd.DataFrame(rows).T
    table.columns = pd.MultiIndex.from_tuples(columns)
    table = table.reindex(_DS_ATTRS)

    keep_cols = [c for c in table.columns if not table[c].map(_is_blank).all()]
    table = table[keep_cols]
    keep_rows = [r for r in table.index if not table.loc[r].map(_is_blank).all()]
    return table.loc[keep_rows]


def _format_ds_value(attr_label: str, value, edp_unit: str = '—') -> str:
    if _is_blank(value):
        return '—'
    if attr_label == 'Median':
        # Medians are expressed in their own model's EDP unit, which can
        # differ between the two sides, so each column is formatted with its
        # own side's unit rather than a single shared format.
        scale, printf_format = median_display(edp_unit)
        return printf_format % (value * scale)
    fmt_str = _DS_ATTR_FORMATS.get(attr_label)
    return fmt_str.format(value) if fmt_str else str(value)


def _render_damage_state_table(
    curves_left: pd.DataFrame | None,
    curves_right: pd.DataFrame | None,
    label_left: str,
    label_right: str,
    unit_left: str = '—',
    unit_right: str = '—',
) -> None:
    """Render the damage-state comparison as a hand-built HTML table instead
    of ``st.dataframe``: Streamlit's dataframe widget can't wrap cell text or
    fix column widths, both of which the free-form DS Description column
    needs — a long description on one damage state would otherwise force
    that column wide and leave the others cramped. A ``<colgroup>`` with a
    fixed label-column width and unset value-column widths makes every
    damage-state column share the remaining space evenly under
    ``table-layout: fixed``, and ``ds-cmp-group-start`` (styles.py) adds a
    visible rule between damage states."""
    table = _damage_state_table(curves_left, curves_right, label_left, label_right)
    if table.empty:
        st.info('No damage-state data to compare.')
        return

    # Each column mixes a text row (DS Description) with numeric rows
    # (Median/Beta/Probability); pre-format every cell to its final display
    # string up front rather than relying on per-column formatting. The unit
    # a Median is shown in comes from the side that column belongs to.
    units_by_side = {label_left: unit_left, label_right: unit_right}
    display = table.copy().astype(object)
    for column in display.columns:
        edp_unit = units_by_side.get(column[1], '—')
        display[column] = [
            _format_ds_value(attr_label, table.loc[attr_label, column], edp_unit)
            for attr_label in table.index
        ]

    group_labels = list(dict.fromkeys(group for group, _ in display.columns))
    sides_by_group = {
        group: [side for g, side in display.columns if g == group]
        for group in group_labels
    }

    def cell_classes(is_group_start: bool, side: str, *base_classes: str) -> str:
        classes = [*base_classes]
        if is_group_start:
            classes.append('ds-cmp-group-start')
        if side == label_right:
            classes.append('ds-cmp-shaded')
        return f' class="{" ".join(classes)}"' if classes else ''

    group_header_cells = ['<th class="ds-cmp-attr"></th>']
    side_header_cells = ['<th class="ds-cmp-attr"></th>']
    for g, group in enumerate(group_labels):
        sides = sides_by_group[group]
        group_cls = 'ds-cmp-group' + ('' if g == 0 else ' ds-cmp-group-start')
        group_header_cells.append(
            f'<th class="{group_cls}" colspan="{len(sides)}">{esc(group)}</th>'
        )
        for i, side in enumerate(sides):
            classes = cell_classes(i == 0 and g > 0, side, 'ds-cmp-side')
            side_header_cells.append(f'<th{classes}>{esc(side)}</th>')

    body_rows = []
    for attr_label in display.index:
        cells = [f'<td class="ds-cmp-attr">{esc(attr_label)}</td>']
        for g, group in enumerate(group_labels):
            for i, side in enumerate(sides_by_group[group]):
                value = display.loc[attr_label, (group, side)]
                cell_html = (
                    clamp_cell(value)
                    if attr_label == 'DS Description'
                    else esc(value)
                )
                classes = cell_classes(i == 0 and g > 0, side)
                cells.append(f'<td{classes}>{cell_html}</td>')
        body_rows.append(f'<tr>{"".join(cells)}</tr>')

    colgroup = '<col style="width:170px">' + '<col>' * len(display.columns)
    html_table = (
        '<table class="ds-cmp-table">'
        f'<colgroup>{colgroup}</colgroup>'
        '<thead>'
        f'<tr>{"".join(group_header_cells)}</tr>'
        f'<tr>{"".join(side_header_cells)}</tr>'
        '</thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        '</table>'
    )
    st.markdown(html_table, unsafe_allow_html=True)


def render(pages: dict) -> None:
    return_to_fragility = st.session_state.get('compare_return_to_fragility')
    if return_to_fragility:
        if st.button('← Back to Fragility Model'):
            st.session_state['selected_fragility_model_id'] = return_to_fragility
            st.session_state.pop('compare_return_to_fragility', None)
            st.switch_page(
                pages['fragility_model'],
                query_params={'fragility_model': return_to_fragility},
            )

    st.markdown(
        '<div class="ned-header"><h1>Compare Fragilities</h1></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        'Select a baseline fragility model and a comparison fragility model '
        'to compare them side by side.'
    )
    st.markdown('---')

    _render_table_header()
    fragility_left, fragility_right = _render_selection_rows()

    label_left = fragility_left or 'Baseline'
    label_right = fragility_right or 'Comparison'
    if fragility_left and fragility_right and fragility_left == fragility_right:
        label_left, label_right = (
            f'{fragility_left} (baseline)',
            (f'{fragility_right} (comparison)'),
        )

    # Drop the leading 'Fragility Model ID' entry: the 'Fragility' picker row
    # above already conveys which model is selected on each side.
    attrs_left = get_model_attributes(fragility_left) if fragility_left else None
    attrs_right = get_model_attributes(fragility_right) if fragility_right else None
    items_left = attrs_left[1:] if attrs_left else None
    items_right = attrs_right[1:] if attrs_right else None
    _render_attributes_table(items_left, items_right)

    if not fragility_left and not fragility_right:
        return

    st.markdown('---')
    st.markdown('## Damage States')

    curves_left = get_fragility_curves(fragility_left) if fragility_left else None
    curves_right = get_fragility_curves(fragility_right) if fragility_right else None

    def x_title(items: list[tuple[str, str, str | None]] | None) -> str:
        if not items:
            return ''
        values = {label: value for label, value, _ in items}
        edp_metric, edp_unit = (
            values.get('EDP Metric', '—'),
            values.get('EDP Unit', '—'),
        )
        return f'{edp_metric} [{edp_unit}]' if edp_unit != '—' else edp_metric

    def edp_unit(items: list[tuple[str, str, str | None]] | None) -> str:
        if not items:
            return '—'
        return {label: value for label, value, _ in items}.get('EDP Unit', '—')

    _render_comparison_chart(
        curves_left,
        curves_right,
        x_title(items_left),
        x_title(items_right),
        label_left,
        label_right,
    )
    _render_damage_state_table(
        curves_left,
        curves_right,
        label_left,
        label_right,
        edp_unit(items_left),
        edp_unit(items_right),
    )
