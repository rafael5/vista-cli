"""Cross-store joins between code-model and doc-model.

Per CLAUDE.md: stores are narrow (parse-and-return). This module
owns the actual joins so command modules stay declarative.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

from vista_cli.canonical import PackageId, resolve_package
from vista_cli.stores.code_model import CodeModelStore
from vista_cli.stores.data_model import DataModelStore
from vista_cli.stores.doc_model import DocModelStore

if TYPE_CHECKING:
    from vista_cli.stores.code_view import CodeModelView

    CodeLookup = Union[CodeModelStore, "CodeModelView"]
else:
    CodeLookup = CodeModelStore


def package_coverage(
    cms: CodeLookup,
    dms: DocModelStore,
    pkg_id: PackageId,
    *,
    latest_only: bool = True,
) -> dict[str, Any]:
    """Doc-coverage for a package: routine / RPC / option counts.

    Returns a structured dict — `documented` counts the entities that
    appear in at least one VDL document, `total` is the count from
    the code-model side. `undocumented_routines` lists those without
    any doc reference, sorted by in-degree desc.
    """
    routines = cms.routines_by_package(pkg_id.directory)
    documented_names = _documented_routine_names(
        dms, [r.get("routine_name", "") for r in routines], latest_only=latest_only
    )

    undocumented: list[dict[str, Any]] = []
    for r in routines:
        name = r.get("routine_name", "")
        if name not in documented_names:
            undocumented.append(
                {
                    "routine_name": name,
                    "in_degree": _i(r.get("in_degree", "0")),
                    "out_degree": _i(r.get("out_degree", "0")),
                    "line_count": _i(r.get("line_count", "0")),
                }
            )
    undocumented.sort(key=lambda r: -int(r["in_degree"]))

    rpcs = cms.rpcs_by_package(pkg_id.directory)
    rpcs_documented = sum(
        1 for r in rpcs if dms.docs_by_rpc(r.get("name", ""), latest_only=latest_only)
    )

    options = cms.options_by_package(pkg_id.directory)
    options_documented = sum(
        1
        for o in options
        if dms.docs_by_option(o.get("name", ""), latest_only=latest_only)
    )

    return {
        "package": pkg_id.directory,
        "namespace": pkg_id.ns,
        "app_code": pkg_id.app_code,
        "routines": {
            "total": len(routines),
            "documented": len(documented_names),
            "undocumented": undocumented,
        },
        "rpcs": {"total": len(rpcs), "documented": rpcs_documented},
        "options": {"total": len(options), "documented": options_documented},
    }


def _documented_routine_names(
    dms: DocModelStore, names: list[str], *, latest_only: bool
) -> set[str]:
    out: set[str] = set()
    for n in names:
        if not n:
            continue
        if dms.docs_by_routine(n, latest_only=latest_only):
            out.add(n)
    return out


def neighbors(
    cms: CodeLookup,
    dms_data: DataModelStore | None,
    routine: str,
    *,
    depth: int = 1,
    top_n: int = 5,
) -> dict[str, Any]:
    """Graph walk around a routine: callees, siblings, same-data routines."""
    callees = cms.callees(routine)[:top_n]

    deeper: list[dict[str, Any]] = []
    if depth >= 2:
        seen: set[str] = {routine, *(c.get("callee_routine", "") for c in callees)}
        for c in callees:
            child = c.get("callee_routine", "")
            for cc in cms.callees(child)[:top_n]:
                tgt = cc.get("callee_routine", "")
                if tgt and tgt not in seen:
                    seen.add(tgt)
                    deeper.append(
                        {
                            "via": child,
                            "callee_routine": tgt,
                            "callee_tag": cc.get("callee_tag", ""),
                            "ref_count": _i(cc.get("ref_count", "0")),
                        }
                    )
        deeper.sort(key=lambda r: -int(r["ref_count"]))
        deeper = deeper[:top_n]

    row = cms.routine(routine)
    package = (row or {}).get("package", "")
    siblings = _siblings_by_call_cohesion(cms, routine, package, top_n=top_n)

    same_data = _same_data_routines(cms, dms_data, routine, top_n=top_n)

    return {
        "root": routine,
        "package": package,
        "callees": [
            {
                "callee_routine": c.get("callee_routine", ""),
                "callee_tag": c.get("callee_tag", ""),
                "kind": c.get("kind", ""),
                "ref_count": _i(c.get("ref_count", "0")),
            }
            for c in callees
        ],
        "callees_depth_2": deeper,
        "siblings": siblings,
        "same_data": same_data,
    }


def _siblings_by_call_cohesion(
    cms: CodeLookup, routine: str, package: str, *, top_n: int
) -> list[dict[str, Any]]:
    """Same-package routines ranked by shared callees with `routine`."""
    if not package:
        return []
    my_callees = {c.get("callee_routine", "") for c in cms.callees(routine)}
    my_callees.discard("")
    out: list[dict[str, Any]] = []
    for sib in cms.routines_by_package(package):
        sib_name = sib.get("routine_name", "")
        if not sib_name or sib_name == routine:
            continue
        sib_callees = {c.get("callee_routine", "") for c in cms.callees(sib_name)}
        shared = my_callees & sib_callees
        if not shared:
            continue
        out.append(
            {
                "routine_name": sib_name,
                "shared_callee_count": len(shared),
                "package": sib.get("package", ""),
            }
        )
    out.sort(key=lambda r: -int(r["shared_callee_count"]))
    return out[:top_n]


def _same_data_routines(
    cms: CodeLookup,
    dms_data: DataModelStore | None,
    routine: str,
    *,
    top_n: int,
) -> list[dict[str, Any]]:
    """Other routines that touch the same globals as `routine`."""
    my_globals = {g.get("global_name", "") for g in cms.globals_for(routine)}
    my_globals.discard("")
    if not my_globals:
        return []

    counts: dict[str, dict[str, Any]] = {}
    for gname in my_globals:
        for r in cms.routines_using_global(gname):
            other = r.get("routine_name", "")
            if not other or other == routine:
                continue
            cur = counts.get(other)
            if cur is None:
                counts[other] = {
                    "routine_name": other,
                    "package": r.get("package", ""),
                    "ref_count": _i(r.get("ref_count", "0")),
                    "shared_globals": [gname],
                }
            else:
                cur["ref_count"] += _i(r.get("ref_count", "0"))
                if gname not in cur["shared_globals"]:
                    cur["shared_globals"].append(gname)

    out = sorted(counts.values(), key=lambda r: -int(r["ref_count"]))
    return out[:top_n]


def file_for_global(
    dms_data: DataModelStore, global_name: str
) -> dict[str, Any] | None:
    """Resolve a bare global name (e.g. `PRCA`) to its FileMan file via root match."""
    if not global_name:
        return None
    candidates = dms_data.files_by_global_root(f"^{global_name}")
    if candidates:
        return candidates[0]
    # Try a prefix scan — global may be `^DIC(4)`-style with subscript
    for f in dms_data.all_files():
        root = f.get("global_root", "")
        if not root:
            continue
        if root.startswith(f"^{global_name}(") or root == f"^{global_name}":
            return f
    return None


def routine_links(
    cms: CodeLookup,
    dms: DocModelStore | None,
    dms_data: DataModelStore | None,
    routine: str,
    *,
    latest_only: bool = True,
) -> dict[str, Any] | None:
    """Dense cross-reference summary for a routine."""
    row = cms.routine(routine)
    if row is None:
        return None
    pkg = row.get("package", "")
    pkg_id = resolve_package(pkg)

    files: list[dict[str, Any]] = []
    seen_files: set[str] = set()
    if dms_data is not None:
        for g in cms.globals_for(routine):
            gname = g.get("global_name", "")
            f = file_for_global(dms_data, gname)
            if f is None:
                continue
            num = f.get("file_number", "")
            if num in seen_files:
                continue
            seen_files.add(num)
            files.append(
                {
                    "file_number": num,
                    "file_name": f.get("file_name", ""),
                    "global": gname,
                    "ref_count": _i(g.get("ref_count", "0")),
                }
            )

    docs: list[dict[str, Any]] = []
    extra_section_count = 0
    if dms is not None:
        docs = dms.docs_by_routine(routine, latest_only=latest_only)
        extra_section_count = max(
            0, len(dms.sections_mentioning_routine(routine)) - len(docs)
        )

    return {
        "routine": routine,
        "package": {
            "directory": pkg,
            "namespace": pkg_id.ns if pkg_id else None,
            "app_code": pkg_id.app_code if pkg_id else None,
        },
        "options": [
            {"name": o.get("name", ""), "tag": o.get("tag", "")}
            for o in cms.options_in_routine(routine)
        ],
        "rpcs": [
            {"name": r.get("name", ""), "tag": r.get("tag", "")}
            for r in cms.rpcs_in_routine(routine)
        ],
        "files": files,
        "docs": docs,
        "extra_section_count": extra_section_count,
        "patches": cms.patches_for_routine(routine),
    }


def _i(value: Any) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0
