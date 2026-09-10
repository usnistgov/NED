import os
import re

import streamlit as st

_DOC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'assets',
    'data_dictionary.md',
)


# The document opens with its own `# NED Data Dictionary` heading. The page
# renders the title itself so it matches every other page, so drop the file's
# copy rather than showing it twice at two different sizes.
_LEADING_H1_RE = re.compile(r'\A\s*#[^#\n][^\n]*\n')


@st.cache_data
def _load_doc() -> str:
    with open(_DOC_PATH, 'r', encoding='utf-8') as f:
        return _LEADING_H1_RE.sub('', f.read(), count=1).lstrip()


def render() -> None:
    st.markdown(
        '<div class="ned-header"><h1>Data Dictionary</h1></div>',
        unsafe_allow_html=True,
    )
    st.markdown('---')
    # Keyed so styles.py can scope its table column widths to this page: the
    # key becomes an `st-key-data-dictionary` class on the container.
    with st.container(key='data-dictionary'):
        st.markdown(_load_doc())
