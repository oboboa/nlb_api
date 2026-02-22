"""Data models for the NLB availability checker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BookQuery:
    """Represents a book you want to look up.

    Args:
        title:          Full or partial title string to search for.
        author:         Author name (any order, e.g. "Andy Weir" or "Weir, Andy").
        material_type:  Optional NLB material-type code to restrict to a specific
                        format, e.g. "bks" (books), "dvd", "aud" (audiobooks).
                        Leave as None to match any non-digital source.
        exclude_sources: Sources to exclude (default: overdrive = digital loans).
    """

    title: str
    author: str
    material_type: Optional[str] = None          # e.g. "bks", "dvd", "aud"
    exclude_sources: tuple[str, ...] = ("overdrive",)

    # ------------------------------------------------------------------ helpers
    def title_matches(self, api_title: str) -> bool:
        """Case-insensitive substring match on title."""
        return self.title.lower() in api_title.lower()

    def author_matches(self, api_author: str) -> bool:
        """Match any 'significant' (len>3) word from the query author against the
        API-returned author string.  Handles "Last, First" inversion gracefully."""
        api_lower = api_author.lower()
        for word in self.author.lower().split():
            if len(word) > 3 and word in api_lower:
                return True
        return False

    def source_allowed(self, api_source: str) -> bool:
        return api_source.lower() not in {s.lower() for s in self.exclude_sources}

    def __str__(self) -> str:
        fmt = f" [{self.material_type}]" if self.material_type else ""
        return f'"{self.title}" by {self.author}{fmt}'


@dataclass
class CopyInfo:
    """Details for a single physical copy at a specific library location."""

    location: str
    status: str           # e.g. "On Loan", "Not on Loan"
    transaction: str      # e.g. "Available for loan", "In Reference Collection"
    media: str            # e.g. "Book", "DVD"
    call_number: str = ""

    @property
    def is_available(self) -> bool:
        combined = (self.transaction + " " + self.status).lower()
        return "available" in combined


@dataclass
class LibrarySummary:
    """Aggregated availability at one library branch."""

    library: str
    available: int
    total: int
    copies: list[CopyInfo] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.available > 0:
            return f"Available ({self.available}/{self.total})"
        return f"NOT available (0/{self.total})"


@dataclass
class BookAvailability:
    """Full availability result for one BookQuery."""

    query: BookQuery
    brns: list[int] = field(default_factory=list)
    copies: list[CopyInfo] = field(default_factory=list)
    error: Optional[str] = None

    # ------------------------------------------------------------------ helpers
    def library_summaries(self) -> list[LibrarySummary]:
        """Roll up copies per library branch, sorted by name."""
        from collections import defaultdict

        buckets: dict[str, list[CopyInfo]] = defaultdict(list)
        for copy in self.copies:
            buckets[copy.location].append(copy)

        summaries = []
        for lib, items in buckets.items():
            avail = sum(1 for c in items if c.is_available)
            summaries.append(LibrarySummary(lib, avail, len(items), items))

        return sorted(summaries, key=lambda s: s.library)

    @property
    def any_available(self) -> bool:
        return any(c.is_available for c in self.copies)

    @property
    def total_available(self) -> int:
        return sum(1 for c in self.copies if c.is_available)
