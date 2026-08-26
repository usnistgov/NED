"""Smoke tests for the native st.navigation router in app.py.

Run from the ``ui/`` directory (matching how the app itself resolves its
database path), pointed at a real built database, e.g.:

    cd ui
    DB_PATH=../db.sqlite3 AUTH_ENABLED=false python -m unittest tests.test_navigation

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
  page_link-based sidebar controls are checked structurally (their target
  page) rather than by simulating a click.
"""

import os
import sqlite3
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

_UI_DIR = Path(__file__).resolve().parent.parent
_APP_PATH = _UI_DIR / 'app.py'

os.environ.setdefault('AUTH_ENABLED', 'false')


def _db_path() -> str:
    return os.environ.get('DB_PATH', str(_UI_DIR / 'backend' / 'db.sqlite3'))


def _pick_fragility_model_with_component() -> tuple[str, str]:
    """A (fragility_model_id, component_id) pair from the real database,
    rather than a hardcoded id, so the test doesn't rot as source data
    changes."""
    conn = sqlite3.connect(_db_path())
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
    if row is None:
        raise unittest.SkipTest(
            'no fragility model with a linked component in the test database'
        )
    return row


def _pick_experiment_with_component() -> tuple[str, str]:
    conn = sqlite3.connect(_db_path())
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
    if row is None:
        raise unittest.SkipTest(
            'no experiment with a linked component in the test database'
        )
    return row


@unittest.skipUnless(
    os.path.exists(_db_path()), f'no database at {_db_path()!r} — set DB_PATH'
)
class NavigationSmokeTest(unittest.TestCase):
    def test_sidebar_page_links_target_expected_pages(self):
        """Home / Components / Data dictionary are st.page_link controls
        (see app.py for why); AppTest can't click them, so this checks each
        points at the right page rather than simulating the click."""
        at = AppTest.from_file(str(_APP_PATH))
        at.run()
        self.assertFalse(at.exception)

        links = {pl.label: pl.page for pl in at.get('page_link')}
        self.assertEqual(links.get('Home'), '')
        self.assertEqual(links.get('Components'), 'components')
        self.assertEqual(links.get('Compare fragilities'), 'compare-fragilities')
        self.assertEqual(links.get('Data dictionary'), 'data-dictionary')

    def test_fragility_model_only_deep_link_backfills_component(self):
        """A `?fragility_model=` URL with no `component` must still resolve
        a real, non-empty component id before "Back to Component" draws."""
        fragility_model_id, expected_component = (
            _pick_fragility_model_with_component()
        )
        at = AppTest.from_file(str(_APP_PATH))
        at.query_params['fragility_model'] = fragility_model_id
        at.run()

        self.assertFalse(at.exception)
        self.assertEqual(
            at.session_state['selected_component_id'], expected_component
        )
        self.assertEqual(at.query_params.get('component'), [expected_component])
        self.assertTrue(any('Fragility Model View' in m.value for m in at.markdown))

    def test_experiment_only_deep_link_backfills_component(self):
        """Same backfill, via the experiment -> component bridge instead of
        the fragility-model one."""
        experiment_id, expected_component = _pick_experiment_with_component()
        at = AppTest.from_file(str(_APP_PATH))
        at.query_params['experiment'] = experiment_id
        at.run()

        self.assertFalse(at.exception)
        self.assertEqual(
            at.session_state['selected_component_id'], expected_component
        )
        self.assertEqual(at.query_params.get('component'), [expected_component])
        self.assertTrue(any('Experiment View' in m.value for m in at.markdown))

    def test_legacy_redirect_fires_once_per_session(self):
        """A bare `?fragility_model=`/`?experiment=`/`?component=` URL with
        no page path resolves to the default (Home) page, which should
        forward to the matching detail page exactly once per session — not
        on every rerun that happens to land back on Home with a leftover
        deep-link param still in the URL."""
        fragility_model_id, _ = _pick_fragility_model_with_component()
        at = AppTest.from_file(str(_APP_PATH))
        at.query_params['fragility_model'] = fragility_model_id
        at.run()

        self.assertFalse(at.exception)
        self.assertTrue(at.session_state['_legacy_redirect_done'])
        self.assertTrue(any('Fragility Model View' in m.value for m in at.markdown))

        # A later rerun in the same AppTest session (same session_state)
        # with a *different* deep-link param present must not redirect
        # again -- it should stay on the (AppTest always re-renders the
        # default) page instead of jumping to the new target.
        at.query_params.clear()
        at.query_params['experiment'] = 'does-not-matter-guard-should-hold'
        at.run()

        self.assertFalse(at.exception)
        self.assertFalse(any('Experiment View' in m.value for m in at.markdown))
        self.assertFalse(any('Fragility Model View' in m.value for m in at.markdown))


if __name__ == '__main__':
    unittest.main()
