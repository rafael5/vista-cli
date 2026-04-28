"""TSV rendering for list-of-dict results.

Matches vista-meta bake conventions: tab-separated, header on the
first line, no quoting. Tabs and newlines inside a value are
replaced with spaces — TSV has no escape mechanism.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence


def render_rows(rows: Sequence[dict[str, Any]], columns: Iterable[str]) -> str:
    """Render rows as TSV with the given column order.

    Missing keys render as empty strings; tabs/newlines inside values
    are replaced with single spaces.
    """
    cols = list(columns)
    out: list[str] = ["\t".join(cols)]
    for row in rows:
        out.append("\t".join(_clean(row.get(c, "")) for c in cols))
    return "\n".join(out) + "\n"


def _clean(value: Any) -> str:
    s = "" if value is None else str(value)
    return s.replace("\t", " ").replace("\n", " ").replace("\r", " ")
