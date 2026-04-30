# pydiff

A small CLI that generates a self-contained HTML report comparing git refs — branches, tags, or commits — in any local repository.

## Features

- Compare any two git refs (branch, tag, commit SHA, `HEAD~N`, `origin/main`, …).
- Compare a ref against the **current worktree** (uncommitted changes) using `.` as the target.
- Compare one base against multiple targets in a single report.
- **Walk mode**: step through per-commit diffs between two refs with `← →` navigation.
- Detects **Added / Modified / Deleted / Renamed / Untracked** files.
- Labels each ref in the report as **branch**, **remote**, **tag**, **commit**, or **worktree**.
- Side-by-side diffs with inline add/remove/change highlighting.
- **Tree-structured TOC** grouping files by directory (collapsible folders, single-file dirs inlined).
- Per-file controls: **Both / Left only / Right only** view, **Sync scroll** toggle (preserves scroll position across toggles), draggable resize handle.
- Per-file and per-target **fullscreen** toggle (Esc to exit), with **← → file navigation** in fullscreen.
- Per-target collapsible sections; prev / next target navigation when multiple targets are present.
- Context-only view by default; optional full-file view.
- **Dark mode** — automatic via `prefers-color-scheme`.
- Binary and non-UTF-8 files are detected and skipped.
- Zero third-party dependencies — pure Python 3 standard library.

## Requirements

- Python 3.14+
- `git` on `PATH`

## Install

From git:
```
pip install git+https://github.com/USER/pydiff.git
```

For development:
```
uv sync --dev
```

## Usage

```
pydiff [-b <base-ref>] [-t <target-ref> [<target-ref> ...]] [options]
```

With no flags, compares `HEAD` against the current worktree (uncommitted changes).

### Flags

| Flag | Default | Meaning |
|---|---|---|
| `-b`, `--base` | `HEAD` | Base git ref |
| `-t`, `--targets` | `.` | One or more target refs; `.` means the current worktree |
| `-d`, `--dir` | `.` | Path to the git repo |
| `-o`, `--out` | `diff_report.html` | Output HTML path |
| `-c`, `--context` | `5` | Context lines around each change |
| `--full` | off | Show entire file instead of context-only |
| `--untracked` | off | When a worktree target is present, also include untracked files as Untracked |
| `--walk` | off | Walk mode: `--walk FROM TO` steps through per-commit diffs between two refs |

## Examples

Preview uncommitted changes against `HEAD` (default behaviour):
```
pydiff
```

Preview uncommitted changes and include untracked files:
```
pydiff --untracked
```

Compare the worktree against a specific base:
```
pydiff -b main
```

Compare two branches:
```
pydiff -b main -t feature/new-api
```

Compare the latest commit against its parent:
```
pydiff -b HEAD~1 -t HEAD
```

Compare two tags:
```
pydiff -b v1.0.0 -t v1.1.0
```

Compare one base against multiple targets in one report:
```
pydiff -b main -t feature/a feature/b feature/c -o review.html
```

Run against a repo elsewhere on disk:
```
pydiff -d ~/code/myrepo -b main -t dev
```

Show full files with wider context:
```
pydiff -b main -t dev --full -c 10
```

Walk through per-commit diffs between two refs:
```
pydiff --walk HEAD~5 HEAD
```

Walk between two branches:
```
pydiff -d ~/code/myrepo --walk main feature/new-api -o walk.html
```

## Output

The generated HTML contains:

- A header with the repo path and the base ref.
- A **targets index** (shown only when multiple targets are present).
- Per target: a **collapsible section** containing a summary with Added / Modified / Deleted / Renamed counts, a table of contents linking to each changed file, and a side-by-side diff per file.
- Floating **↑ / ↓ navigation** between target sections (multi-target reports only).

Each file diff supports:
- Toggling between side-by-side view, left-only, and right-only.
- Toggling sync scroll between panes.
- Dragging the central handle to resize left/right split (clamped 10–90%).
- Fullscreen toggle on the file (or on the whole target section).

Pure adds/deletes render with only the relevant side shown.

## How it works

1. Resolves each ref via `git rev-parse --verify` (except `.`, which is a literal sentinel for the worktree).
2. Enumerates changed files and their statuses via `git diff --name-status -M -z <base> <target>`; when the target is the worktree, the second ref is dropped so git compares against the working tree. With `--untracked`, also merges in paths from `git ls-files --others --exclude-standard` as Untracked.
3. For each change, reads both sides via `git show <ref>:<path>` for git refs, or directly from disk for worktree paths, and feeds the line lists into `difflib.HtmlDiff.make_table`.
4. Post-processes the result into two independent tables (left / right panes) and emits a single self-contained HTML file.

## Notes and limitations

- Heavy edits combined with a rename may fall below git's similarity threshold and appear as delete + add.
- Binary or non-UTF-8 files are shown as `<Binary or non-UTF-8 file>` rather than diffed.
- Very large files will produce large HTML; use `-c` to reduce context or avoid `--full` on huge files.
- Works on bare repos, since all git access goes through `git -C <dir>`.
