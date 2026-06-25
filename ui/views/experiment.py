import json

import streamlit as st

from db import get_experiment_detail, get_reference
from utils import attr, build_citation, fmt


def render() -> None:
    experiment_id = st.session_state.get("selected_experiment_id", "")

    if st.button("← Back to Component"):
        st.session_state["page"] = "Component Detail"
        if "experiment" in st.query_params:
            del st.query_params["experiment"]
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
    st.markdown(f"**{fmt(row['Experiment ID'])}**")
    st.markdown("---")

    attr("Specimen",                  fmt(row["Specimen"]))
    attr("Inspection Sequence",       fmt(row["Inspection Sequence"]))
    attr("Reviewer",                  fmt(row["Reviewer"]))
    attr("Test Type",                 fmt(row["Test Type"]))
    attr("Loading Protocol",          fmt(row["Loading Protocol"]))
    attr("Peak Test Amplitude",       fmt(row["Peak Test Amplitude"]))
    attr("Location",                  fmt(row["Location"]))
    attr("Governing Design Standard", fmt(row["Governing Design Standard"]))
    attr("Design Objective",          fmt(row["Design Objective"]))
    attr("Component Detail",          fmt(row["Component Detail"]))
    attr("Material",                  fmt(row["Material"]))
    attr("Size Class",                fmt(row["Size Class"]))
    attr("Component Description",     fmt(row["Component Description"]))
    attr("Damage Description",        fmt(row["Damage Description"]))
    attr("DS Rank",                   fmt(row["DS Rank"]))
    attr("DS Class",                  fmt(row["DS Class"]))
    attr("EDP Metric",                fmt(row["EDP Metric"]))
    attr("EDP Unit",                  fmt(row["EDP Unit"]))
    attr("EDP Value",                 fmt(row["EDP Value"]))
    attr("Alt EDP Metric",            fmt(row["Alt EDP Metric"]))
    attr("Alt EDP Unit",              fmt(row["Alt EDP Unit"]))
    attr("Alt EDP Value",             fmt(row["Alt EDP Value"]))
    attr("Prior Damage",              fmt(row["Prior Damage"]))
    attr("Prior Damage Repaired",     fmt(row["Prior Damage Repaired"]))
    attr("Notes",                     fmt(row["Notes"]))

    st.markdown("<br>", unsafe_allow_html=True)

    reference_id = row["reference_id"]
    df_ref = get_reference(fmt(reference_id)) if reference_id else None
    if df_ref is not None and not df_ref.empty:
        ref = df_ref.iloc[0]

        try:
            csl = json.loads(ref["csl_data"]) if ref["csl_data"] else {}
        except (ValueError, TypeError):
            csl = {}

        citation = build_citation(csl)
        if not citation:
            citation = f"{fmt(ref['author'])} ({fmt(ref['year'])}). {fmt(ref['title'])}."
        attr("Reference",  citation)
        attr("Study Type", fmt(ref["study_type"]))
