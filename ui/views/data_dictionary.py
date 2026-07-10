import os

import streamlit as st

_DOC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'assets',
    'data_dictionary.md',
)


@st.cache_data
def _load_doc() -> str:
    with open(_DOC_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def render() -> None:
    st.markdown('---')
    st.markdown(_load_doc())
