"""Fuzzy-match suggestions for "did you mean?" on not-found errors.

VistA's namespaces are heterogeneous: routines / RPCs / options are
upper-case (`PRCA45PT`), package directories are mixed-case
(`Accounts Receivable`), file numbers are numeric (`200`). The matcher
folds case internally so a user querying `prca45pt` or
`accounts receivabl` still finds the canonical name, then returns the
candidate in its original case.

Backed by difflib (stdlib) so vista-cli stays at zero new runtime deps.
"""

from __future__ import annotations

import difflib


def did_you_mean(
    query: str,
    candidates: list[str],
    *,
    n: int = 3,
    cutoff: float = 0.6,
) -> list[str]:
    """Return up to `n` close matches from `candidates`, ranked best-first.

    Comparison is case-insensitive; the returned strings preserve the
    case from `candidates` so they print canonically.

    `cutoff` is the SequenceMatcher ratio threshold (0.0 = anything,
    1.0 = exact). 0.6 is difflib's own default — loose enough to catch
    single-character typos and transpositions, strict enough that a
    completely different name returns nothing.

    Empty query or empty candidates → empty list.
    """
    if not query or not candidates:
        return []
    # Build a lower-case → original-case map so we can match on lower
    # and project results back. If two candidates collide on lower-case,
    # the first one in input order wins.
    folded: dict[str, str] = {}
    for c in candidates:
        if c and c.lower() not in folded:
            folded[c.lower()] = c
    matches = difflib.get_close_matches(
        query.lower(), list(folded.keys()), n=n, cutoff=cutoff
    )
    return [folded[m] for m in matches]
