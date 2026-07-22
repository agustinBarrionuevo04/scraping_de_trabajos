from __future__ import annotations

import os
import sqlite3

import pandas as pd
import streamlit as st


@st.cache_data(ttl=60)
def load_jobs(db_path: str | None = None) -> pd.DataFrame:
    path = db_path or os.environ.get("JOBS_DB_PATH", "jobs.db")
    conn = sqlite3.connect(path)
    df = pd.read_sql("SELECT * FROM jobs", conn)
    conn.close()
    return df
