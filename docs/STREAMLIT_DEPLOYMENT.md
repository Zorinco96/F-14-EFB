# Streamlit Community Cloud deployment

Live app: https://f-14-efb.streamlit.app/

Use these deployment fields after the GitHub repository is available:

- Repository: `Zorinco96/F-14-EFB`
- Branch: `main`
- Main file path: `app.py`
- Python version: `3.12`
- Secrets: none required

In Streamlit Community Cloud, choose **Create app**, select the repository and branch, enter the main file path, select Python 3.12 under advanced settings, and deploy. The root `requirements.txt` supplies the application dependencies.

After a push to `main`, Streamlit Community Cloud should rebuild the app automatically. The kneeboard generator requires Pillow, which is declared in the root requirements file.
