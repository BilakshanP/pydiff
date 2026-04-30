"""Command-line interface for pydiff."""

from __future__ import annotations

import argparse
import sys

from pydiff.html_render import render, render_walk


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
    _ = p.add_argument(
        "--walk",
        nargs=2,
        metavar=("FROM", "TO"),
        help="Walk mode: show per-commit diffs between two refs (inclusive)",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.walk:
        # Validate: --walk is incompatible with -b, -t, --untracked
        if args.base != "HEAD" or args.targets != ["."] or args.untracked:
            sys.exit("Error: --walk cannot be combined with -b, -t, or --untracked")
        render_walk(args)
    else:
        render(args)


if __name__ == "__main__":
    main()
