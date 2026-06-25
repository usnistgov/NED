import streamlit as st

from db import get_components


def render() -> None:
    df_home = get_components()

    st.markdown('---')

    st.markdown('## What is NED?')
    st.markdown(
        """
        The **Nonstructural Element Database (NED)** is a curated relational database collecting experimental,
        analytical, and historic performance data on nonstructural building elements. It is designed to support
        the development and validation of **seismic fragility and consequence models** for use in loss
        estimation frameworks such as FEMA P-58.

        NED expands significantly upon the FEMA P-58 nonstructural database, providing a structured,
        traceable, and openly accessible resource for the earthquake engineering research community.
        """
    )

    m1, m2, _ = st.columns([1, 1, 4])
    m1.metric('Experiments', f'{int(df_home["# Tests"].sum()):,}')
    m2.metric('Fragility Models', f'{int(df_home["# Fragility Models"].sum()):,}')

    st.markdown('---')

    st.markdown('## Key Features')
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            **Comprehensive Data Coverage**
            Over 2,000 experimental data points spanning mechanical, electrical, plumbing,
            architectural finishes, furnishings, and specialty components — all linked to
            primary source references.

            **Structured Taxonomy**
            Components are classified using the **UNIFORMAT II** hierarchy (Major Group →
            Group → Element) augmented with NISTIR subcategory attributes: connection
            detail, material, size class, and additional descriptors as needed.
            """
        )

    with col2:
        st.markdown(
            """
            **Traceable to Source**
            Every data point is linked to a citable reference, and fragility models are linked to underlying source data, 
            supporting reproducibility, transparency, dynamic data reuse, and scalability.

            **Open & Actively Maintained**
            Hosted publicly on GitHub, with a defined contribution
            workflow for researchers wishing to add data or propose schema changes.
            """
        )

    st.markdown('---')

    st.markdown('## Database Architecture')
    st.markdown(
        """
        NED is a relational SQLite database with five core tables and two bridge tables
        that link experimental observations and fragility models back to the components they characterize.
        """
    )

    st.graphviz_chart(
        """
        digraph ERD {
            graph [rankdir=LR, fontname="Helvetica", fontsize=11, splines=curved, nodesep=0.8, ranksep=1.4, bgcolor="transparent"]
            node  [shape=box, fontname="Helvetica", fontsize=11, style=filled, fillcolor="#f5f7fa", color="#aab4c4", margin="0.3,0.15"]
            edge  [color="#6b7a8d", arrowsize=0.7]

            Component
            Reference
            Experiment
            FragilityModel
            FragilityCurve

            Component      -> Experiment      [style=solid]
            Reference      -> Experiment      [style=solid]
            Reference      -> FragilityModel  [style=solid]
            FragilityModel -> FragilityCurve  [style=solid]
            Component      -> FragilityModel  [style=dashed dir=both]
            Experiment     -> FragilityModel  [style=dashed dir=both]
        }
        """,
        use_container_width=True,
    )
    st.caption('— solid arrow: one-to-many    · · · dashed arrow: many-to-many')

    st.markdown(
        """
        | Table | Description |
        |---|---|
        | **Component** | The central reference table. Each row is a unique nonstructural component subtype, classified by the four-level NISTIR hierarchy: Major Group → Group → Element → Subelement. |
        | **Reference** | Research publications from which data are drawn — experimental studies, reconnaissance reports, analytical studies, and literature reviews. Stores full citation metadata in CSL-JSON format. |
        | **Experiment** | Individual experimental test observations. Each record captures the specimen, test type, loading protocol, EDP (metric, unit, and value), and damage state classification. Subcategory attributes (`comp_detail`, `material`, `size_class`) allow a single component type to be subdivided without a new component record. Linked to one Component and one Reference. |
        | **FragilityModel** | A fragility model for a specific component configuration. Stores the EDP metric and unit that the curves are expressed in, along with subcategory attributes, data source provenance (`reviewer`, `source`), and an optional FEMA P-58 cross-reference. Linked to one Reference. |
        | **FragilityCurve** | Individual lognormal fragility curves within a FragilityModel. Each curve stores damage state rank, description, basis, number of observations, median, beta (lognormal dispersion), and mutually exclusive probability. |
        """
    )

    st.markdown(
        """
        **Bridge tables** handle the many-to-many relationships: a fragility model may be supported
        by multiple experiments (`ExperimentFragilityModelBridge`), and a component may be associated
        with multiple fragility models (`ComponentFragilityModelBridge`).
        """
    )

    st.markdown('---')

    st.markdown('## Using This App')
    st.markdown(
        """
        Use the **sidebar** to navigate between pages:

        - **Home** — this page; project overview and documentation.
        - **Components** — browse, filter, and search all component types in the database.
        """
    )

    st.markdown('---')

    st.markdown('## Learn More')
    st.markdown(
        """
        The full backend codebase — including the database schema, ingestion pipeline,
        contribution guide, and Jupyter notebook visualization tools — is publicly available
        on GitHub:

        **[usnistgov/NED on GitHub](https://github.com/usnistgov/NED)**
        """
    )
