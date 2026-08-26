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

_LOGO_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')

st.set_page_config(
    page_title='NED – Nonstructural Element Database',
    page_icon=_LOGO_PATH,
    layout='wide',
    initial_sidebar_state='expanded',
)

styles.inject()

if (
    os.environ.get('AUTH_ENABLED', 'true').lower() != 'false'
    and not auth.check_password()
):
    st.stop()

# ── Pages ──────────────────────────────────────────────────────────────────────
# Every page's render function takes the `pages` mapping below so it can build
# st.page_link/st.switch_page targets for other pages without an import cycle
# (this module is the only place the view modules and their st.Page wrappers
# both exist).
PAGES: dict[str, Any] = {}


def _component_detail() -> None:
    component_detail.render(PAGES)


def _fragility_model() -> None:
    fragility_model.render(PAGES)


def _experiment() -> None:
    experiment.render(PAGES)


def _compare_fragilities() -> None:
    compare_fragilities.render(PAGES)


def _components() -> None:
    components.render(PAGES)


home_page = st.Page(home.render, title='Home', url_path='home', default=True)
components_page = st.Page(_components, title='Components', url_path='components')
compare_page = st.Page(
    _compare_fragilities, title='Compare Fragilities', url_path='compare-fragilities'
)
data_dictionary_page = st.Page(
    data_dictionary.render, title='Data Dictionary', url_path='data-dictionary'
)
component_detail_page = st.Page(
    _component_detail, title='Component Detail', url_path='component'
)
fragility_model_page = st.Page(
    _fragility_model, title='Fragility Model Detail', url_path='fragility-model'
)
experiment_page = st.Page(
    _experiment, title='Experiment Detail', url_path='experiment'
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

nav = st.navigation(
    [
        home_page,
        components_page,
        compare_page,
        data_dictionary_page,
        component_detail_page,
        fragility_model_page,
        experiment_page,
    ],
    position='hidden',
)

# ── Legacy root-URL redirect ─────────────────────────────────────────────────
# Old shared links point at the bare root with just a `?component=`,
# `?fragility_model=`, or `?experiment=` query param and no page path, which
# resolves to this default (Home) page. Forward them to the matching detail
# page, once per session — the guard keeps this from re-firing (and
# overriding the user's own Back navigation) every time a rerun happens to
# land back on Home with one of these params still in the URL.
if nav is home_page and not st.session_state.get('_legacy_redirect_done'):
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

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image('assets/logo.png', width=80)
    st.markdown('### Nonstructural Element Database (NED)')
    st.caption(
        'A curated collection of experimental data, fragility models, and references '
        'for nonstructural building components, organized using the NISTIR taxonomy.'
    )
    st.markdown('---')

    # Plain st.page_link/st.switch_page (no query params) between these
    # pages, rather than st.button + st.switch_page: st.switch_page always
    # emits two separate history.pushState calls to the frontend (one to
    # clear the outgoing page's query params, one for the page change),
    # confirmed with a Playwright-instrumented repro even when no
    # query_params= is passed — so leaving a detail page (which does carry
    # query params) through a plain st.button here still stutters the
    # browser Back button. st.page_link renders a real <a href>, which is
    # always a single history entry. "Compare fragilities" stays a button
    # because it also needs to clear `compare_return_to_fragility` session
    # state before navigating, which a page_link's click can't run — see the
    # handoff for that known trade-off.
    st.page_link(home_page, label='Home', icon='🏠')
    st.page_link(components_page, label='Components', icon='📋')
    st.page_link(compare_page, label='Compare fragilities', icon='⚖️')

    # if st.button('⚖️  Compare fragilities', key='nav_compare'):
    #     st.session_state.pop('compare_return_to_fragility', None)
    #     st.switch_page(compare_page)

    st.page_link(data_dictionary_page, label='Data dictionary', icon='📖')

    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('---')
    if st.button('Sign out', key='nav_logout'):
        st.session_state.clear()
        st.rerun()
    st.caption('Nonstructural Element Database')

# ── Page dispatch ──────────────────────────────────────────────────────────────
nav.run()
