"""Streamlit frontend for the NLB availability checker.

Run locally:
    streamlit run app.py

Run on your local network (accessible from your phone on the same Wi-Fi):
    streamlit run app.py --server.address 0.0.0.0 --server.port 8501
    Then open  http://<your-pc-ip>:8501  on your phone.

Deploy for free (accessible anywhere, including phone):
    https://streamlit.io/cloud  → connect your GitHub repo → done.

Environment setup
-----------------
    Create a .env file (or set env vars) with:
        NLB_API_KEY=<your key>
        NLB_APP_CODE=<your app code>
"""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from availability import fetch_all
from models import BookAvailability
from nlb_client import NLBClient
from titles import TITLES

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NLB Availability Checker",
    page_icon="📚",
    layout="centered",         # 'centered' works better on mobile than 'wide'
    initial_sidebar_state="collapsed",
)

load_dotenv()

# ── helper ────────────────────────────────────────────────────────────────────

def _make_client() -> NLBClient | None:
    api_key = os.getenv("NLB_API_KEY")
    app_code = os.getenv("NLB_APP_CODE")
    if not api_key or not app_code:
        st.error(
            "Missing credentials.  "
            "Set **NLB_API_KEY** and **NLB_APP_CODE** in your `.env` file or environment."
        )
        return None
    return NLBClient(api_key, app_code)


@st.cache_data(ttl=1800, show_spinner=False)   # cache results for 30 minutes
def _fetch_results(_client_key: tuple, titles_repr: str) -> list[dict]:
    """Cached wrapper — returns results as plain dicts so Streamlit can pickle them."""
    api_key, app_code = _client_key
    client = NLBClient(api_key, app_code)

    status_placeholder = st.empty()
    log: list[str] = []

    def on_status(msg: str) -> None:
        log.append(msg)
        status_placeholder.markdown(
            "**Fetching…**\n\n" + "\n\n".join(f"- {m}" for m in log[-5:])
        )

    results = fetch_all(TITLES, client, on_status=on_status)
    status_placeholder.empty()

    # Serialise to plain dicts for Streamlit's pickle-based cache
    return [_serialise(r) for r in results]


def _serialise(r: BookAvailability) -> dict:
    return {
        "title": r.query.title,
        "author": r.query.author,
        "material_type": r.query.material_type,
        "brns": r.brns,
        "error": r.error,
        "any_available": r.any_available,
        "total_available": r.total_available,
        "libraries": [
            {
                "library": s.library,
                "available": s.available,
                "total": s.total,
                "label": s.label,
                "copies": [
                    {
                        "status": c.status,
                        "transaction": c.transaction,
                        "media": c.media,
                        "call_number": c.call_number,
                    }
                    for c in s.copies
                ],
            }
            for s in r.library_summaries()
        ],
    }


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("📚 NLB Library Availability")
st.caption(
    f"Checking **{len(TITLES)}** title(s).  "
    "Results are cached for 30 minutes to stay under the API rate limit."
)

col_check, col_clear = st.columns([3, 1])
with col_check:
    run = st.button("🔍 Check availability", use_container_width=True, type="primary")
with col_clear:
    if st.button("🗑 Clear cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

client = _make_client()
if client is None:
    st.stop()

if run or st.session_state.get("results"):

    if run:
        # Invalidate old session results so a fresh fetch is triggered
        st.session_state.pop("results", None)

    if "results" not in st.session_state:
        api_key = os.getenv("NLB_API_KEY", "")
        app_code = os.getenv("NLB_APP_CODE", "")
        titles_repr = str([(q.title, q.author, q.material_type) for q in TITLES])
        with st.spinner("Querying NLB API — this may take a minute for long lists …"):
            st.session_state["results"] = _fetch_results(
                (api_key, app_code), titles_repr
            )

    results: list[dict] = st.session_state["results"]

    # ── summary banner ────────────────────────────────────────────────────────
    n_available = sum(1 for r in results if r["any_available"])
    n_total = len(results)
    st.markdown(
        f"### {n_available}/{n_total} titles have copies available right now"
    )
    st.divider()

    # ── per-book cards ────────────────────────────────────────────────────────
    for r in results:
        icon = "✅" if r["any_available"] else "❌"
        header = f"{icon} **{r['title']}** — *{r['author']}*"
        fmt_tag = f" `{r['material_type']}`" if r["material_type"] else ""
        with st.expander(header + fmt_tag, expanded=r["any_available"]):
            if r["error"]:
                st.warning(r["error"])
                continue

            if not r["libraries"]:
                st.info("No copy records returned.")
                continue

            st.markdown(
                f"**{r['total_available']} / {sum(lib['total'] for lib in r['libraries'])} "
                f"copies available** across {len(r['libraries'])} branch(es)"
            )

            # Filter toggle
            show_all = st.toggle(
                "Show all branches (including unavailable)",
                key=f"toggle_{r['title']}",
                value=False,
            )

            for lib in r["libraries"]:
                if not show_all and lib["available"] == 0:
                    continue
                avail_colour = "green" if lib["available"] > 0 else "red"
                st.markdown(
                    f"- :{avail_colour}[**{lib['library']}**] — {lib['label']}"
                )

            if r["brns"]:
                brn_links = ", ".join(
                    f"[{brn}](https://catalogue.nlb.gov.sg/cgi-bin/spydus.exe/"
                    f"ENQ/EXPNOS/BIBENQ?BRN={brn})"
                    for brn in r["brns"]
                )
                st.caption(f"BRN(s): {brn_links}")
