"""Cache-aware code-model lookup view.

`CodeModelView` wraps a `CodeModelStore` and an optional `CacheStore`.
When a fresh cache is present, lookups for routine rows, calls, globals,
and patches are answered from the cache (one SQLite query each).
Anything not mirrored in the cache (xindex, rpcs, options, packages)
falls through to the TSV reader transparently — joined.py and the
command modules don't have to know which path is hot.

A stale cache is treated as no cache: serving wrong data is worse than
re-reading the TSVs.
"""

from __future__ import annotations

import logging
from pathlib import Path

from vista_cli.stores.cache import CacheStore
from vista_cli.stores.code_model import CodeModelStore

logger = logging.getLogger(__name__)


class CodeModelView:
    """Transparent cache-aware proxy in front of CodeModelStore.

    The methods explicitly defined here are the cache-mirrored ones.
    Everything else is delegated via `__getattr__` to the underlying
    CodeModelStore so the view exposes the full TSV API surface.
    """

    def __init__(self, cms: CodeModelStore, cache: CacheStore | None = None):
        self.cms = cms
        self.cache = cache

    # ── Cached lookups ────────────────────────────────────────────

    def routine(self, name: str):
        if self.cache is not None:
            row = self.cache.routine(name)
            if row is not None:
                return row
            return None
        return self.cms.routine(name)

    def routines_by_package(self, pkg: str):
        if self.cache is not None:
            return self.cache.routines_by_package(pkg)
        return self.cms.routines_by_package(pkg)

    def all_routines(self):
        if self.cache is not None:
            return self.cache.all_routines()
        return self.cms.all_routines()

    def callees(self, routine: str):
        if self.cache is not None:
            return self.cache.callees(routine)
        return self.cms.callees(routine)

    def callers(self, routine: str):
        if self.cache is not None:
            return self.cache.callers(routine)
        return self.cms.callers(routine)

    def globals_for(self, routine: str):
        if self.cache is not None:
            return self.cache.globals_for(routine)
        return self.cms.globals_for(routine)

    def routines_using_global(self, global_name: str):
        if self.cache is not None:
            return self.cache.routines_using_global(global_name)
        return self.cms.routines_using_global(global_name)

    def patches_for_routine(self, name: str):
        if self.cache is not None:
            patches = self.cache.patches_for_routine(name)
            if patches:
                return patches
            # Empty cache result for an existing routine could be real
            # (no patches) or could mean the cache mirror missed the
            # routine — fall through to the TSV path to be safe.
            if self.cache.routine(name) is not None:
                return patches
        return self.cms.patches_for_routine(name)

    def routines_for_patch(self, patch_id: str):
        if self.cache is not None:
            return self.cache.routines_for_patch(patch_id)
        return self.cms.routines_for_patch(patch_id)

    # ── Passthrough for everything else (xindex, rpcs, options, …) ─

    def __getattr__(self, name: str):
        # Only reached for names not defined on the view itself.
        return getattr(self.cms, name)


def make_code_view(
    *,
    code_model_dir: Path,
    cache_db: Path,
    doc_db: Path,
    allow_cache: bool = True,
) -> CodeModelView:
    """Construct a view, attaching a fresh cache when one is available.

    The cache is skipped when:
    - `allow_cache=False` (CLI `--no-cache` flag)
    - the cache file does not exist
    - the cache reports stale relative to its source TSVs / doc DB
    - opening the cache raises (corrupt file, permission, etc.)
    """
    cms = CodeModelStore(code_model_dir)
    if not allow_cache or not Path(cache_db).exists():
        return CodeModelView(cms, cache=None)

    try:
        cache = CacheStore(cache_db)
        stale, reasons = cache.is_stale(
            code_model_dir=code_model_dir, doc_db=doc_db
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("cache unreadable, falling back to TSV: %s", e)
        return CodeModelView(cms, cache=None)

    if stale:
        logger.info(
            "joined cache is stale (%s) — serving from TSVs; "
            "run `vista build-cache` to refresh",
            ", ".join(reasons),
        )
        cache.close()
        return CodeModelView(cms, cache=None)

    return CodeModelView(cms, cache=cache)
