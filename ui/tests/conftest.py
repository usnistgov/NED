import json
import sqlite3
import sys
from pathlib import Path

import pytest
import streamlit as st

# ui/ modules import each other with flat names (`from db import ...`,
# `import auth`), so ui/ itself — not ui/tests — needs to be on sys.path for
# those imports to resolve, same as when `streamlit run app.py` is launched
# from inside ui/.
_UI_DIR = Path(__file__).resolve().parent.parent
if str(_UI_DIR) not in sys.path:
    sys.path.insert(0, str(_UI_DIR))


# Minimal re-statement of the tables in ned_app/models.py that ui/db.py
# queries. Column names (including Django's default `<field>_id` naming for
# foreign keys) must match the real schema; kept here by hand rather than
# built from `manage.py migrate` so ui/tests stay independent of the Django
# app and its settings module.
_SCHEMA = """
CREATE TABLE ned_app_component (
    id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    component_id VARCHAR(20) UNIQUE,
    major_group VARCHAR(255),
    "group" VARCHAR(255),
    element VARCHAR(255),
    subelement VARCHAR(255)
);

CREATE TABLE ned_app_reference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_id VARCHAR(255) UNIQUE NOT NULL,
    reference_label VARCHAR(100),
    title VARCHAR(255) NOT NULL,
    author VARCHAR(255) NOT NULL,
    year INTEGER NOT NULL,
    study_type VARCHAR(50) NOT NULL,
    comp_type VARCHAR(255),
    pdf_saved BOOLEAN,
    csl_data TEXT NOT NULL
);

CREATE TABLE ned_app_experiment (
    id VARCHAR(255) PRIMARY KEY,
    reference_id VARCHAR(255) NOT NULL REFERENCES ned_app_reference(reference_id),
    component_id VARCHAR(20) NOT NULL REFERENCES ned_app_component(component_id),
    specimen VARCHAR(255),
    specimen_inspection_sequence VARCHAR(255),
    reviewer VARCHAR(50),
    comp_detail VARCHAR(100),
    material VARCHAR(100),
    size_class VARCHAR(100),
    test_type VARCHAR(50),
    loading_protocol TEXT,
    peak_test_amplitude VARCHAR(255),
    location VARCHAR(255),
    governing_design_standard VARCHAR(255),
    design_objective TEXT,
    comp_description TEXT NOT NULL,
    ds_description TEXT NOT NULL,
    prior_damage TEXT,
    prior_damage_repaired TEXT,
    edp_metric VARCHAR(50),
    edp_unit VARCHAR(50),
    edp_value DECIMAL,
    alt_edp_metric VARCHAR(50),
    alt_edp_unit VARCHAR(50),
    alt_edp_value DECIMAL,
    ds_rank INTEGER,
    ds_class VARCHAR(50),
    notes TEXT
);

CREATE TABLE ned_app_fragilitymodel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fragility_model_id VARCHAR(255) UNIQUE NOT NULL,
    reference_id VARCHAR(255) NOT NULL REFERENCES ned_app_reference(reference_id),
    model_id VARCHAR(255) NOT NULL,
    p58_fragility VARCHAR(50),
    comp_detail VARCHAR(100),
    material VARCHAR(100),
    size_class VARCHAR(100),
    comp_description TEXT NOT NULL,
    reviewer VARCHAR(255),
    source VARCHAR(255),
    edp_metric VARCHAR(255),
    edp_unit VARCHAR(255)
);

CREATE TABLE ned_app_experimentfragilitymodelbridge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id VARCHAR(255) NOT NULL REFERENCES ned_app_experiment(id),
    fragility_model_id VARCHAR(255) NOT NULL
        REFERENCES ned_app_fragilitymodel(fragility_model_id)
);

CREATE TABLE ned_app_componentfragilitymodelbridge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id VARCHAR(20) NOT NULL REFERENCES ned_app_component(component_id),
    fragility_model_id VARCHAR(255) NOT NULL
        REFERENCES ned_app_fragilitymodel(fragility_model_id)
);

CREATE TABLE ned_app_fragilitycurve (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fragility_model_id VARCHAR(255) NOT NULL
        REFERENCES ned_app_fragilitymodel(fragility_model_id),
    basis VARCHAR(50),
    num_observations INTEGER,
    ds_rank INTEGER,
    ds_description TEXT NOT NULL,
    median DECIMAL,
    beta DECIMAL,
    probability DECIMAL
);
"""


def _seed(conn: sqlite3.Connection) -> None:
    """Insert a small hand-built dataset covering the shapes ui/db.py's
    queries and post-processing rely on: two major groups (so
    get_major_groups/get_groups have something to filter), two groups within
    one major group (so Group letter-recombination + get_groups filtering are
    exercised), a component with no subelement (fillna('—') path), and one
    fully wired-up component -> experiment -> fragility model -> curve chain
    (via both bridge tables) for the relational queries."""
    conn.executescript(_SCHEMA)

    conn.executemany(
        'INSERT INTO ned_app_component '
        '(id, name, component_id, major_group, "group", element, subelement) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        [
            (
                'B2011',
                'Curtain Wall',
                'B.20.1.1',
                'B - SHELL',
                '20 - Exterior Enclosure',
                '1 - Exterior Walls',
                '1 - Curtain Walls',
            ),
            (
                'B2012',
                'Storefront',
                'B.20.1.2',
                'B - SHELL',
                '20 - Exterior Enclosure',
                '1 - Exterior Walls',
                '2 - Storefronts',
            ),
            (
                'B3010',
                'Built-Up Roofing',
                'B.30.1.0',
                'B - SHELL',
                '30 - Roofing',
                '1 - Roof Coverings',
                None,
            ),
            (
                'D2010',
                'Sprinkler Riser',
                'D.20.1.0',
                'D - SERVICES',
                '20 - Plumbing',
                '1 - Fire Protection',
                None,
            ),
        ],
    )

    conn.executemany(
        'INSERT INTO ned_app_reference '
        '(reference_id, reference_label, title, author, year, study_type, '
        'comp_type, pdf_saved, csl_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [
            (
                'Smith-2020',
                '',
                'A Study of Curtain Walls',
                'Smith',
                2020,
                'Experiment',
                '',
                0,
                json.dumps({'DOI': '10.1000/xyz123'}),
            ),
            (
                'Jones-2021',
                '',
                'Storefront Glazing Performance',
                'Jones',
                2021,
                'Analytical Study',
                '',
                0,
                json.dumps({'URL': 'https://example.com/paper'}),
            ),
        ],
    )

    conn.executemany(
        'INSERT INTO ned_app_experiment '
        '(id, reference_id, component_id, specimen, test_type, '
        'comp_description, ds_description, edp_metric, edp_unit, edp_value, '
        'ds_rank, ds_class) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [
            (
                'EXP-001',
                'Smith-2020',
                'B.20.1.1',
                'S1',
                'Dynamic, uniaxial',
                'Wall panel',
                'Cracking observed',
                'Story Drift Ratio',
                'Ratio',
                0.02,
                1,
                'Consequential',
            ),
            (
                'EXP-002',
                'Jones-2021',
                'B.20.1.2',
                'S2',
                'Monotonic, lateral',
                'Storefront glazing',
                'No visible damage',
                'Peak Floor Acceleration, horizontal',
                'g',
                0.5,
                1,
                'No damage',
            ),
        ],
    )

    conn.execute(
        'INSERT INTO ned_app_fragilitymodel '
        '(fragility_model_id, reference_id, model_id, comp_description, '
        'edp_metric, edp_unit) VALUES (?, ?, ?, ?, ?, ?)',
        (
            'Smith-2020|M1',
            'Smith-2020',
            'M1',
            'Wall panel fragility',
            'Story Drift Ratio',
            'Ratio',
        ),
    )

    conn.execute(
        'INSERT INTO ned_app_componentfragilitymodelbridge '
        '(component_id, fragility_model_id) VALUES (?, ?)',
        ('B.20.1.1', 'Smith-2020|M1'),
    )
    conn.execute(
        'INSERT INTO ned_app_experimentfragilitymodelbridge '
        '(experiment_id, fragility_model_id) VALUES (?, ?)',
        ('EXP-001', 'Smith-2020|M1'),
    )

    conn.execute(
        'INSERT INTO ned_app_fragilitycurve '
        '(fragility_model_id, basis, num_observations, ds_rank, '
        'ds_description, median, beta, probability) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        ('Smith-2020|M1', 'Experiment', 5, 1, 'Cracking', 0.02, 0.3, 1.0),
    )

    conn.commit()


@pytest.fixture
def fixture_db_path(tmp_path) -> str:
    """Build the hand-seeded fixture SQLite DB for one test and return its
    path. Built fresh per test (in tmp_path) rather than committed as a
    binary fixture, so the schema stays visible/reviewable as code."""
    path = tmp_path / 'fixture.sqlite3'
    conn = sqlite3.connect(path)
    try:
        _seed(conn)
    finally:
        conn.close()
    return str(path)


@pytest.fixture
def db_module(fixture_db_path, monkeypatch):
    """The ui/db.py module, pointed at the fixture DB.

    db.py's query functions are wrapped in @st.cache_data, which caches by
    function+args only (not by _DB_PATH), so without clearing the cache here
    a query made in an earlier test against a different fixture DB would
    leak into this one. st.cache_data.clear() clears every @st.cache_data
    function process-wide, not just db.py's, but that's fine in a test
    process with no other cached state.
    """
    import db as db_module_

    monkeypatch.setattr(db_module_, '_DB_PATH', fixture_db_path)
    st.cache_data.clear()
    yield db_module_
    st.cache_data.clear()
