"""Centralized settings loader.

Works locally (values come from .env via python-dotenv into os.environ) and
on Streamlit Community Cloud (values come from st.secrets, configured in the
app's Settings -> Secrets). Cloud secrets take priority when present.
"""
import os

try:
    import streamlit as st

    _secrets = st.secrets
except Exception:
    _secrets = {}


def get_setting(key, default=None):
    try:
        if key in _secrets:
            return _secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)
