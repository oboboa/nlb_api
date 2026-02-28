"""Parse a Goodreads CSV export into BookQuery objects.

How to get your Goodreads export
---------------------------------
1. Go to https://www.goodreads.com/review/import
2. Click **Export Library** (bottom of the page).
3. Download the generated CSV file.
4. Upload it in the app sidebar.

The CSV has columns including:
    Title, Author, Exclusive Shelf, Bookshelves, ...

``Author`` is in "Last, First" format, which BookQuery.author_matches() handles fine.
"""

from __future__ import annotations

import csv
import io
from typing import Sequence

from models import BookQuery

# Goodreads shelf names that map to human-readable labels
SHELF_LABELS: dict[str, str] = {
    "to-read": "To Read",
    "currently-reading": "Currently Reading",
    "read": "Read",
}

_ALL_SHELVES = list(SHELF_LABELS.keys())


def parse_goodreads_csv(
    file_content: str | bytes,
    shelves: Sequence[str] = ("to-read",),
) -> list[BookQuery]:
    """Convert a Goodreads CSV export to a list of BookQuery objects.

    Args:
        file_content: Raw bytes or string content of the exported CSV file.
        shelves:      Exclusive-shelf values to include, e.g. ("to-read",).
                      Pass ``_ALL_SHELVES`` to include every shelf.

    Returns:
        List of BookQuery objects ready to pass to ``fetch_all()``.
    """
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(file_content))

    wanted_shelves = {s.lower().strip() for s in shelves}
    queries: list[BookQuery] = []
    seen: set[tuple[str, str]] = set()  # deduplicate (title, author) pairs

    for row in reader:
        shelf = (row.get("Exclusive Shelf") or "").lower().strip()
        if shelf not in wanted_shelves:
            continue

        title = (row.get("Title") or "").strip()
        author = (row.get("Author") or "").strip()

        if not title or not author:
            continue

        key = (title.lower(), author.lower())
        if key in seen:
            continue
        seen.add(key)

        queries.append(BookQuery(title=title, author=author))

    return queries


def available_shelves(file_content: str | bytes) -> list[str]:
    """Return the distinct ``Exclusive Shelf`` values present in the CSV."""
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(file_content))
    shelves: set[str] = set()
    for row in reader:
        shelf = (row.get("Exclusive Shelf") or "").strip()
        if shelf:
            shelves.add(shelf)
    return sorted(shelves)
