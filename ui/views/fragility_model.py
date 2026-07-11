import json
import math
import textwrap

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import (
    get_fragility_curves,
    get_fragility_model_detail,
    get_fragility_model_experiments,
    get_fragility_model_experiments_export,
    get_reference,
)
from utils import FIELD_HELP, attr, build_citation, csv_safe, fmt
from views.experiments_table import render_experiments_table, with_reference


def _lognormal_curves(
    df_curves: pd.DataFrame, n_points: int = 200
) -> pd.DataFrame | None:
    """Build long-format plot data from median/beta pairs. Returns None if no
    damage state has a usable (positive) median and beta."""
    valid = df_curves.dropna(subset=['Median', 'Beta']).copy()
    valid = valid[(valid['Median'] > 0) & (valid['Beta'] > 0)]
    if valid.empty:
        return None

    lo = float((valid['Median'] * np.exp(-3.5 * valid['Beta'])).min())
    hi = float((valid['Median'] * np.exp(2.5 * valid['Beta'])).max())
    edps = np.linspace(lo, hi, n_points)
    erf_v = np.vectorize(math.erf)

    frames = []
    for _, r in valid.iterrows():
        median, beta = float(r['Median']), float(r['Beta'])
        z = np.log(edps / median) / beta
        probs = 0.5 * (1.0 + erf_v(z / math.sqrt(2)))
        ds_rank = int(r['DS Rank']) if pd.notna(r['DS Rank']) else 0
        desc = str(r.get('DS Description') or '').strip()
        if desc:
            head = f'DS {ds_rank}: '
            wrapped = textwrap.wrap(
                head + desc,
                width=38,
                subsequent_indent=' ' * len(head),
                break_long_words=False,
            )
            label = '<br>'.join(wrapped) if wrapped else head + desc
        else:
            label = f'DS {ds_rank}'
        frames.append(
            pd.DataFrame({
                'EDP': edps,
                'Probability': probs,
                'Damage State': label,
                '_rank': ds_rank,
            })
        )
    return pd.concat(frames, ignore_index=True)


def render_model_body(
    fragility_model_id: str, key_prefix: str = '', show_download: bool = True
) -> None:
    """Render the full fragility-model detail (attributes, reference, damage-state
    chart, and curve table) for the given model. ``key_prefix`` makes the widget
    keys unique so this can be rendered more than once on a page (e.g. the
    side-by-side compare view). Set ``show_download`` to ``False`` to omit the
    curve CSV download button."""
    df_fm_detail = get_fragility_model_detail(fragility_model_id)

    if df_fm_detail.empty:
        st.warning(f"Fragility model '{fragility_model_id}' not found.")
        return

    row = df_fm_detail.iloc[0]

    st.markdown(f'**{fmt(row["fragility_model_id"])}**')
    st.markdown('---')

    attr('Model ID', fmt(row['model_id']))
    attr('P-58 Fragility', fmt(row['p58_fragility']))
    attr(
        'Component Detail',
        fmt(row['comp_detail']),
        help_text=FIELD_HELP['comp_detail'],
    )
    attr('Material', fmt(row['material']), help_text=FIELD_HELP['material'])
    attr('Size Class', fmt(row['size_class']), help_text=FIELD_HELP['size_class'])
    attr('Component Description', fmt(row['comp_description']))
    attr('EDP Metric', fmt(row['edp_metric']))
    attr('EDP Unit', fmt(row['edp_unit']))
    attr('Reviewer', fmt(row['reviewer']))
    attr('Source', fmt(row['source']))

    reference_id = row['reference_id']
    df_ref = get_reference(fmt(reference_id)) if reference_id else None
    if df_ref is not None and not df_ref.empty:
        ref = df_ref.iloc[0]

        try:
            csl = json.loads(ref['csl_data']) if ref['csl_data'] else {}
        except (ValueError, TypeError):
            csl = {}

        citation = build_citation(csl)
        if not citation:
            citation = (
                f'{fmt(ref["author"])} ({fmt(ref["year"])}). {fmt(ref["title"])}.'
            )
        attr('Reference', citation)
        attr('Study Type', fmt(ref['study_type']))

    st.markdown('---')

    st.markdown('## Damage States')
    df_curves = get_fragility_curves(fragility_model_id)

    if df_curves.empty:
        st.info('No fragility curves are associated with this model.')
    else:
        plot_df = _lognormal_curves(df_curves)
        if plot_df is not None:
            edp_metric = fmt(row['edp_metric'])
            edp_unit = fmt(row['edp_unit'])
            x_title = f'{edp_metric} [{edp_unit}]' if edp_unit != '—' else edp_metric

            fig = go.Figure()
            # Sort by EDP as well: rows within a damage state share the same
            # _rank, and an unstable sort on ties scrambles the point order,
            # making the CDF trace double back on itself.
            for ds_label, group in plot_df.sort_values(['_rank', 'EDP']).groupby(
                'Damage State', sort=False
            ):
                fig.add_trace(
                    go.Scatter(
                        x=group['EDP'],
                        y=group['Probability'],
                        mode='lines',
                        name=ds_label,
                        hovertemplate=(
                            f'{x_title}: %{{x:.3f}}<br>'
                            'Probability: %{y:.2f}<extra></extra>'
                        ),
                    )
                )

            fig.update_layout(
                height=360,
                autosize=True,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(
                    title=x_title,
                    showgrid=False,
                ),
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
            st.plotly_chart(
                fig, use_container_width=True, key=f'{key_prefix}curves_chart'
            )
        else:
            st.info(
                'No fragility curves with usable median/beta values for this model.'
            )

        st.dataframe(
            df_curves,
            use_container_width=True,
            hide_index=True,
            column_config={
                'DS Rank': st.column_config.NumberColumn('DS Rank', format='%d'),
                'DS Description': st.column_config.TextColumn('DS Description'),
                'Basis': st.column_config.TextColumn('Basis'),
                '# Observations': st.column_config.NumberColumn(
                    '# Observations', format='%d'
                ),
                'Median': st.column_config.NumberColumn('Median', format='%.4f'),
                'Beta': st.column_config.NumberColumn('Beta', format='%.3f'),
                'Probability': st.column_config.NumberColumn(
                    'Probability', format='%.2f'
                ),
            },
        )
        if show_download:
            st.download_button(
                'Download CSV',
                csv_safe(df_curves).to_csv(index=False),
                file_name=f'{fragility_model_id}_curves.csv',
                mime='text/csv',
                key=f'{key_prefix}curves_csv',
            )


def render() -> None:
    fragility_model_id = st.session_state.get('selected_fragility_model_id', '')

    if st.button('← Back to Component'):
        st.session_state['page'] = 'Component Detail'
        if 'fragility_model' in st.query_params:
            del st.query_params['fragility_model']
        st.rerun()

    st.markdown(
        '<div class="ned-header"><h1>Fragility Model View</h1></div>',
        unsafe_allow_html=True,
    )
    render_model_body(fragility_model_id)

    # ── Source Data ──
    st.markdown('---')
    st.markdown('## Source Data')
    df_exp = get_fragility_model_experiments(fragility_model_id)

    if df_exp.empty:
        st.info('No experiments are have been linked with this fragility model.')
    else:
        render_experiments_table(
            df_exp,
            with_reference(get_fragility_model_experiments_export(fragility_model_id)),
            file_name=f'{fragility_model_id}_experiments.csv',
            key_prefix='src_',
        )
