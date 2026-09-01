"""Smoke tests for the native st.navigation router in app.py.

These run against the hand-seeded fixture database built by ``conftest.py``
(the ``fixture_db_path`` fixture), so they need no built database and run
as part of the standard suite and in CI:

    python -m pytest ui/tests -q

``streamlit.testing.v1.AppTest`` has two hard limitations that shape what's
covered here rather than what's ideal:

- It has no browser history model at all, so it cannot simulate real
  Back/Forward button presses. That must be verified manually or with a
  browser-driven tool (e.g. Playwright) against a running app instead — see
  the handoff for how that was done for this change.
- It can't simulate clicking an ``st.page_link`` (it isn't a
  simulate-able widget the way ``st.button`` is), and switching pages
  reliably a second time within one ``AppTest`` instance was unreliable in
  practice. Each test below therefore drives at most one navigation, and the
  page_link-based View/Back controls are checked structurally (their target
  page) rather than by simulating a click.
- The top nav bar is Streamlit's own chrome rather than widgets, so it can
  be neither clicked nor enumerated; only the routing behind it (which page
  is the default) is covered here.

The fixture database is deliberately tiny: one fragility model wired to one
component through the component bridge, and experiments on that same
component. The assertions below therefore check *which* records a page
resolved to and that the page rendered, never how many rows a table drew —
the ``_pick_*`` helpers query for the relationships rather than hardcoding
ids, so growing the seed data doesn't rot these tests.
"""

import sqlite3
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

_UI_DIR = Path(__file__).resolve().parent.parent
_APP_PATH = _UI_DIR / 'app.py'

# AppTest's default 3s script timeout is generous locally but tight on a cold
# CI runner, where the first run pays for importing plotly and Streamlit's
# script-runner machinery.
_RUN_TIMEOUT = 30


@pytest.fixture
def app_db(fixture_db_path, monkeypatch):
    """Point app.py's database access at the conftest fixture DB.

    ``ui/db.py`` resolves ``_DB_PATH`` once at import time and ``AppTest``
    execs app.py inside this same process, so the already-imported ``db``
    module is what the app ends up querying — patch the module attribute,
    and ``DB_PATH`` as well to cover the case where ``db`` hasn't been
    imported yet. Cached results are cleared on both sides for the same
    reason ``conftest.db_module`` clears them: @st.cache_data keys on
    function+args only, not on ``_DB_PATH``, so a query answered against an
    earlier test's fixture DB would otherwise leak into this one.

    Also runs from ``ui/``, because the About NED and sign-in views load
    their logo by the relative path ``assets/logo.png`` — the same working
    directory ``streamlit run app.py`` is launched from. Without this the
    app raises MediaFileStorageError when the suite is invoked from the repo
    root, as CI does.
    """
    monkeypatch.chdir(_UI_DIR)
    monkeypatch.setenv('DB_PATH', fixture_db_path)
    monkeypatch.setenv('AUTH_ENABLED', 'false')

    import db

    monkeypatch.setattr(db, '_DB_PATH', fixture_db_path)
    st.cache_data.clear()
    yield fixture_db_path
    st.cache_data.clear()


def _pick_fragility_model_with_component(db_path: str) -> tuple[str, str]:
    """A (fragility_model_id, component_id) pair from the fixture database,
    rather than hardcoded ids, so the test doesn't rot as the seed data
    changes. The pair is guaranteed to exist by ``conftest._seed()``, so a
    missing one is a broken fixture, not a reason to skip."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("""
            SELECT fm.fragility_model_id, c.id
            FROM ned_app_componentfragilitymodelbridge b
            JOIN ned_app_fragilitymodel fm
                ON fm.fragility_model_id = b.fragility_model_id
            JOIN ned_app_component c ON c.component_id = b.component_id
            ORDER BY fm.fragility_model_id
            LIMIT 1
        """).fetchone()
    finally:
        conn.close()
    assert row is not None, (
        'fixture database has no fragility model linked to a component'
    )
    return row


def _pick_experiment_with_component(db_path: str) -> tuple[str, str]:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("""
            SELECT e.id, c.id
            FROM ned_app_experiment e
            JOIN ned_app_component c ON c.component_id = e.component_id
            ORDER BY e.id
            LIMIT 1
        """).fetchone()
    finally:
        conn.close()
    assert row is not None, (
        'fixture database has no experiment linked to a component'
    )
    return row


def test_default_page_is_the_component_database(app_db):
    """The top nav bar replaced the sidebar's page_link controls, and it is
    Streamlit's own chrome rather than widgets, so AppTest can neither click
    it nor enumerate it (``AppTest.switch_page`` only drives file-based
    ``pages/*.py``). What is checkable is the routing decision behind it:
    Component database is registered as the default page, so a bare URL —
    and a click on the header logo, which Streamlit always routes to the
    default page — lands there rather than on About NED."""
    at = AppTest.from_file(str(_APP_PATH))
    at.run(timeout=_RUN_TIMEOUT)
    assert not at.exception

    assert any('<h1>Components</h1>' in m.value for m in at.markdown)
    assert not any('What is NED?' in m.value for m in at.markdown)


def test_component_view_links_target_component_detail(app_db):
    """The per-row View controls are st.page_link (see app.py for why);
    AppTest can't click them, so this checks they point at the right page
    rather than simulating the click."""
    at = AppTest.from_file(str(_APP_PATH))
    at.run(timeout=_RUN_TIMEOUT)
    assert not at.exception

    view_links = [pl for pl in at.get('page_link') if pl.label == 'View']
    assert view_links, 'the component table rendered no View links'
    assert {pl.page for pl in view_links} == {'component'}


def test_fragility_model_only_deep_link_backfills_component(app_db):
    """A `?fragility_model=` URL with no `component` must still resolve a
    real, non-empty component id before "Back to Component" draws."""
    fragility_model_id, expected_component = _pick_fragility_model_with_component(
        app_db
    )
    at = AppTest.from_file(str(_APP_PATH))
    at.query_params['fragility_model'] = fragility_model_id
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert at.session_state['selected_component_id'] == expected_component
    assert at.query_params.get('component') == [expected_component]
    assert any('Fragility Model View' in m.value for m in at.markdown)


def test_experiment_only_deep_link_backfills_component(app_db):
    """Same backfill, via the experiment -> component bridge instead of the
    fragility-model one."""
    experiment_id, expected_component = _pick_experiment_with_component(app_db)
    at = AppTest.from_file(str(_APP_PATH))
    at.query_params['experiment'] = experiment_id
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert at.session_state['selected_component_id'] == expected_component
    assert at.query_params.get('component') == [expected_component]
    assert any('Experiment View' in m.value for m in at.markdown)


def test_component_deep_link_renders_component_detail(app_db):
    """The third deep-link param. Unlike the two above there's nothing to
    backfill, so this just pins that `?component=` resolves to the detail
    page for that component and not to the default (Home) page."""
    _, component_id = _pick_experiment_with_component(app_db)
    at = AppTest.from_file(str(_APP_PATH))
    at.query_params['component'] = component_id
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert at.session_state['selected_component_id'] == component_id
    assert any('Component View' in m.value for m in at.markdown)


def test_legacy_redirect_fires_once_per_session(app_db):
    """A bare `?fragility_model=`/`?experiment=`/`?component=` URL with no
    page path resolves to the default (Home) page, which should forward to
    the matching detail page exactly once per session — not on every rerun
    that happens to land back on Home with a leftover deep-link param still
    in the URL."""
    fragility_model_id, _ = _pick_fragility_model_with_component(app_db)
    at = AppTest.from_file(str(_APP_PATH))
    at.query_params['fragility_model'] = fragility_model_id
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert at.session_state['_legacy_redirect_done']
    assert any('Fragility Model View' in m.value for m in at.markdown)

    # A later rerun in the same AppTest session (same session_state) with a
    # *different* deep-link param present must not redirect again -- it
    # should stay on the (AppTest always re-renders the default) page
    # instead of jumping to the new target.
    #
    # This has to be a *real* experiment id: the experiment view bails out
    # at its "not found" warning before drawing its header, so a bogus id
    # would make the assertion below hold whether or not the guard works.
    experiment_id, _ = _pick_experiment_with_component(app_db)
    at.query_params.clear()
    at.query_params['experiment'] = experiment_id
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert not any('Experiment View' in m.value for m in at.markdown)
    assert not any('Fragility Model View' in m.value for m in at.markdown)
