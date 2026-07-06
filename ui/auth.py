import hmac
import os

import streamlit as st


def _load_credentials() -> dict[str, str]:
    """Build the set of valid logins from environment variables.

    APP_CREDENTIALS holds multiple accounts as "user1:pass1,user2:pass2".
    APP_USERNAME/APP_PASSWORD (the original single-account vars) are still
    honored so existing deployments keep working unchanged.
    """
    credentials: dict[str, str] = {}

    for pair in os.environ.get('APP_CREDENTIALS', '').split(','):
        username, sep, password = pair.strip().partition(':')
        if sep and username and password:
            credentials[username] = password

    legacy_user = os.environ.get('APP_USERNAME')
    legacy_password = os.environ.get('APP_PASSWORD')
    if legacy_user and legacy_password:
        credentials.setdefault(legacy_user, legacy_password)

    return credentials


def check_password() -> bool:
    """Show a login form and return True if the user is authenticated."""
    credentials = _load_credentials()

    if not credentials:
        st.error(
            'Authentication is enabled but no credentials are configured. '
            'Set APP_CREDENTIALS (user1:pass1,user2:pass2) or '
            'APP_USERNAME and APP_PASSWORD in environment variables.'
        )
        st.stop()

    if st.session_state.get('authenticated'):
        return True

    st.markdown(
        "<div style='max-width:400px;margin:8rem auto;'>",
        unsafe_allow_html=True,
    )
    st.image('assets/logo.png', width=80)
    st.markdown('### Nonstructural Element Database')
    st.caption('Sign in to continue.')

    st.warning(
        '⚠️ **Development preview** — this site is under active development and is for '
        'testing and feedback purposes only. Data and features may change without notice.',
        icon=None,
    )

    with st.form('login_form'):
        username = st.text_input('Username')
        password = st.text_input('Password', type='password')
        submitted = st.form_submit_button('Sign in', use_container_width=True)

    if submitted:
        # Check every account (no early exit) so response time doesn't leak
        # which usernames exist.
        valid = False
        for expected_username, expected_password in credentials.items():
            if hmac.compare_digest(
                username, expected_username
            ) and hmac.compare_digest(password, expected_password):
                valid = True
        if valid:
            st.session_state['authenticated'] = True
            st.rerun()
        else:
            st.error('Invalid username or password.')

    st.markdown('</div>', unsafe_allow_html=True)
    return False
