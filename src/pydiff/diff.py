#!/usr/bin/env python3
import argparse
import difflib
import html
import os
import re
import subprocess
import sys
from typing import cast

CSS_STYLES = """
<style>
    body { font-family: system-ui, sans-serif; margin: 40px; color: #24292f; }
    h1, h2, h3 { border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }
    a { color: #0969da; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .summary-card { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 16px; margin-bottom: 24px; }
    .summary-card > h3:first-child, .summary-card > h4:first-child { margin-top: 0; }
    .summary-card h4 { margin-top: 16px; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; color: #fff; margin-right: 8px; }
    .badge-add { background-color: #2da44e; }
    .badge-mod { background-color: #bf8700; }
    .badge-del { background-color: #cf222e; }
    .badge-ren { background-color: #8250df; }
    .toc-list { list-style-type: none; padding-left: 0; }
    .toc-list li { margin-bottom: 4px; font-family: monospace; font-size: 14px; }
    .file-container { margin-top: 30px; }
    .target-index { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px 16px; margin-bottom: 24px; }
    .target-index h3 { margin: 0 0 8px 0; border: none; padding: 0; font-size: 14px; }
    .target-index ol { margin: 0; padding-left: 20px; font-family: monospace; font-size: 13px; }
    .target-section { margin-top: 20px; border: 1px solid #d0d7de; border-radius: 6px; }
    .target-section > summary { list-style: none; cursor: pointer; padding: 10px 16px; background: #f6f8fa; border-radius: 6px; display: flex; align-items: center; gap: 8px; }
    .target-section > summary > h2 { margin-right: auto; }
    .target-section[open] > summary { border-bottom: 1px solid #d0d7de; border-radius: 6px 6px 0 0; }
    .target-section > summary::-webkit-details-marker { display: none; }
    .target-section > summary::before { content: '▸'; display: inline-block; color: #57606a; transition: transform 0.15s; }
    .target-section[open] > summary::before { transform: rotate(90deg); }
    .target-section > summary h2 { display: inline; border: none; padding: 0; font-size: 18px; }
    .target-body { padding: 16px; }
    .target-nav { display: flex; gap: 6px; }
    .nav-fab { position: fixed; right: 20px; bottom: 20px; display: flex; flex-direction: column; gap: 6px; z-index: 100; }
    .nav-fab button { width: 36px; height: 36px; border-radius: 18px; border: 1px solid #d0d7de; background: #fff; font-size: 16px; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .nav-fab button:hover { background: #f6f8fa; }
    .nav-fab button:disabled { opacity: 0.4; cursor: not-allowed; }

    /* Fullscreen overlay */
    .fullscreen { position: fixed !important; inset: 0 !important; z-index: 1000 !important; background: #fff; overflow: auto; margin: 0 !important; border-radius: 0 !important; border: none !important; padding: 20px !important; }
    .fullscreen .pane { max-height: calc(100vh - 200px); }
    body.has-fullscreen { overflow: hidden; }
    .file-header { display: flex; justify-content: space-between; align-items: center; background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 8px 16px; font-family: monospace; font-size: 14px; cursor: pointer; list-style: none; gap: 8px; }
    .file-header::-webkit-details-marker { display: none; }
    .file-container[open] .file-header { border-bottom-left-radius: 0; border-bottom-right-radius: 0; border-bottom: none; }
    .file-content { border: 1px solid #d0d7de; border-top: none; border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; padding: 0; background-color: #ffffff; }
    .status-chip { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; color: #fff; margin-right: 8px; letter-spacing: 0.02em; }
    .hdr-controls { display: inline-flex; gap: 6px; align-items: center; }
    .ref-chip { display: inline-block; padding: 1px 7px; border-radius: 10px; font-size: 10px; font-weight: 600; color: #fff; margin-left: 6px; vertical-align: middle; letter-spacing: 0.02em; text-transform: uppercase; }
    /* Controls bar (sits between header and split) */
    .controls { display: flex; gap: 6px; padding: 6px 10px; background: #f6f8fa; border-bottom: 1px solid #d0d7de; align-items: center; }
    .hdr-btn { font-size: 11px; padding: 2px 8px; border-radius: 10px; background: #eaeef2; color: #57606a; border: 1px solid #d0d7de; cursor: pointer; font-family: inherit; }
    .hdr-btn:hover { background: #dde2e8; }
    .hdr-btn.active { background: #ddeeff; color: #0969da; border-color: #0969da; }
    .btn-icon { border: none !important; background: transparent; padding: 4px 8px; font-size: 22px; line-height: 1; color: #57606a; }
    .btn-icon:hover { background: #eaeef2; color: #24292f; }

    /* Split view container.
       Default (sync on): outer box scrolls vertically; panes only scroll horizontally. Native, smooth.
       Sync off (.nosync): each pane scrolls independently in both axes. */
    .split { display: flex; align-items: stretch; max-height: 70vh; overflow-y: auto; overflow-x: hidden; position: relative; }
    .split.nosync { overflow: visible; max-height: none; }
    .pane { flex: 1 1 50%; min-width: 0; }
    .pane-inner { overflow-x: auto; width: 100%; }
    .split.nosync .pane { max-height: 70vh; overflow-y: auto; }
    .split.nosync .pane-inner { overflow-x: auto; }
    .pane.hidden { display: none; }
    .pane.solo { flex: 1 1 100%; }
    .handle { width: 6px; background: #d0d7de; cursor: col-resize; flex: 0 0 6px; position: sticky; top: 0; align-self: stretch; }
    .split.nosync .handle { position: static; }
    .handle:hover, .handle.dragging { background: #0969da; }
    .handle.hidden { display: none; }

    table.diff {
        font-family: ui-monospace, monospace;
        font-size: 13px;
        line-height: 1.45;
        border-collapse: collapse;
        width: 100%;
        min-width: max-content;
        tab-size: 4;
        -moz-tab-size: 4;
    }
    table.diff th { background: #eaeef2; color: #57606a; padding: 4px 10px; text-align: left; position: sticky; top: 0; z-index: 1; border-bottom: 1px solid #d0d7de; }
    table.diff td.diff_header { background: #eaeef2; border-right: 1px solid #d0d7de; padding: 2px 10px; color: #57606a; text-align: right; width: 48px; min-width: 48px; vertical-align: top; user-select: none; }
    table.diff td { padding: 2px 10px; white-space: pre; vertical-align: top; }
    table.diff tbody tr:hover td { background-color: #f6f8fa; }
    table.diff tbody tr:hover td.diff_add { background-color: #9be8ae; }
    table.diff tbody tr:hover td.diff_chg { background-color: #a2ccff; }
    table.diff tbody tr:hover td.diff_sub { background-color: #ffa0a0; }
    /* Hunk separator row: a single cell spanning the row */
    table.diff tr td[colspan]:only-child { background: #f6f8fa; color: #6e7781; text-align: center; }
    td.diff_add { background-color: #abf2bc; }
    td.diff_chg { background-color: #b3d9ff; }
    td.diff_sub { background-color: #ffb3b3; }
    span.diff_add { background-color: #2da44e; color: #fff; border-radius: 3px; padding: 1px; font-weight: bold; }
    span.diff_sub { background-color: #cf222e; color: #fff; border-radius: 3px; padding: 1px; font-weight: bold; }
    span.diff_chg { background-color: #0969da; color: #fff; border-radius: 3px; padding: 1px; font-weight: bold; }
</style>
"""

JS_SCRIPT = """
<script>
(function() {
    function setView(split, mode) {
        var L = split.querySelector('.pane.left');
        var R = split.querySelector('.pane.right');
        var H = split.querySelector('.handle');
        L.classList.remove('hidden','solo'); R.classList.remove('hidden','solo'); H.classList.remove('hidden');
        if (mode === 'left')  { R.classList.add('hidden'); H.classList.add('hidden'); L.classList.add('solo'); }
        if (mode === 'right') { L.classList.add('hidden'); H.classList.add('hidden'); R.classList.add('solo'); }
        if (mode === 'both') { L.style.flexBasis = '50%'; R.style.flexBasis = '50%'; }
        split.dataset.view = mode;
        var fc = split.closest('.file-content');
        fc.querySelectorAll('[data-view]').forEach(function(b) {
            b.classList.toggle('active', b.dataset.view === mode);
        });
    }

    document.querySelectorAll('.file-content').forEach(function(fc) {
        var split = fc.querySelector('.split:not(.single)');
        if (!split) return;
        var L = split.querySelector('.pane.left');
        var R = split.querySelector('.pane.right');
        var H = split.querySelector('.handle');

        fc.querySelectorAll('[data-view]').forEach(function(b) {
            b.addEventListener('click', function(e) {
                e.preventDefault();
                setView(split, b.dataset.view);
            });
        });
        var syncBtn = fc.querySelector('[data-sync-toggle]');
        if (syncBtn) {
            syncBtn.addEventListener('click', function(e) {
                e.preventDefault();
                var wasSync = !split.classList.contains('nosync');
                var y = wasSync ? split.scrollTop : (L.scrollTop || R.scrollTop);
                split.classList.toggle('nosync');
                var on = !split.classList.contains('nosync');
                syncBtn.classList.toggle('active', on);
                syncBtn.textContent = on ? 'Sync: on' : 'Sync: off';
                // Transfer scroll position to the newly-active scroller(s).
                requestAnimationFrame(function() {
                    if (on) {
                        split.scrollTop = y;
                    } else {
                        L.scrollTop = y;
                        R.scrollTop = y;
                    }
                });
            });
        }

        // Drag handle
        var dragging = false;
        H.addEventListener('mousedown', function(e) {
            if (split.dataset.view !== 'both') return;
            dragging = true;
            H.classList.add('dragging');
            e.preventDefault();
        });
        document.addEventListener('mousemove', function(e) {
            if (!dragging) return;
            var rect = split.getBoundingClientRect();
            var pct = ((e.clientX - rect.left) / rect.width) * 100;
            pct = Math.max(10, Math.min(90, pct));
            L.style.flexBasis = pct + '%';
            R.style.flexBasis = (100 - pct) + '%';
        });
        document.addEventListener('mouseup', function() {
            if (dragging) { dragging = false; H.classList.remove('dragging'); }
        });
    });

    // Target prev/next navigation
    var targets = Array.prototype.slice.call(document.querySelectorAll('.target-section'));
    if (targets.length > 1) {
        var prev = document.getElementById('nav-prev');
        var next = document.getElementById('nav-next');
        function currentIndex() {
            var y = window.scrollY + 80;
            var idx = 0;
            for (var i = 0; i < targets.length; i++) {
                if (targets[i].offsetTop <= y) idx = i;
            }
            return idx;
        }
        function jump(delta) {
            var i = currentIndex() + delta;
            if (i < 0) i = 0;
            if (i >= targets.length) i = targets.length - 1;
            targets[i].scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        if (prev) prev.addEventListener('click', function() { jump(-1); });
        if (next) next.addEventListener('click', function() { jump(1); });
    }

    // Fullscreen toggle (target-section or file-container)
    var fsCurrent = null;
    function exitFullscreen() {
        if (!fsCurrent) return;
        fsCurrent.classList.remove('fullscreen');
        var btn = fsCurrent.querySelector(':scope > summary [data-expand]');
        if (btn) btn.textContent = '⛶';
        fsCurrent = null;
        document.body.classList.remove('has-fullscreen');
    }
    document.querySelectorAll('[data-expand]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault(); e.stopPropagation();
            var container = btn.closest('.file-container') || btn.closest('.target-section');
            if (!container) return;
            if (fsCurrent === container) { exitFullscreen(); return; }
            if (fsCurrent) exitFullscreen();
            container.classList.add('fullscreen');
            if (!container.open) container.open = true;
            btn.textContent = '✕';
            fsCurrent = container;
            document.body.classList.add('has-fullscreen');
        });
    });
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') exitFullscreen();
    });
})();
</script>
"""

STATUS_STYLE: dict[str, tuple[str, str, str]] = {
    "A": ("Added", "#2da44e", "badge-add"),
    "M": ("Modified", "#bf8700", "badge-mod"),
    "D": ("Deleted", "#cf222e", "badge-del"),
    "R": ("Renamed", "#8250df", "badge-ren"),
}


def git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args], check=True, capture_output=True, text=True
    ).stdout


# Sentinel string passed as a target ref to mean "the current working tree"
# (staged + unstaged changes, tracked files only). Chosen as "." because it
# mirrors the usual "here / current" convention.
WORKTREE_SENTINEL = "."


def is_worktree(ref: str) -> bool:
    return ref == WORKTREE_SENTINEL


def resolve(repo: str, ref: str) -> str:
    if is_worktree(ref):
        return WORKTREE_SENTINEL
    try:
        return git(repo, "rev-parse", "--verify", ref).strip()
    except subprocess.CalledProcessError:
        sys.exit(f"Error: cannot resolve git ref '{ref}'")


REF_KIND: dict[str, tuple[str, str]] = {
    "branch": ("branch", "#2da44e"),
    "remote-branch": ("remote", "#0969da"),
    "tag": ("tag", "#bf8700"),
    "commit": ("commit", "#6e7781"),
    "worktree": ("worktree", "#fb8500"),
}


def classify(repo: str, ref: str) -> str:
    # Revision expressions and HEAD itself are conceptually "a commit", even
    # though git resolves them to the underlying branch ref.
    if is_worktree(ref):
        return "worktree"
    if ref == "HEAD" or any(c in ref for c in "~^@:"):
        return "commit"
    try:
        full = git(repo, "rev-parse", "--symbolic-full-name", ref).strip()
    except subprocess.CalledProcessError:
        full = ""
    if full.startswith("refs/heads/"):
        return "branch"
    if full.startswith("refs/remotes/"):
        return "remote-branch"
    if full.startswith("refs/tags/"):
        return "tag"
    return "commit"


def ref_chip(kind: str) -> str:
    label, color = REF_KIND[kind]
    return f"<span class='ref-chip' style='background:{color}'>{label}</span>"


def list_changes(repo: str, a: str, b: str) -> list[tuple[str, str, str]]:
    # Worktree target: omit second ref so git diffs against the working tree.
    if is_worktree(b):
        out = git(repo, "diff", "--name-status", "-M", "-z", a)
    else:
        out = git(repo, "diff", "--name-status", "-M", "-z", a, b)
    tokens = out.split("\0")
    _ = tokens.pop()
    changes: list[tuple[str, str, str]] = []
    i = 0
    while i < len(tokens):
        status = tokens[i][0]
        if status == "R":
            changes.append(("R", tokens[i + 1], tokens[i + 2]))
            i += 3
        else:
            changes.append((status, tokens[i + 1], tokens[i + 1]))
            i += 2
    return changes


def list_untracked(repo: str) -> list[str]:
    """Return paths of untracked files, honoring .gitignore."""
    out = git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    parts = out.split("\0")
    return [p for p in parts if p]


def show(repo: str, ref: str, path: str) -> list[str]:
    if is_worktree(ref):
        full = os.path.join(repo, path)
        try:
            with open(full, "rb") as f:
                raw = f.read()
        except FileNotFoundError:
            return ["<File not found>\n"]
        except OSError:
            return ["<Error reading file>\n"]
        if b"\0" in raw[:8000]:
            return ["<Binary or non-UTF-8 file>\n"]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return ["<Binary or non-UTF-8 file>\n"]
        return text.splitlines(keepends=True)
    try:
        text = git(repo, "show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return ["<Error reading blob>\n"]
    if "\0" in text[:8000]:
        return ["<Binary or non-UTF-8 file>\n"]
    return text.splitlines(keepends=True)


def anchor_id(ref_label: str, path: str) -> str:
    return "f-" + "".join(c if c.isalnum() else "-" for c in f"{ref_label}_{path}")


# Match one <tr>...</tr>; non-greedy, tolerant of attributes and newlines.
_TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S)
# Match a <td> or <th> cell with its content.
_CELL_RE = re.compile(r"<(t[dh])\b([^>]*)>(.*?)</\1>", re.S)


def split_diff_table(diff_html: str, from_desc: str, to_desc: str) -> tuple[str, str]:
    """Split HtmlDiff.make_table output into two independent tables (left, right).

    HtmlDiff emits 6 cells per row: [next, lineno, code] x 2. We drop the two
    'next' nav columns (they're intra-table navigation that breaks once we split)
    and keep [lineno, code] on each side.
    """
    left_rows: list[str] = []
    right_rows: list[str] = []
    for m in _TR_RE.finditer(diff_html):
        cells: list[tuple[str, str, str]] = _CELL_RE.findall(m.group(1))
        # Hunk separator: a single cell spanning the row
        if len(cells) == 1:
            tag, attrs, content = cells[0]
            row = f'<tr><{tag} colspan="2"{attrs}>{content}</{tag}></tr>'
            left_rows.append(row)
            right_rows.append(row)
            continue
        if len(cells) != 6:
            continue  # unknown row shape; skip

        # cells: [0]=L-next, [1]=L-lineno, [2]=L-code, [3]=R-next, [4]=R-lineno, [5]=R-code
        def mk(
            cell_lineno: tuple[str, str, str], cell_code: tuple[str, str, str]
        ) -> str:
            tag_l, attrs_l, content_l = cell_lineno
            tag_c, attrs_c, content_c = cell_code
            # Ensure empty code cells still occupy a full line height so rows align across panes.
            if not content_c.strip():
                content_c = "&nbsp;"
            return (
                f"<tr><{tag_l}{attrs_l}>{content_l}</{tag_l}>"
                f"<{tag_c}{attrs_c}>{content_c}</{tag_c}></tr>"
            )

        left_rows.append(mk(cells[1], cells[2]))
        right_rows.append(mk(cells[4], cells[5]))

    def build(rows: list[str], desc: str) -> str:
        return (
            f'<table class="diff"><thead><tr><th colspan="2">{desc}</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    return build(left_rows, from_desc), build(right_rows, to_desc)


def render_file_block(
    anchor: str,
    color: str,
    label: str,
    header: str,
    diff_html: str,
    from_desc: str,
    to_desc: str,
    status: str,
) -> str:
    left, right = split_diff_table(diff_html, from_desc, to_desc)
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Git-native directory/commit diff HTML report"
    )
    _ = p.add_argument(
        "-b",
        "--base",
        default="HEAD",
        help="Base git ref (branch, tag, or commit). Default: HEAD",
    )
    _ = p.add_argument(
        "-t",
        "--targets",
        nargs="+",
        default=["."],
        help="Target git refs. Use '.' for the current worktree (uncommitted changes). Default: .",
    )
    _ = p.add_argument(
        "-d", "--dir", default=".", help="Repo path (default: current dir)"
    )
    _ = p.add_argument("-o", "--out", default="diff_report.html", help="Output file")
    _ = p.add_argument(
        "-c",
        "--context",
        type=int,
        default=5,
        help="Context lines around changes (default: 5)",
    )
    _ = p.add_argument(
        "--full", action="store_true", help="Show full files instead of context-only"
    )
    _ = p.add_argument(
        "--untracked",
        action="store_true",
        help="Include untracked files as Added entries (only meaningful when target is '.')",
    )
    return p


def main() -> None:
    render(build_parser().parse_args())


if __name__ == "__main__":
    main()
