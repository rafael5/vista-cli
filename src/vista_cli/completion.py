"""Click shell-completion callbacks for entity-name arguments.

Each completer reads from the configured stores at completion time
(via env vars) and returns prefix matches up to `_LIMIT`. Completers
must never raise — Click invokes them on every <TAB>, and a crash
would degrade the shell experience. Anything unexpected returns `[]`
and the user gets no completions for that press.

Wire by passing the function as `shell_complete=` on the relevant
`@click.argument`. The ctx/param parameters are required by Click's
signature even when unused.
"""

from __future__ import annotations

from typing import Any

from vista_cli.canonical import all_packages
from vista_cli.config import Config
from vista_cli.stores.code_view import make_code_view
from vista_cli.stores.data_model import DataModelStore

_LIMIT = 50


def _safe_view():
    """Build a CodeModelView; return None if data is unreachable."""
    try:
        cfg = Config.from_env()
        return make_code_view(
            code_model_dir=cfg.code_model_dir,
            cache_db=cfg.cache_db,
            doc_db=cfg.doc_db,
        )
    except Exception:  # noqa: BLE001
        return None


def complete_routine(ctx: Any, param: Any, incomplete: str) -> list[str]:
    view = _safe_view()
    if view is None:
        return []
    try:
        inc = incomplete.upper()
        return sorted(
            r.get("routine_name", "")
            for r in view.all_routines()
            if r.get("routine_name", "").startswith(inc)
        )[:_LIMIT]
    except Exception:  # noqa: BLE001
        return []


def complete_package(ctx: Any, param: Any, incomplete: str) -> list[str]:
    inc = incomplete.lower()
    out: set[str] = set()
    try:
        for p in all_packages():
            for v in (p.directory, p.ns, p.app_code):
                if v and v.lower().startswith(inc):
                    out.add(v)
        view = _safe_view()
        if view is not None:
            for r in view.all_routines():
                pkg = r.get("package", "")
                if pkg and pkg.lower().startswith(inc):
                    out.add(pkg)
    except Exception:  # noqa: BLE001
        return []
    return sorted(out)[:_LIMIT]


def complete_rpc(ctx: Any, param: Any, incomplete: str) -> list[str]:
    view = _safe_view()
    if view is None:
        return []
    try:
        inc = incomplete.upper()
        return sorted(
            r.get("name", "")
            for r in view.all_rpcs()
            if r.get("name", "").startswith(inc)
        )[:_LIMIT]
    except Exception:  # noqa: BLE001
        return []


def complete_option(ctx: Any, param: Any, incomplete: str) -> list[str]:
    view = _safe_view()
    if view is None:
        return []
    try:
        inc = incomplete.upper()
        return sorted(
            o.get("name", "")
            for o in view.all_options()
            if o.get("name", "").startswith(inc)
        )[:_LIMIT]
    except Exception:  # noqa: BLE001
        return []


def complete_file(ctx: Any, param: Any, incomplete: str) -> list[str]:
    try:
        cfg = Config.from_env()
        dms = DataModelStore(cfg.data_model_dir)
        return sorted(
            f.get("file_number", "")
            for f in dms.all_files()
            if f.get("file_number", "").startswith(incomplete)
        )[:_LIMIT]
    except Exception:  # noqa: BLE001
        return []
