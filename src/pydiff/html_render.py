"""HTML rendering for pydiff.

Post-processes ``difflib.HtmlDiff`` output into split-pane tables and assembles
the final self-contained HTML report. CSS and JS are loaded at import time
from the ``pydiff.assets`` package via :mod:`importlib.resources`.
"""

from __future__ import annotations

import argparse
import difflib
import html
import os
import re
import subprocess
from importlib.resources import files
from typing import cast

from pydiff.gitio import (
    classify,
    git,
    is_worktree,
    list_changes,
    list_untracked,
    ref_chip,
    resolve,
    show,
)


STATUS_STYLE: dict[str, tuple[str, str, str]] = {
    "A": ("Added", "#2da44e", "badge-add"),
    "M": ("Modified", "#bf8700", "badge-mod"),
    "D": ("Deleted", "#cf222e", "badge-del"),
    "R": ("Renamed", "#8250df", "badge-ren"),
}


_assets = files("pydiff.assets")
CSS_STYLES: str = (
    f"<style>\n{_assets.joinpath('styles.css').read_text(encoding='utf-8')}</style>"
)
JS_SCRIPT: str = (
    f"<script>\n{_assets.joinpath('script.js').read_text(encoding='utf-8')}</script>"
)


def anchor_id(ref_label: str, path: str) -> str:
    return "f-" + "".join(c if c.isalnum() else "-" for c in f"{ref_label}_{path}")


# Match one <tr>...</tr>; non-greedy, tolerant of attributes and newlines.
_TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S)
# Match a <td> or <th> cell with its content.
_CELL_RE = re.compile(r"<(t[dh])\b([^>]*)>(.*?)</\1>", re.S)


def split_diff_table(
    diff_html: str, from_desc: str, to_desc: str, max_lineno: int = 1
) -> tuple[str, str]:
    """Split HtmlDiff.make_table output into two independent tables (left, right).

    HtmlDiff emits 6 cells per row: [next, lineno, code] x 2. We split the row
    in half but keep the nav column (f/n/t jump links) on each side. IDs and
    href targets are rewritten with a per-pane suffix so left-pane and
    right-pane anchors don't collide.
    """
    # HtmlDiff puts a __top id on the outer <table>; grab that N so we can
    # reattach the id to each pane's new table for the 't' links.
    top_m = re.search(r'id="(difflib_chg_to\d+__top)"', diff_html)
    top_id = top_m.group(1) if top_m else ""

    left_rows: list[str] = []
    right_rows: list[str] = []
    prev_from_line = 0
    prev_to_line = 0

    def rewrite_ids(cell_attrs: str, cell_content: str, suffix: str) -> tuple[str, str]:
        # Rewrite any id="difflib_chg_..." on the cell and href="#difflib_chg_..."
        # inside its content so left/right nav targets stay scoped to their pane.
        new_attrs = re.sub(
            r'(id=")(difflib_chg_[^"]+)(")',
            lambda m: f"{m.group(1)}{m.group(2)}{suffix}{m.group(3)}",
            cell_attrs,
        )
        new_content = re.sub(
            r'(href="#)(difflib_chg_[^"]+)(")',
            lambda m: f"{m.group(1)}{m.group(2)}{suffix}{m.group(3)}",
            cell_content,
        )
        return new_attrs, new_content

    for m in _TR_RE.finditer(diff_html):
        cells: list[tuple[str, str, str]] = _CELL_RE.findall(m.group(1))
        # Hunk separator: a single cell spanning the row
        if len(cells) == 1:
            tag, attrs, content = cells[0]
            row = f'<tr><{tag} colspan="3"{attrs}>{content}</{tag}></tr>'
            left_rows.append(row)
            right_rows.append(row)
            continue
        if len(cells) != 6:
            continue  # unknown row shape; skip

        # cells: [0]=L-next, [1]=L-lineno, [2]=L-code, [3]=R-next, [4]=R-lineno, [5]=R-code
        # Detect hunk boundaries: a gap in line numbers on either side means
        # context was skipped. Tag the row so CSS can draw a separator line.
        row_class = ""
        from_num_m = re.search(r">(\d+)<", f">{cells[1][2]}<")
        to_num_m = re.search(r">(\d+)<", f">{cells[4][2]}<")
        cur_from = int(from_num_m.group(1)) if from_num_m else 0
        cur_to = int(to_num_m.group(1)) if to_num_m else 0
        if prev_from_line and cur_from > prev_from_line + 1:
            row_class = " class='hunk-boundary'"
        elif prev_to_line and cur_to > prev_to_line + 1:
            row_class = " class='hunk-boundary'"
        if cur_from:
            prev_from_line = cur_from
        if cur_to:
            prev_to_line = cur_to

        def mk(
            cell_nav: tuple[str, str, str],
            cell_lineno: tuple[str, str, str],
            cell_code: tuple[str, str, str],
            suffix: str,
        ) -> str:
            tag_n, attrs_n, content_n = cell_nav
            attrs_n, content_n = rewrite_ids(attrs_n, content_n, suffix)
            tag_l, attrs_l, content_l = cell_lineno
            tag_c, attrs_c, content_c = cell_code
            # Ensure empty code cells still occupy a full line height so rows align across panes.
            if not content_c.strip():
                content_c = "&nbsp;"
            return (
                f"<tr{row_class}><{tag_n}{attrs_n}>{content_n}</{tag_n}>"
                f"<{tag_l}{attrs_l}>{content_l}</{tag_l}>"
                f"<{tag_c}{attrs_c}>{content_c}</{tag_c}></tr>"
            )

        # Left pane keeps original nav cell (has ids + links), suffix "_l".
        left_rows.append(mk(cells[0], cells[1], cells[2], "_l"))
        # Right pane builds a nav cell using cells[0]'s id-bearing attrs and
        # cells[3]'s link content, so the right pane has its own
        # independently-addressable set of anchors.
        _, l_attrs, _ = cells[0]
        tag_r, _, content_r = cells[3]
        right_nav_cell = (tag_r, l_attrs, content_r)
        right_rows.append(mk(right_nav_cell, cells[4], cells[5], "_r"))

    def build(rows: list[str], desc: str, suffix: str) -> str:
        tid = f' id="{top_id}{suffix}"' if top_id else ""
        digits = max(len(str(max_lineno)), 2)
        style = f' style="--lineno-width: calc({digits}ch + 20px)"'
        return (
            f'<table class="diff"{tid}{style}><thead><tr><th colspan="3">{desc}</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    return build(left_rows, from_desc, "_l"), build(right_rows, to_desc, "_r")


def render_file_block(
    anchor: str,
    color: str,
    label: str,
    header: str,
    diff_html: str,
    from_desc: str,
    to_desc: str,
    status: str,
    max_lineno: int,
) -> str:
    left, right = split_diff_table(diff_html, from_desc, to_desc, max_lineno)
    summary = (
        f"<summary class='file-header' id='{anchor}' style='border-top: 3px solid {color};'>"
        f"<span><span class='status-chip' style='background:{color}'>{label}</span>"
        f"<strong>{header}</strong></span>"
        f"<span class='hdr-controls'>"
        f"<button class='hdr-btn btn-icon' data-expand title='Fullscreen' onclick='event.stopPropagation();'>⛶</button>"
        f"<a class='hdr-btn' href='#' onclick='event.stopPropagation();'>&#8593; Top</a>"
        f"</span></summary>"
    )
    # Single-pane modes: no controls, no handle, no JS interaction needed.
    if status == "A":
        body = f"<div class='file-content'><div class='split single'><div class='pane solo'><div class='pane-inner'>{right}</div></div></div></div>"
    elif status == "D":
        body = f"<div class='file-content'><div class='split single'><div class='pane solo'><div class='pane-inner'>{left}</div></div></div></div>"
    else:
        controls = (
            "<div class='controls'>"
            "<button class='hdr-btn active' data-view='both'>Both</button>"
            "<button class='hdr-btn' data-view='left'>Left only</button>"
            "<button class='hdr-btn' data-view='right'>Right only</button>"
            "<button class='hdr-btn active' data-sync-toggle>Sync: on</button>"
            "</div>"
        )
        body = (
            f"<div class='file-content'>{controls}"
            f"<div class='split' data-view='both'>"
            f"<div class='pane left'><div class='pane-inner'>{left}</div></div>"
            f"<div class='handle'></div>"
            f"<div class='pane right'><div class='pane-inner'>{right}</div></div>"
            f"</div></div>"
        )
    return f"<details class='file-container' open>{summary}{body}</details>"


def render(args: argparse.Namespace) -> None:
    repo = cast(str, args.dir)
    base = cast(str, args.base)
    targets = cast(list[str], args.targets)
    out_path = cast(str, args.out)
    context_lines = cast(int, args.context)
    full = cast(bool, args.full)
    untracked = cast(bool, args.untracked)

    base_sha = resolve(repo, base)
    base_short = (
        "worktree"
        if is_worktree(base_sha)
        else git(repo, "rev-parse", "--short", base_sha).strip()
    )

    base_kind = classify(repo, base)
    try:
        repo_path = git(repo, "rev-parse", "--show-toplevel").strip()
    except subprocess.CalledProcessError:
        repo_path = os.path.abspath(repo)
    repo_name = os.path.basename(repo_path) or repo_path
    try:
        origin = git(repo, "config", "--get", "remote.origin.url").strip()
    except subprocess.CalledProcessError:
        origin = ""
    repo_display = html.escape(repo_name)
    if origin:
        repo_display += (
            f" <span style='color:#6e7781'>(origin: {html.escape(origin)})</span>"
        )

    out = [
        f"<!DOCTYPE html><html><head><title>Git Diff: {html.escape(base)}</title>{CSS_STYLES}</head><body>"
    ]
    out.append("<h1>Git Diff Report</h1>")
    out.append(f"<p><strong>Repo:</strong> <code>{repo_display}</code><br>")
    out.append(
        f"<strong>Base:</strong> <code>{html.escape(base)} ({base_short})</code>{ref_chip(base_kind)}</p>"
    )

    differ = difflib.HtmlDiff()
    context_mode = not full

    # Resolve target shorts up front for the index
    target_info: list[tuple[str, str, str, str, str]] = []
    for t in targets:
        sha = resolve(repo, t)
        short = (
            "worktree"
            if is_worktree(sha)
            else git(repo, "rev-parse", "--short", sha).strip()
        )
        kind = classify(repo, t)
        target_info.append((t, sha, short, f"target-{len(target_info)}", kind))

    if len(target_info) > 1:
        out.append("<div class='target-index'><h3>Targets in this report</h3><ol>")
        for label, _, short, anchor, kind in target_info:
            out.append(
                f"<li><a href='#{anchor}'><code>{html.escape(label)} ({short})</code></a>{ref_chip(kind)}</li>"
            )
        out.append("</ol></div>")

    for target, target_sha, target_short, tgt_anchor, target_kind in target_info:
        changes = list_changes(repo, base_sha, target_sha)
        if untracked and is_worktree(target_sha):
            existing = {c[2] for c in changes}
            for p in list_untracked(repo):
                if p not in existing:
                    changes.append(("A", p, p))
        counts = {"A": 0, "M": 0, "D": 0, "R": 0}
        for status, _, _ in changes:
            counts[status] = counts.get(status, 0) + 1

        out.append(f"<details class='target-section' id='{tgt_anchor}' open>")
        out.append(
            f"<summary><h2>Target: <code>{html.escape(target)} ({target_short})</code>{ref_chip(target_kind)}</h2>"
            + "<span><button class='hdr-btn btn-icon' data-expand title='Fullscreen' onclick='event.stopPropagation();'>⛶</button></span></summary>"
        )
        out.append("<div class='target-body'>")

        out.append("<div class='summary-card'><h3>Summary</h3><div>")
        for code in ("A", "M", "D", "R"):
            label, _, cls = STATUS_STYLE[code]
            out.append(f"<span class='badge {cls}'>{counts[code]} {label}</span> ")
        out.append("</div>")

        if changes:
            out.append("<h4>Table of Contents</h4><ul class='toc-list'>")
            for status, old, new in changes:
                label, color, _ = STATUS_STYLE[status]
                display = html.escape(new if status != "R" else f"{old} → {new}")
                out.append(
                    f"<li><span style='color:{color}'>[{status}]</span> "
                    + f"<a href='#{anchor_id(target, new)}'>{display}</a></li>"
                )
            out.append("</ul>")
        else:
            out.append("<p><i>No changes.</i></p>")
        out.append("</div>")

        for status, old, new in changes:
            label, color, _ = STATUS_STYLE[status]
            from_lines = show(repo, base_sha, old) if status != "A" else []
            to_lines = show(repo, target_sha, new) if status != "D" else []
            from_desc = html.escape(f"{base}:{old}" if status != "A" else "Not present")
            to_desc = html.escape(f"{target}:{new}" if status != "D" else "Deleted")
            header = html.escape(f"{old} → {new}" if status == "R" else new)
            diff_html = differ.make_table(
                from_lines,
                to_lines,
                fromdesc=from_desc,
                todesc=to_desc,
                context=context_mode,
                numlines=context_lines,
            )
            out.append(
                render_file_block(
                    anchor_id(target, new),
                    color,
                    label,
                    header,
                    diff_html,
                    from_desc,
                    to_desc,
                    status,
                    max(len(from_lines), len(to_lines), 1),
                )
            )

        out.append("</div></details>")

    if len(target_info) > 1:
        out.append(
            "<div class='nav-fab'>"
            + "<button id='nav-prev' title='Previous target'>&#8593;</button>"
            + "<button id='nav-next' title='Next target'>&#8595;</button>"
            + "</div>"
        )

    out.append(JS_SCRIPT)
    out.append("</body></html>")
    with open(out_path, "w", encoding="utf-8") as f:
        _ = f.write("\n".join(out))
    print(f"✅ Report generated: {out_path}")
