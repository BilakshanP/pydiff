"""Git I/O and ref handling for pydiff.

All shell-out to ``git`` lives here, along with ref resolution, classification,
change enumeration, and blob fetching. The worktree sentinel ``"."`` is
special-cased so that worktree content is read from disk rather than via git.
"""

from __future__ import annotations

import os
import subprocess
import sys


# Sentinel string passed as a target ref to mean "the current working tree"
# (staged + unstaged changes, tracked files only). Chosen as "." because it
# mirrors the usual "here / current" convention.
WORKTREE_SENTINEL = "."


REF_KIND: dict[str, tuple[str, str]] = {
    "branch": ("branch", "#2da44e"),
    "remote-branch": ("remote", "#0969da"),
    "tag": ("tag", "#bf8700"),
    "commit": ("commit", "#6e7781"),
    "worktree": ("worktree", "#fb8500"),
}


def git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args], check=True, capture_output=True, text=True
    ).stdout


def is_worktree(ref: str) -> bool:
    return ref == WORKTREE_SENTINEL


def resolve(repo: str, ref: str) -> str:
    if is_worktree(ref):
        return WORKTREE_SENTINEL
    try:
        return git(repo, "rev-parse", "--verify", ref).strip()
    except subprocess.CalledProcessError:
        sys.exit(f"Error: cannot resolve git ref '{ref}'")


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
