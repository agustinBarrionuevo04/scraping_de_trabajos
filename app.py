from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from ui.data_loader import load_jobs

st.set_page_config(page_title="Job Scraper — Revisión", layout="wide")

DB_PATH = os.environ.get("JOBS_DB_PATH", "jobs.db")

st.title("Job Scraper — Ofertas")

st.sidebar.header("Filtros")

min_score = st.sidebar.slider(
    "Score mínimo", min_value=0.0, max_value=1.0, value=0.5, step=0.01
)

text_search = st.sidebar.text_input("Buscar en título/empresa")

if st.sidebar.button("Recargar datos"):
    st.cache_data.clear()

sort_label_to_col = {
    "match_score desc": "match_score",
    "posted_date desc": "posted_date",
    "scraped_at desc": "scraped_at",
}
sort_by = st.sidebar.selectbox(
    "Ordenar por",
    options=list(sort_label_to_col.keys()),
    index=0,
)

df = load_jobs(DB_PATH)

if df.empty:
    st.warning("No hay ofertas en la base de datos todavía.")
    st.stop()

df["_posted_date_dt"] = pd.to_datetime(df["posted_date"], errors="coerce")
df["posted_date_display"] = df["_posted_date_dt"].dt.strftime("%d/%m/%Y")

df_filtered = df[
    (df["match_score"] >= min_score) | (df["match_score"].isna())
].copy()

sources = sorted(df["source"].dropna().unique())
selected_sources = st.sidebar.multiselect("Source", options=sources, default=list(sources))
if selected_sources:
    df_filtered = df_filtered[df_filtered["source"].isin(selected_sources)]

locations = sorted(df["location"].dropna().unique())
selected_locations = st.sidebar.multiselect("Location", options=locations, default=list(locations))
if selected_locations:
    df_filtered = df_filtered[df_filtered["location"].isin(selected_locations)]

if text_search:
    text_lower = text_search.lower()
    mask = (
        df_filtered["title"].str.lower().str.contains(text_lower, na=False)
        | df_filtered["company"].str.lower().str.contains(text_lower, na=False)
    )
    df_filtered = df_filtered[mask]

sort_col = sort_label_to_col[sort_by]
ascending = False
na_pos = "last"
if sort_col == "match_score":
    na_pos = "last"
elif sort_col == "posted_date":
    sort_col = "_posted_date_dt"
elif sort_col == "scraped_at":
    na_pos = "last"

df_filtered = df_filtered.sort_values(sort_col, ascending=ascending, na_position=na_pos)

df_filtered = df_filtered.reset_index(drop=True)

st.write(f"{len(df_filtered)} ofertas de {len(df)} totales")

display_df = df_filtered[["title", "company", "location", "match_score", "posted_date_display", "source"]].copy()
display_df = display_df.rename(columns={"posted_date_display": "posted_date"})
display_df["match_score"] = display_df["match_score"].apply(
    lambda x: round(x, 2) if pd.notna(x) else None
)

st.dataframe(
    display_df,
    width="stretch",
    hide_index=True,
    column_config={
        "match_score": st.column_config.ProgressColumn(
            "match_score",
            format="%.2f",
            min_value=0,
            max_value=1,
        ),
    },
)

if not df_filtered.empty:
    options = [
        f"{row['title']} — {row['company']}" for _, row in df_filtered.iterrows()
    ]
    selected_label = st.selectbox("Ver detalle de:", options)

    if selected_label:
        idx = options.index(selected_label)
        row = df_filtered.iloc[idx]

        with st.expander(
            f"Detalle: {row['title']} — {row['company']}", expanded=True
        ):
            col1, col2 = st.columns([2, 1])
            with col1:
                score = row.get("match_score")
                if pd.notna(score):
                    st.write(f"**Score:** {score:.2f}")
                    st.progress(float(score))
                else:
                    st.write("**Score:** sin puntuar")
                st.write("**Descripción:**")
                st.text(row.get("description", ""))
            with col2:
                url = row.get("url")
                if pd.notna(url):
                    st.link_button("Ver oferta original", url)
