"""Smoke test: the dashboard script runs end-to-end without raising."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def test_dashboard_renders_without_exceptions():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert len(at.metric) == 4


def test_region_filter_changes_table():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.selectbox[0].select("London").run()
    assert not at.exception
    assert len(at.dataframe[0].value) < 106
