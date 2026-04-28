"""Markdown rendering of joined routine information."""

from __future__ import annotations

from typing import Any

from vista_cli.canonical import resolve_package


def render_routine(info: dict[str, Any]) -> str:
    """Render a routine info dict as markdown.

    Expected keys (all may be empty/None):
        routine_name, package, source_path, line_count,
        in_degree, out_degree, rpc_count, option_count,
        version_line,
        callees: list of dicts (callee_routine, callee_tag, kind, ref_count)
        callers: list of dicts (caller_name, caller_package, ref_count, callee_tag)
        globals: list of dicts (global_name, ref_count)
        xindex: list of dicts (line_text, tag_offset, error_text)
        rpcs: list of dicts (name, tag)
        options: list of dicts (name, tag)
        docs: list of dicts (title, doc_type, rel_path, patch_id)
    """
    lines: list[str] = []
    name = info.get("routine_name", "?")
    pkg = info.get("package", "?")
    pkg_id = resolve_package(pkg) if pkg else None
    ns = pkg_id.ns if pkg_id else "?"

    lines.append(f"# {name}  [{pkg}]")
    lines.append("")
    bits = []
    if info.get("line_count"):
        bits.append(f"{info['line_count']} lines")
    bits.append(f"in={info.get('in_degree', 0)}")
    bits.append(f"out={info.get('out_degree', 0)}")
    if info.get("rpc_count"):
        bits.append(f"RPC×{info['rpc_count']}")
    if info.get("option_count"):
        bits.append(f"OPT×{info['option_count']}")
    lines.append(" · ".join(bits))
    lines.append("")
    if info.get("source_path"):
        lines.append(f"**source:** `{info['source_path']}`")
    if info.get("version_line"):
        lines.append(f"**header:** `{info['version_line'].strip()}`")
    lines.append(f"**namespace:** `{ns}`")
    lines.append("")

    # ── code facts ─────────────────────────────────────────────────
    lines.append("## Code facts")
    lines.append("")

    callees = info.get("callees") or []
    if callees:
        lines.append("**Callees**")
        lines.append("")
        for c in callees[:15]:
            tag = c.get("callee_tag", "")
            rtn = c.get("callee_routine", "")
            ref = f"{tag}^{rtn}" if tag else f"^{rtn}"
            kind = c.get("kind", "")
            cnt = c.get("ref_count", "0")
            lines.append(f"- `{ref}` ({kind}) ×{cnt}")
        lines.append("")

    callers = info.get("callers") or []
    if callers:
        lines.append("**Callers**")
        lines.append("")
        for c in callers[:15]:
            cn = c.get("caller_name", "")
            cp = c.get("caller_package", "")
            cnt = c.get("ref_count", "0")
            lines.append(f"- `{cn}` [{cp}] ×{cnt}")
        lines.append("")

    globs = info.get("globals") or []
    if globs:
        lines.append("**Globals**")
        lines.append("")
        for g in globs[:15]:
            lines.append(f"- `^{g.get('global_name', '')}` ×{g.get('ref_count', '0')}")
        lines.append("")

    xindex = info.get("xindex") or []
    if xindex:
        lines.append("**XINDEX findings**")
        lines.append("")
        for x in xindex[:15]:
            line = x.get("line_text", "")
            tag = x.get("tag_offset", "")
            txt = x.get("error_text", "")
            lines.append(f"- line {line} [{tag}] — {txt}")
        lines.append("")

    rpcs = info.get("rpcs") or []
    if rpcs:
        lines.append("**RPCs exposed**")
        lines.append("")
        for r in rpcs:
            lines.append(f"- `{r.get('name', '')}` (tag `{r.get('tag', '')}`)")
        lines.append("")

    options = info.get("options") or []
    if options:
        lines.append("**Options exposed**")
        lines.append("")
        for o in options:
            lines.append(f"- `{o.get('name', '')}` (tag `{o.get('tag', '')}`)")
        lines.append("")

    # ── documentation ──────────────────────────────────────────────
    docs = info.get("docs") or []
    if docs:
        lines.append("## Documentation")
        lines.append("")
        for d in docs:
            title = d.get("title", "?")
            dt = d.get("doc_type", "?")
            patch = d.get("patch_id") or ""
            patch_s = f" (patch {patch})" if patch else ""
            rel = d.get("rel_path", "")
            lines.append(f"- **[{dt}]** {title}{patch_s}")
            if rel:
                lines.append(f"  `{rel}`")
        lines.append("")
    else:
        lines.append("## Documentation")
        lines.append("")
        lines.append("_No VDL documentation references this routine._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
