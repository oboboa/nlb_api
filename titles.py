"""Edit this file to control which titles the app checks.

Each BookQuery takes:
    title          – full or partial title (case-insensitive substring match)
    author         – author in any order ("Andy Weir" or "Weir, Andy" both work)
    material_type  – optional NLB code to restrict format:
                         "bks"  → print books
                         "dvd"  → DVDs
                         "aud"  → audiobooks / CDs
                         None   → any physical item (default)
    exclude_sources – tuple of sources to skip (default: ("overdrive",) = skip e-books)

Examples
--------
    BookQuery("Project Hail Mary", "Andy Weir")
    BookQuery("Dune", "Frank Herbert", material_type="bks")
    BookQuery("Planet Earth", "David Attenborough", material_type="dvd")
"""

from models import BookQuery

TITLES: list[BookQuery] = [
    BookQuery("Project Hail Mary", "Andy Weir"),
    BookQuery("Remarkably Bright Creatures", "Shelby Van Pelt"),
    BookQuery("The Midnight Library", "Matt Haig"),
    BookQuery("Atomic Habits", "James Clear"),
    # ── add your own titles below ──────────────────────────────────────────
]
