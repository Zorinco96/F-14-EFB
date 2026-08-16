"""Legacy Streamlit entry point.

The full v3 application is `app.py`. This file remains so old launch commands do
not fail, but it intentionally routes into the current application.
"""

from app import *  # noqa: F401,F403
