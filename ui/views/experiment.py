import json

import streamlit as st

from db import (
    get_experiment_detail,
    get_experiment_fragility_models,
    get_reference,
)
from utils import FIELD_HELP, attr, build_citation, doi_url, esc, fmt, header_span


def render() -> None:
    experiment_id = st.session_state.get('selected_experiment_id', '')

    if st.button('← Back to Component'):
        st.session_state['page'] = 'Component Detail'
        if 'experiment' in st.query_params:
            del st.query_params['experiment']
        st.rerun()

    df_exp_detail = get_experiment_detail(experiment_id)

    if df_exp_detail.empty:
        st.warning(f"Experiment '{experiment_id}' not found.")
        return

    row = df_exp_detail.iloc[0]

    st.markdown(
        '<div class="ned-header"><h1>Experiment View</h1></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'**{fmt(row["Experiment ID"])}**')
    st.markdown('---')

    attr('Specimen', fmt(row['Specimen']))
    attr(
        'Inspection Sequence',
        fmt(row['Inspection Sequence']),
        help_text=FIELD_HELP['specimen_inspection_sequence'],
    )
    attr('Reviewer', fmt(row['Reviewer']))
    attr('Test Type', fmt(row['Test Type']))
    attr(
        'Loading Protocol',
        fmt(row['Loading Protocol']),
        help_text=FIELD_HELP['loading_protocol'],
    )
    attr('Peak Test Amplitude', fmt(row['Peak Test Amplitude']))
    attr('Location', fmt(row['Location']))
    attr(
        'Governing Design Standard',
        fmt(row['Governing Design Standard']),
        help_text=FIELD_HELP['governing_design_standard'],
    )
    attr(
        'Design Objective',
        fmt(row['Design Objective']),
        help_text=FIELD_HELP['design_objective'],
    )
    attr(
        'Component Detail',
        fmt(row['Component Detail']),
        help_text=FIELD_HELP['comp_detail'],
    )
    attr('Material', fmt(row['Material']), help_text=FIELD_HELP['material'])
    attr('Size Class', fmt(row['Size Class']), help_text=FIELD_HELP['size_class'])
    attr('Component Description', fmt(row['Component Description']))
    attr('Damage Description', fmt(row['Damage Description']))
    attr('DS Rank', fmt(row['DS Rank']), help_text=FIELD_HELP['ds_rank'])
    attr('DS Class', fmt(row['DS Class']), help_text=FIELD_HELP['ds_class'])
    attr('EDP Metric', fmt(row['EDP Metric']))
    attr('EDP Unit', fmt(row['EDP Unit']))
    attr('EDP Value', fmt(row['EDP Value']))
    attr('Alt EDP Metric', fmt(row['Alt EDP Metric']))
    attr('Alt EDP Unit', fmt(row['Alt EDP Unit']))
    attr('Alt EDP Value', fmt(row['Alt EDP Value']))
    attr(
        'Prior Damage',
        fmt(row['Prior Damage']),
        help_text=FIELD_HELP['prior_damage'],
    )
    attr(
        'Prior Damage Repaired',
        fmt(row['Prior Damage Repaired']),
        help_text=FIELD_HELP['prior_damage_repaired'],
    )
    attr('Notes', fmt(row['Notes']))

    st.markdown('<br>', unsafe_allow_html=True)

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

    # ── Fragility models informed by this experiment ──
    # The reverse of the fragility model's "Source Data" section: a fragility
    # model cites the experiments beneath it, and here we surface which models
    # (if any) an experiment informed.
    st.markdown('---')
    st.markdown('## Fragility models informed by this experiment')
    df_fm = get_experiment_fragility_models(experiment_id)

    if df_fm.empty:
        st.info('No fragility models currently cite this experiment.')
    else:
        component_id = st.session_state.get('selected_component_id', '')
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
                header_span(label, _FM_HEADER_HELP.get(label)),
                unsafe_allow_html=True,
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
                if component_id:
                    st.query_params['component'] = component_id
                if 'experiment' in st.query_params:
                    del st.query_params['experiment']
                st.rerun()
