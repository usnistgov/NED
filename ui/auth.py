import hmac
import os

import streamlit as st

_APP_USERNAME = os.environ.get("APP_USERNAME")
_APP_PASSWORD = os.environ.get("APP_PASSWORD")


def check_password() -> bool:
    """Show a login form and return True if the user is authenticated."""
    if not _APP_USERNAME or not _APP_PASSWORD:
        st.error(
            "Authentication is enabled but APP_USERNAME and/or APP_PASSWORD "
            "environment variables are not set."
        )
        st.stop()

    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        "<div style='max-width:400px;margin:8rem auto;'>",
        unsafe_allow_html=True,
    )
    st.image("assets/logo.png", width=80)
    st.markdown("### Nonstructural Element Database")
    st.caption("Sign in to continue.")

    st.warning(
        "⚠️ **Development preview** — this site is under active development and is for "
        "testing and feedback purposes only. Data and features may change without notice.",
        icon=None,
    )

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        if hmac.compare_digest(username, _APP_USERNAME) and hmac.compare_digest(
            password, _APP_PASSWORD
        ):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.markdown("</div>", unsafe_allow_html=True)
    return False
