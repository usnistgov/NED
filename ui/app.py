import os
from typing import Any

import streamlit as st

import auth
import styles
from utils import scroll_to_top_on_page_change
from views import (
    compare_fragilities,
    component_detail,
    components,
    data_dictionary,
    experiment,
    fragility_model,
    home,
)

_ASSETS = os.path.join(os.path.dirname(__file__), 'assets')
_LOGO_PATH = os.path.join(_ASSETS, 'logo.png')
# The wordmark is used in the top nav only; the square mark stays as the
# favicon and on the pages that render a logo of their own.
_NAV_LOGO_PATH = os.path.join(_ASSETS, 'logo-2.png')

st.set_page_config(
    page_title='NED – Nonstructural Element Database',
    page_icon=_LOGO_PATH,
    layout='wide',
)

styles.inject()

_auth_enabled = os.environ.get('AUTH_ENABLED', 'true').lower() != 'false'
_authenticated = not _auth_enabled or bool(st.session_state.get('authenticated'))

# ── Pages ──────────────────────────────────────────────────────────────────────
# Every page's render function takes the `pages` mapping below so it can build
# st.page_link/st.switch_page targets for other pages without an import cycle
# (this module is the only place the view modules and their st.Page wrappers
# both exist).
PAGES: dict[str, Any] = {}


def _components() -> None:
    components.render(PAGES)


def _component_detail() -> None:
    component_detail.render(PAGES)


def _fragility_model() -> None:
    fragility_model.render(PAGES)


def _experiment() -> None:
    experiment.render(PAGES)


def _compare_fragilities() -> None:
    compare_fragilities.render(PAGES)


# Component database is the default page so that clicking the header logo
# lands there — Streamlit's logo always navigates to the default page, and
# `st.logo(link=...)` only takes an absolute URL, which it opens in a new tab.
home_page = st.Page(home.render, title='About NED', url_path='home')
components_page = st.Page(
    _components, title='Component database', url_path='components', default=True
)
compare_page = st.Page(
    _compare_fragilities,
    title='Compare fragilities',
    url_path='compare-fragilities',
)
data_dictionary_page = st.Page(
    data_dictionary.render,
    title='Data dictionary',
    url_path='data-dictionary',
)
component_detail_page = st.Page(
    _component_detail,
    title='Component Detail',
    url_path='component',
    visibility='hidden',
)
fragility_model_page = st.Page(
    _fragility_model,
    title='Fragility Model Detail',
    url_path='fragility-model',
    visibility='hidden',
)
experiment_page = st.Page(
    _experiment,
    title='Experiment Detail',
    url_path='experiment',
    visibility='hidden',
)

PAGES.update({
    'home': home_page,
    'components': components_page,
    'compare': compare_page,
    'data_dictionary': data_dictionary_page,
    'component_detail': component_detail_page,
    'fragility_model': fragility_model_page,
    'experiment': experiment_page,
})

# The full real page set is registered on every run, signed in or not, so
# the browser's current URL (e.g. a shared `/component?component=...` link
# opened cold) resolves against it from the very first run instead of
# against a narrower placeholder that would forget the path once real
# navigation takes over. `position` alone toggles the visible chrome: hidden
# pre-auth (a run that skipped registering navigation entirely would leave
# the previous run's top nav bar stuck in the page header, since Streamlit
# doesn't clear a position='top' nav on its own between runs), top once
# signed in.
nav = st.navigation(
    [
        components_page,
        compare_page,
        data_dictionary_page,
        home_page,
        component_detail_page,
        fragility_model_page,
        experiment_page,
    ],
    position='top' if _authenticated else 'hidden',
)

if not _authenticated:
    auth.check_password()
    st.stop()

st.logo(_NAV_LOGO_PATH, size='large')

# ── Legacy root-URL redirect ─────────────────────────────────────────────────
# Old shared links point at the bare root with just a `?component=`,
# `?fragility_model=`, or `?experiment=` query param and no page path, which
# resolves to the default page. Forward them to the matching detail page, once
# per session — the guard keeps this from re-firing (and overriding the user's
# own Back navigation) every time a rerun happens to land back on the default
# page with one of these params still in the URL.
if nav is components_page and not st.session_state.get('_legacy_redirect_done'):
    st.session_state['_legacy_redirect_done'] = True
    qp = st.query_params
    target = None
    if 'experiment' in qp:
        params = {'experiment': qp['experiment']}
        if 'component' in qp:
            params['component'] = qp['component']
        target = (experiment_page, params)
    elif 'fragility_model' in qp:
        params = {'fragility_model': qp['fragility_model']}
        if 'component' in qp:
            params['component'] = qp['component']
        target = (fragility_model_page, params)
    elif 'component' in qp:
        target = (component_detail_page, {'component': qp['component']})
    if target is not None:
        target_page, target_params = target
        st.switch_page(target_page, query_params=target_params)

scroll_to_top_on_page_change(nav.url_path)

# ── Page dispatch ──────────────────────────────────────────────────────────────
nav.run()
