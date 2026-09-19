"""Streamlit dashboard for browsing vgeval runs.

Tabs:
  * Leaderboard   — overall + per-dimension means per provider
  * Gallery       — source image -> output video with scores
  * Compare       — two providers on one prompt, side by side + rationale
  * Run detail    — per-dimension bar chart

Run via `vgeval dashboard`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `vgeval` importable when Streamlit runs this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from vgeval.config import get_settings  # noqa: E402
from vgeval.report import leaderboard, per_dimension, run_dims  # noqa: E402
from vgeval.store import RunStore  # noqa: E402

st.set_page_config(page_title="vgeval", layout="wide")


def list_runs() -> list[str]:
    runs_dir = get_settings().runs_dir
    if not runs_dir.exists():
        return []
    runs = [p.name for p in runs_dir.iterdir() if (p / "manifest.json").exists()]
    return sorted(runs, reverse=True)


runs = list_runs()
if not runs:
    st.title("vgeval")
    st.info("No runs found. Generate one with `vgeval run` then `vgeval judge --stub`.")
    st.stop()

st.sidebar.title("vgeval")
run_id = st.sidebar.selectbox("Run", runs)
store = RunStore.open(run_id)
manifest = store.read_manifest()
st.sidebar.caption(f"suite {manifest.suite_version} · rubric {manifest.rubric_version}")

results = {s.job_id: s for s in store.read_results()}
requests = store.read_requests()
states = store.read_job_states()

tab_board, tab_gallery, tab_compare, tab_detail = st.tabs(
    ["Leaderboard", "Gallery", "Compare", "Run detail"]
)

with tab_board:
    st.header("Leaderboard")
    board = leaderboard(run_id)
    if not board:
        st.warning("No judge scores yet. Run `vgeval judge`.")
    else:
        st.dataframe(pd.DataFrame(board), use_container_width=True, hide_index=True)

with tab_gallery:
    st.header("Gallery")
    for job_id, state in states.items():
        if not state.video_path:
            continue
        req = requests.get(job_id)
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                if req and Path(req.source_image).exists():
                    st.image(req.source_image, caption="source", use_container_width=True)
            with c2:
                if Path(state.video_path).exists():
                    st.video(state.video_path)
            with c3:
                st.write(f"**{state.provider}** · `{job_id}`")
                if req:
                    st.caption(req.prompt)
                sc = results.get(job_id)
                if sc:
                    st.dataframe(
                        pd.DataFrame([sc.dims]).T.rename(columns={0: "score"}),
                        use_container_width=True,
                    )
                    if sc.defects:
                        st.error("⚠️ Defects found:\n" + "\n".join(f"- {d}" for d in sc.defects))
                    if sc.needs_review:
                        st.caption("Needs human review: " + ", ".join(sc.needs_review))

with tab_compare:
    st.header("Compare providers")
    providers = manifest.providers
    prompt_ids = sorted({r.prompt_id for r in requests.values()})
    if len(providers) < 2:
        st.info("Add a second provider to compare (see docs/adding-a-provider.md).")
    else:
        pid = st.selectbox("Prompt", prompt_ids)
        cols = st.columns(2)
        pa = cols[0].selectbox("A", providers, index=0)
        pb = cols[1].selectbox("B", providers, index=1)
        for col, prov in ((cols[0], pa), (cols[1], pb)):
            jid = f"{prov}__{pid}"
            st_state = states.get(jid)
            with col:
                if st_state and st_state.video_path and Path(st_state.video_path).exists():
                    st.video(st_state.video_path)
                sc = results.get(jid)
                if sc:
                    st.dataframe(
                        pd.DataFrame([sc.dims]).T.rename(columns={0: "score"}),
                        use_container_width=True,
                    )
                    if sc.rationale:
                        st.caption(sc.rationale)
                    if sc.defects:
                        st.error("⚠️ " + " · ".join(sc.defects))

with tab_detail:
    st.header("Per-dimension means")
    rows = per_dimension(run_id)
    dims = run_dims(run_id)
    value_dims = [d for d in dims if any(d in r for r in rows)]
    if rows and value_dims:
        df = pd.DataFrame(rows).melt(
            id_vars=["provider", "n"], value_vars=value_dims,
            var_name="dimension", value_name="score",
        ).dropna(subset=["score"])
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("dimension:N", sort=value_dims),
                y="score:Q",
                color="provider:N",
                xOffset="provider:N",
                tooltip=["provider", "dimension", "score"],
            )
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.warning("No judge scores yet.")
