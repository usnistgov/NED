import os

import streamlit as st

import auth
import styles
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

# ── Query-param routing ────────────────────────────────────────────────────────
if 'experiment' in st.query_params:
    st.session_state['page'] = 'Experiment Detail'
    st.session_state['selected_experiment_id'] = st.query_params['experiment']
    st.session_state['selected_component_id'] = st.query_params.get('component', '')
elif 'fragility_model' in st.query_params:
    st.session_state['page'] = 'Fragility Model Detail'
    st.session_state['selected_fragility_model_id'] = st.query_params[
        'fragility_model'
    ]
    st.session_state['selected_component_id'] = st.query_params.get('component', '')
elif 'component' in st.query_params:
    st.session_state['page'] = 'Component Detail'
    st.session_state['selected_component_id'] = st.query_params['component']

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image('assets/logo.png', width=80)
    st.markdown('### Nonstructural Element Database (NED)')
    st.caption(
        'A curated collection of experimental data, fragility models, and references '
        'for nonstructural building components, organized using the NISTIR taxonomy.'
    )
    # st.warning("⚠️ **Development preview.** This site is under active development and is for testing and feedback purposes only.")
    st.markdown('---')

    page = st.session_state.get('page', 'Home')

    if st.button('🏠  Home', key='nav_home'):
        st.query_params.clear()
        st.session_state['page'] = 'Home'
        st.rerun()

    if st.button('📋  Components', key='nav_components'):
        st.query_params.clear()
        st.session_state['page'] = 'Components'
        st.rerun()

    if st.button('⚖️  Compare fragilities', key='nav_compare'):
        st.query_params.clear()
        st.session_state['page'] = 'Compare Fragilities'
        st.rerun()

    if st.button('📖  Data dictionary', key='nav_data_dictionary'):
        st.query_params.clear()
        st.session_state['page'] = 'Data Dictionary'
        st.rerun()

    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('---')
    if st.button('Sign out', key='nav_logout'):
        st.session_state.clear()
        st.rerun()
    st.caption('Nonstructural Element Database')

# ── Page dispatch ──────────────────────────────────────────────────────────────
page = st.session_state.get('page', 'Home')

if page == 'Home':
    home.render()
elif page == 'Components':
    components.render()
elif page == 'Compare Fragilities':
    compare_fragilities.render()
elif page == 'Data Dictionary':
    data_dictionary.render()
elif page == 'Component Detail':
    component_detail.render()
elif page == 'Fragility Model Detail':
    fragility_model.render()
elif page == 'Experiment Detail':
    experiment.render()
