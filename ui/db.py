import os
import sqlite3

import pandas as pd
import streamlit as st

_DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'backend', 'db.sqlite3'
)
_DB_PATH = os.environ.get('DB_PATH', _DEFAULT_DB)

_COMPONENTS_QUERY = """
SELECT
    c.id                                    AS "ID",
    c.major_group                           AS major_group,
    c."group"                               AS "Group",
    c.element                               AS "Element",
    c.name                                  AS "Name",
    COUNT(DISTINCT e.id)                    AS "# Tests",
    COUNT(DISTINCT b.fragility_model_id)    AS "# Fragility Models"
FROM ned_app_component c
LEFT JOIN ned_app_experiment e
       ON e.component_id = c.component_id
LEFT JOIN ned_app_componentfragilitymodelbridge b
       ON b.component_id = c.component_id
GROUP BY c.id, c.major_group, c."group", c.element, c.name
ORDER BY c.id
"""


@st.cache_data
def get_components() -> pd.DataFrame:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        df = pd.read_sql(_COMPONENTS_QUERY, conn)
    finally:
        conn.close()

    df['Element'] = df['Element'].str.split(' - ', n=1).str[-1].fillna('—')
    df['major_group'] = df['major_group'].fillna('—')

    major_letter = df['major_group'].str.split(' - ', n=1).str[0]
    group_split = df['Group'].str.split(' - ', n=1)
    df['Group'] = (
        major_letter + group_split.str[0] + ' - ' + group_split.str[1]
    ).fillna('—')

    return df


def get_major_groups() -> list[str]:
    df = get_components()
    return sorted(df['major_group'].dropna().unique().tolist())


def get_groups(major_group_filter: str | None = None) -> list[str]:
    df = get_components()
    if major_group_filter and major_group_filter != 'All groups':
        df = df[df['major_group'] == major_group_filter]
    groups = df['Group'].replace('—', pd.NA).dropna().unique().tolist()
    return sorted(groups)


@st.cache_data
def get_component_detail(component_id: str) -> pd.DataFrame:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            'SELECT id, name, component_id, major_group, "group", element, subelement '
            'FROM ned_app_component WHERE id = ?',
            conn,
            params=(component_id,),
        )
    finally:
        conn.close()


@st.cache_data
def get_component_fragility_models(component_id: str) -> pd.DataFrame:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            """
            SELECT
                fm.fragility_model_id,
                fm.model_id             AS "Model ID",
                fm.p58_fragility        AS "P-58 Fragility",
                fm.comp_detail          AS "Component Detail",
                fm.material             AS "Material",
                fm.size_class           AS "Size Class",
                fm.comp_description     AS "Component Description"
            FROM ned_app_componentfragilitymodelbridge b
            JOIN ned_app_fragilitymodel fm ON fm.fragility_model_id = b.fragility_model_id
            JOIN ned_app_component c ON c.component_id = b.component_id
            WHERE c.id = ?
            ORDER BY fm.fragility_model_id
            """,
            conn,
            params=(component_id,),
        )
    finally:
        conn.close()


@st.cache_data
def get_component_fragility_models_export(component_id: str) -> pd.DataFrame:
    """All fragility models for a component with the full set of fields shown
    on the Fragility Model view page — one row per fragility curve (damage
    state), with model attributes repeated. Includes the reference columns
    needed to build the citation ('author', 'year', 'title', 'csl_data')."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            """
            SELECT
                fm.fragility_model_id   AS "Fragility Model ID",
                fm.model_id             AS "Model ID",
                fm.p58_fragility        AS "P-58 Fragility",
                fm.comp_detail          AS "Component Detail",
                fm.material             AS "Material",
                fm.size_class           AS "Size Class",
                fm.comp_description     AS "Component Description",
                fm.edp_metric           AS "EDP Metric",
                fm.edp_unit             AS "EDP Unit",
                fm.reviewer             AS "Reviewer",
                fm.source               AS "Source",
                r.author                AS "author",
                r.year                  AS "year",
                r.title                 AS "title",
                r.csl_data              AS "csl_data",
                r.study_type            AS "Study Type",
                fc.ds_rank              AS "DS Rank",
                fc.ds_description       AS "DS Description",
                fc.basis                AS "Basis",
                fc.num_observations     AS "# Observations",
                fc.median               AS "Median",
                fc.beta                 AS "Beta",
                fc.probability          AS "Probability"
            FROM ned_app_componentfragilitymodelbridge b
            JOIN ned_app_fragilitymodel fm ON fm.fragility_model_id = b.fragility_model_id
            JOIN ned_app_component c ON c.component_id = b.component_id
            LEFT JOIN ned_app_reference r ON r.reference_id = fm.reference_id
            LEFT JOIN ned_app_fragilitycurve fc ON fc.fragility_model_id = fm.fragility_model_id
            WHERE c.id = ?
            ORDER BY fm.fragility_model_id, fc.ds_rank
            """,
            conn,
            params=(component_id,),
        )
    finally:
        conn.close()


@st.cache_data
def get_fragility_models() -> pd.DataFrame:
    """All fragility models paired with the (human-readable) component id they
    belong to, so the list can be filtered by component/taxonomy/search."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            """
            SELECT
                fm.fragility_model_id   AS fragility_model_id,
                fm.comp_detail          AS comp_detail,
                fm.material             AS material,
                c.id                    AS comp_id
            FROM ned_app_componentfragilitymodelbridge b
            JOIN ned_app_fragilitymodel fm ON fm.fragility_model_id = b.fragility_model_id
            JOIN ned_app_component c ON c.component_id = b.component_id
            ORDER BY fm.fragility_model_id
            """,
            conn,
        )
    finally:
        conn.close()


@st.cache_data
def get_reference(reference_id: str) -> pd.DataFrame:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            'SELECT reference_id, title, author, year, study_type, comp_type, csl_data '
            'FROM ned_app_reference WHERE reference_id = ?',
            conn,
            params=(reference_id,),
        )
    finally:
        conn.close()


@st.cache_data
def get_fragility_model_detail(fragility_model_id: str) -> pd.DataFrame:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            'SELECT fragility_model_id, model_id, reference_id, p58_fragility, '
            'comp_detail, material, size_class, comp_description, '
            'edp_metric, edp_unit, reviewer, source '
            'FROM ned_app_fragilitymodel WHERE fragility_model_id = ?',
            conn,
            params=(fragility_model_id,),
        )
    finally:
        conn.close()


@st.cache_data
def get_fragility_curves(fragility_model_id: str) -> pd.DataFrame:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            """
            SELECT
                ds_rank             AS "DS Rank",
                ds_description      AS "DS Description",
                basis               AS "Basis",
                num_observations    AS "# Observations",
                median              AS "Median",
                beta                AS "Beta",
                probability         AS "Probability"
            FROM ned_app_fragilitycurve
            WHERE fragility_model_id = ?
            ORDER BY ds_rank
            """,
            conn,
            params=(fragility_model_id,),
        )
    finally:
        conn.close()


@st.cache_data
def get_component_experiments(component_id: str) -> pd.DataFrame:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            """
            SELECT
                e.id                    AS "experiment_id",
                r.author || ', ' || r.year AS "Source",
                json_extract(r.csl_data, '$.DOI') AS "doi",
                e.test_type             AS "Test Type",
                e.location              AS "Location",
                e.design_objective      AS "Design Objective",
                e.comp_description      AS "Component Description",
                e.ds_description        AS "Damage Description",
                e.edp_metric            AS "EDP Metric",
                e.edp_unit              AS "EDP Unit",
                e.edp_value             AS "EDP Value",
                e.ds_rank               AS "DS Rank",
                e.ds_class              AS "DS Class",
                e.reference_id          AS "Reference ID",
                c.subelement            AS "NISTIR Subelement"
            FROM ned_app_experiment e
            JOIN ned_app_component c ON c.component_id = e.component_id
            JOIN ned_app_reference r ON r.reference_id = e.reference_id
            WHERE c.id = ?
            ORDER BY e.reference_id, e.specimen, e.ds_rank
            """,
            conn,
            params=(component_id,),
        )
    finally:
        conn.close()


@st.cache_data
def get_component_experiments_export(component_id: str) -> pd.DataFrame:
    """All experiments for a component with the full set of fields shown on
    the Experiment view page, plus the reference columns needed to build the
    citation ('author', 'year', 'title', 'csl_data')."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            """
            SELECT
                e.id                        AS "Experiment ID",
                e.specimen                  AS "Specimen",
                e.specimen_inspection_sequence AS "Inspection Sequence",
                e.reviewer                  AS "Reviewer",
                e.test_type                 AS "Test Type",
                e.loading_protocol          AS "Loading Protocol",
                e.peak_test_amplitude       AS "Peak Test Amplitude",
                e.location                  AS "Location",
                e.governing_design_standard AS "Governing Design Standard",
                e.design_objective          AS "Design Objective",
                e.comp_detail               AS "Component Detail",
                e.material                  AS "Material",
                e.size_class                AS "Size Class",
                e.comp_description          AS "Component Description",
                e.ds_description            AS "Damage Description",
                e.ds_rank                   AS "DS Rank",
                e.ds_class                  AS "DS Class",
                e.edp_metric                AS "EDP Metric",
                e.edp_unit                  AS "EDP Unit",
                e.edp_value                 AS "EDP Value",
                e.alt_edp_metric            AS "Alt EDP Metric",
                e.alt_edp_unit              AS "Alt EDP Unit",
                e.alt_edp_value             AS "Alt EDP Value",
                e.prior_damage              AS "Prior Damage",
                e.prior_damage_repaired     AS "Prior Damage Repaired",
                e.notes                     AS "Notes",
                r.author                    AS "author",
                r.year                      AS "year",
                r.title                     AS "title",
                r.csl_data                  AS "csl_data",
                r.study_type                AS "Study Type"
            FROM ned_app_experiment e
            JOIN ned_app_component c ON c.component_id = e.component_id
            JOIN ned_app_reference r ON r.reference_id = e.reference_id
            WHERE c.id = ?
            ORDER BY e.reference_id, e.specimen, e.ds_rank
            """,
            conn,
            params=(component_id,),
        )
    finally:
        conn.close()


@st.cache_data
def get_experiment_detail(experiment_id: str) -> pd.DataFrame:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        return pd.read_sql(
            """
            SELECT
                e.id                        AS "Experiment ID",
                e.specimen                  AS "Specimen",
                e.specimen_inspection_sequence AS "Inspection Sequence",
                e.reviewer                  AS "Reviewer",
                e.test_type                 AS "Test Type",
                e.loading_protocol          AS "Loading Protocol",
                e.peak_test_amplitude       AS "Peak Test Amplitude",
                e.location                  AS "Location",
                e.governing_design_standard AS "Governing Design Standard",
                e.design_objective          AS "Design Objective",
                e.comp_detail               AS "Component Detail",
                e.material                  AS "Material",
                e.size_class                AS "Size Class",
                e.comp_description          AS "Component Description",
                e.ds_description            AS "Damage Description",
                e.ds_rank                   AS "DS Rank",
                e.ds_class                  AS "DS Class",
                e.edp_metric                AS "EDP Metric",
                e.edp_unit                  AS "EDP Unit",
                e.edp_value                 AS "EDP Value",
                e.alt_edp_metric            AS "Alt EDP Metric",
                e.alt_edp_unit              AS "Alt EDP Unit",
                e.alt_edp_value             AS "Alt EDP Value",
                e.prior_damage              AS "Prior Damage",
                e.prior_damage_repaired     AS "Prior Damage Repaired",
                e.notes                     AS "Notes",
                e.reference_id              AS "reference_id"
            FROM ned_app_experiment e
            WHERE e.id = ?
            """,
            conn,
            params=(experiment_id,),
        )
    finally:
        conn.close()
