import streamlit as st

from db import get_components, get_groups, get_major_groups
from utils import esc, fmt


def render() -> None:
    st.markdown(
        '<div class="ned-header"><h1>Components</h1></div>',
        unsafe_allow_html=True,
    )

    df_all = get_components()
    total_components = len(df_all)

    st.markdown("---")

    major_groups = ["All groups"] + get_major_groups()
    selected_group = st.selectbox("NISTIR Major Group", major_groups)

    groups = ["All groups"] + get_groups(selected_group)
    selected_subgroup = st.selectbox("NISTIR Group", groups)

    search = st.text_input(
        "Search",
        placeholder="Search by name, ID, or element…",
        label_visibility="collapsed",
    )

    df_display = df_all.copy()

    if selected_group != "All groups":
        df_display = df_display[df_display["major_group"] == selected_group]

    if selected_subgroup != "All groups":
        df_display = df_display[df_display["Group"] == selected_subgroup]

    if search:
        mask = (
            df_display["ID"].str.contains(search, case=False, na=False, regex=False)
            | df_display["Name"].str.contains(search, case=False, na=False, regex=False)
            | df_display["Element"].str.contains(search, case=False, na=False, regex=False)
        )
        df_display = df_display[mask]

    df_display = df_display.drop(columns=["major_group", "Group"]).reset_index(drop=True)

    if df_display.empty:
        st.info("No components match the current filters.")
    else:
        _WIDTHS = [1.2, 2.5, 5, 1, 1.5, 1]

        h = st.columns(_WIDTHS)
        for col, label in zip(h, ["ID", "Element", "Name", "# Tests", "# Fragility Models", ""]):
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
            c[0].markdown(f"<span style='font-size:0.88rem;'>{esc(row['ID'])}</span>", unsafe_allow_html=True)
            c[1].markdown(f"<span style='font-size:0.88rem;'>{esc(row['Element'])}</span>", unsafe_allow_html=True)
            c[2].markdown(f"<span style='font-size:0.88rem;'>{esc(row['Name'])}</span>", unsafe_allow_html=True)
            c[3].markdown(f"<span style='font-size:0.88rem;'>{int(row['# Tests'])}</span>", unsafe_allow_html=True)
            c[4].markdown(f"<span style='font-size:0.88rem;'>{int(row['# Fragility Models'])}</span>", unsafe_allow_html=True)
            if c[5].button("View", key=f"comp_{row['ID']}"):
                st.session_state["selected_component_id"] = row["ID"]
                st.session_state["page"] = "Component Detail"
                st.query_params["component"] = row["ID"]
                st.rerun()

        st.caption(f"Showing {len(df_display)} of {total_components} components")
