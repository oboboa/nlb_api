"""Orchestration layer: given a list of BookQuery objects, return availability.

This module is intentionally side-effect-free (no I/O, no Streamlit, no CLI
printing) so it can be used from a script, a Streamlit app, or a test equally.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Optional

from models import BookAvailability, BookQuery, CopyInfo
from nlb_client import NLBClient

logger = logging.getLogger(__name__)


def _parse_copy(item: dict) -> CopyInfo:
    """Convert a raw API 'item' dict into a CopyInfo dataclass."""
    loc = item.get("location") or {}
    status = item.get("status") or {}
    txn = item.get("transactionStatus") or {}
    media = item.get("media") or {}
    return CopyInfo(
        location=loc.get("name") or "Unknown Location",
        status=status.get("name") or "Unknown Status",
        transaction=txn.get("name") or "Unknown Transaction Status",
        media=media.get("name") or "Unknown Media",
        call_number=item.get("callNumber") or "",
    )


def fetch_one(
    query: BookQuery,
    client: NLBClient,
    on_status: Optional[Callable[[str], None]] = None,
) -> BookAvailability:
    """Search for *query*, resolve BRNs, and collect all copy-level availability.

    Parameters
    ----------
    query:      The title/author (and optional format) to look up.
    client:     An authenticated NLBClient instance.
    on_status:  Optional callback(message: str) for progress reporting
                (used by both CLI and Streamlit).
    """

    def emit(msg: str) -> None:
        if on_status:
            on_status(msg)
        logger.info(msg)

    result = BookAvailability(query=query)

    # ---- step 1: find matching BRNs ----------------------------------------
    emit(f"Searching for {query} …")
    try:
        raw_titles = client.search_titles(
            title=query.title,
            author=query.author,
            material_type=query.material_type,
        )
    except Exception as exc:
        result.error = f"Search failed: {exc}"
        logger.error("Search failed for %s: %s", query, exc)
        return result

    matching_brns: set[int] = set()
    for t in raw_titles:
        t_title = (t.get("title") or "").strip()
        t_author = (t.get("author") or "").strip()
        t_source = (t.get("source") or "").strip()
        brn = t.get("brn")

        if brn is None:
            continue
        if not query.title_matches(t_title):
            continue
        if not query.author_matches(t_author):
            continue
        if not query.source_allowed(t_source):
            continue

        matching_brns.add(int(brn))

    result.brns = sorted(matching_brns)

    if not matching_brns:
        result.error = "No matching physical BRNs found."
        emit(f"  ↳ No matching BRNs for {query}")
        return result

    emit(f"  ↳ Found {len(matching_brns)} BRN(s): {sorted(matching_brns)}")

    # ---- step 2: get availability for each BRN ------------------------------
    copies: list[CopyInfo] = []
    for brn in sorted(matching_brns):
        emit(f"  Fetching availability for BRN {brn} …")
        try:
            items = client.get_availability(brn)
        except Exception as exc:
            logger.error("Availability fetch failed for BRN %s: %s", brn, exc)
            continue

        for item in items:
            copies.append(_parse_copy(item))

    result.copies = copies
    emit(f"  ↳ Retrieved {len(copies)} copy record(s) for {query}")
    return result


def fetch_all(
    queries: Iterable[BookQuery],
    client: NLBClient,
    on_status: Optional[Callable[[str], None]] = None,
) -> list[BookAvailability]:
    """Fetch availability for every query in *queries* sequentially.

    Rate limiting is managed inside NLBClient; this function just iterates.
    """
    results = []
    for query in queries:
        results.append(fetch_one(query, client, on_status=on_status))
    return results
