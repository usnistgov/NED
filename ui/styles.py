import streamlit as st

_CSS = """
<style>
/* ── Global ── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #ffffff;
    font-family: "Inter", "Segoe UI", sans-serif;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #f4f5f7;
    border-right: 1px solid #e0e0e0;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    padding-top: 1rem;
}

/* Sidebar nav button base style */
div[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0.55rem 1rem;
    font-size: 0.92rem;
    color: #333333;
    cursor: pointer;
    transition: background 0.15s;
}
div[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #e8eaed;
    color: #111;
}

/* Active nav item (applied via a class we inject) */
div[data-testid="stSidebar"] .stButton.active-nav > button {
    background-color: #D94F3D;
    color: #ffffff !important;
    font-weight: 600;
}

/* ── Main header area ── */
.ned-header h1 {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 0.15rem;
}
.ned-header p {
    font-size: 0.95rem;
    color: #555;
    margin-top: 0;
}

/* ── Summary metric boxes ── */
.metric-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.metric-box {
    background: #f4f5f7;
    border-radius: 10px;
    padding: 0.75rem 1.25rem;
    min-width: 140px;
}
.metric-box .metric-label {
    font-size: 0.78rem;
    color: #777;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.2rem;
}
.metric-box .metric-value {
    font-size: 1.45rem;
    font-weight: 700;
    color: #1a1a2e;
}

/* ── Dataframe tweaks ── */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}

/* ── Inline selectbox labels ── */
div[data-testid="stSelectbox"] {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.75rem;
}
div[data-testid="stSelectbox"] label {
    white-space: nowrap;
    margin-bottom: 0;
    min-width: fit-content;
}
div[data-testid="stSelectbox"] > div {
    flex: 1;
}

/* ── Component detail attribute grid ── */
.attr-grid {
    display: grid;
    grid-template-columns: 200px 1fr;
    row-gap: 0.6rem;
    column-gap: 1rem;
    margin-bottom: 1.5rem;
}
.attr-label {
    font-size: 0.88rem;
    color: #555;
    font-weight: 600;
}
.attr-value {
    font-size: 0.95rem;
    color: #1a1a2e;
}
.attr-hint {
    grid-column: 2;
    font-size: 0.78rem;
    color: #888;
    margin-top: -0.4rem;
}
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
