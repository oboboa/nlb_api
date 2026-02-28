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
from goodreads import available_shelves, parse_goodreads_csv, SHELF_LABELS, _ALL_SHELVES
from models import BookAvailability, BookQuery
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

# ── session state defaults ────────────────────────────────────────────────────
if "manual_titles" not in st.session_state:
    st.session_state["manual_titles"] = []   # list[BookQuery] added via the UI
if "results_list" not in st.session_state:
    st.session_state["results_list"] = []    # list[dict], newest-first
if "results_keys" not in st.session_state:
    st.session_state["results_keys"] = set() # set of (title_lower, author_lower) already fetched

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
def _fetch_results(_client_key: tuple, titles_repr: str, _titles: list[BookQuery]) -> list[dict]:
    """Fetch only the supplied titles and return serialised dicts."""
    api_key, app_code = _client_key
    client = NLBClient(api_key, app_code)

    status_placeholder = st.empty()
    log: list[str] = []

    def on_status(msg: str) -> None:
        log.append(msg)
        status_placeholder.markdown(
            "**Fetching\u2026**\n\n" + "\n\n".join(f"- {m}" for m in log[-5:])
        )

    results = fetch_all(_titles, client, on_status=on_status)
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


# ── Sidebar: Goodreads import ─────────────────────────────────────────────────

with st.sidebar:
    st.header("📥 Import from Goodreads")
    st.markdown(
        "Export your library from "
        "[Goodreads → Import and Export](https://www.goodreads.com/review/import), "
        "then upload the CSV here."
    )
    uploaded = st.file_uploader("Goodreads CSV export", type="csv", label_visibility="collapsed")

    imported_titles: list[BookQuery] = []
    if uploaded is not None:
        raw = uploaded.read()
        found_shelves = available_shelves(raw)
        shelf_options = found_shelves or _ALL_SHELVES
        shelf_labels = [SHELF_LABELS.get(s, s) for s in shelf_options]

        selected_labels = st.multiselect(
            "Shelves to include",
            options=shelf_labels,
            default=[SHELF_LABELS.get("to-read", shelf_labels[0])] if shelf_labels else [],
        )
        # Map labels back to raw shelf names
        label_to_shelf = {v: k for k, v in SHELF_LABELS.items()}
        selected_shelves = [label_to_shelf.get(lbl, lbl) for lbl in selected_labels]

        imported_titles = parse_goodreads_csv(raw, shelves=selected_shelves)
        st.success(f"{len(imported_titles)} book(s) loaded from Goodreads")

    st.divider()
    use_default = st.checkbox(
        f"Also include hardcoded titles.py list ({len(TITLES)} titles)",
        value=uploaded is None,
        disabled=uploaded is None,
    )

    st.divider()
    st.subheader("➕ Add a title")
    with st.form("add_title_form", clear_on_submit=True):
        new_title = st.text_input("Title")
        new_author = st.text_input("Author")
        submitted = st.form_submit_button("Add", use_container_width=True)
        if submitted:
            t, a = new_title.strip(), new_author.strip()
            if t and a:
                st.session_state["manual_titles"].append(BookQuery(title=t, author=a))
            else:
                st.warning("Please fill in both Title and Author.")

    if st.session_state["manual_titles"]:
        if st.button("🗑 Clear manually added titles", use_container_width=True):
            st.session_state["manual_titles"] = []
            st.rerun()

# ── Build candidate list from all sources ─────────────────────────────────────
candidates: list[BookQuery] = []
seen_candidates: set[tuple[str, str]] = set()

for source in (
    imported_titles,
    st.session_state["manual_titles"],
    TITLES if (use_default or not imported_titles) else [],
):
    for q in source:
        key = (q.title.lower(), q.author.lower())
        if key not in seen_candidates:
            seen_candidates.add(key)
            candidates.append(q)

# ── UI ────────────────────────────────────────────────────────────────────────

st.title("📚 NLB Library Availability")

# ── Title selection table ─────────────────────────────────────────────────────
with st.expander(
    f"📋 Titles to check ({len(candidates)} total)",
    expanded=not st.session_state["results_list"],
):
    st.caption("Tick the checkboxes to include or exclude individual titles.")

    if not candidates:
        st.info("No titles yet — add some via the sidebar.")
        st.stop()

    # Key changes whenever the candidate list changes so the editor resets to
    # all-selected when a new import or manual entry is added.
    _editor_key = f"title_editor_{hash(str([(q.title, q.author) for q in candidates]))}"
    candidate_rows = [{"✓": True, "Title": q.title, "Author": q.author} for q in candidates]

    edited_rows: list[dict] = st.data_editor(
        candidate_rows,
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=True, width="small"),
            "Title": st.column_config.TextColumn("Title", disabled=True),
            "Author": st.column_config.TextColumn("Author", disabled=True),
        },
        hide_index=True,
        use_container_width=True,
        key=_editor_key,
    )

    active_titles: list[BookQuery] = [
        candidates[i] for i, row in enumerate(edited_rows) if row["✓"]
    ]
    already_fetched = sum(
        1 for q in active_titles
        if (q.title.lower(), q.author.lower()) in st.session_state["results_keys"]
    )
    new_count = len(active_titles) - already_fetched
    note = f"**{len(active_titles)}/{len(candidates)}** selected"
    if already_fetched:
        note += f" • {already_fetched} already cached, {new_count} new"
    st.caption(note)

col_check, col_clear = st.columns([3, 1])
with col_check:
    run = st.button(
        "🔍 Check availability",
        use_container_width=True,
        type="primary",
        disabled=len(active_titles) == 0,
    )
with col_clear:
    if st.button("🗑 Clear all results", use_container_width=True):
        st.session_state["results_list"] = []
        st.session_state["results_keys"] = set()
        st.cache_data.clear()
        st.rerun()

client = _make_client()
if client is None:
    st.stop()

if run:
    # Only fetch titles not already in the cache
    titles_to_fetch = [
        q for q in active_titles
        if (q.title.lower(), q.author.lower()) not in st.session_state["results_keys"]
    ]
    if not titles_to_fetch:
        st.info("All selected titles are already in the results below.")
    else:
        api_key = os.getenv("NLB_API_KEY", "")
        app_code = os.getenv("NLB_APP_CODE", "")
        n = len(titles_to_fetch)
        # Each book uses ~2 API calls; 15/min limit → warn if it'll take a while
        est_mins = round(n * 2 / 15 * 1.2, 1)
        spinner_msg = (
            f"Querying NLB API for {n} new title(s)…"
            + (f" (est. ~{est_mins} min)" if est_mins >= 1 else "")
        )
        titles_repr = str([(q.title, q.author, q.material_type) for q in titles_to_fetch])
        with st.spinner(spinner_msg):
            new_results = _fetch_results((api_key, app_code), titles_repr, titles_to_fetch)
        # Prepend newest results
        st.session_state["results_list"] = new_results + st.session_state["results_list"]
        for r in new_results:
            st.session_state["results_keys"].add((r["title"].lower(), r["author"].lower()))
        st.rerun()

results: list[dict] = st.session_state["results_list"]

# ── Results ─────────────────────────────────────────────────────────────────
if not results:
    st.info("Select titles above and click **Check availability** to begin.")
else:
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
