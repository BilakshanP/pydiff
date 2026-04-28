"""Tests for pydiff.

These use the bundled ``demo_repo/`` as a fixture. Tests that mutate the
working tree restore it in ``tearDown`` / ``__exit__`` so repeated runs stay
green.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

from pydiff import cli, gitio, html_render


REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_REPO = str(REPO_ROOT / "demo_repo")


class SmokeTests(unittest.TestCase):
    def test_module_exposes_entrypoints(self) -> None:
        self.assertTrue(callable(cli.main))
        self.assertTrue(callable(html_render.render))


class CliDefaults(unittest.TestCase):
    def test_empty_args_defaults(self) -> None:
        ns = cli.build_parser().parse_args([])
        self.assertEqual(ns.base, "HEAD")
        self.assertEqual(ns.targets, ["."])
        self.assertEqual(ns.dir, ".")
        self.assertEqual(ns.out, "diff_report.html")
        self.assertEqual(ns.context, 5)
        self.assertFalse(ns.full)
        self.assertFalse(ns.untracked)

    def test_untracked_flag(self) -> None:
        ns = cli.build_parser().parse_args(["--untracked"])
        self.assertTrue(ns.untracked)

    def test_explicit_base_and_targets(self) -> None:
        ns = cli.build_parser().parse_args(
            ["-b", "main", "-t", "feature-a", "feature-b", "."]
        )
        self.assertEqual(ns.base, "main")
        self.assertEqual(ns.targets, ["feature-a", "feature-b", "."])


class DemoRepoCleanState(unittest.TestCase):
    """Fail fast if the demo repo has pre-existing worktree changes."""

    def test_demo_repo_is_clean(self) -> None:
        out = subprocess.run(
            ["git", "-C", DEMO_REPO, "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(
            out,
            "",
            "demo_repo has uncommitted changes; tests assume a clean fixture",
        )


class WorktreeSentinel(unittest.TestCase):
    def test_is_worktree_true_for_dot(self) -> None:
        self.assertTrue(gitio.is_worktree("."))

    def test_is_worktree_false_for_refs(self) -> None:
        for ref in ("HEAD", "main", "HEAD~1", "v1.0.0", "./foo", ""):
            self.assertFalse(gitio.is_worktree(ref), ref)

    def test_ref_kind_has_worktree(self) -> None:
        self.assertIn("worktree", gitio.REF_KIND)
        label, color = gitio.REF_KIND["worktree"]
        self.assertEqual(label, "worktree")
        self.assertTrue(color.startswith("#"))

    def test_ref_chip_renders_worktree_color(self) -> None:
        chip = gitio.ref_chip("worktree")
        self.assertIn("worktree", chip)
        self.assertIn(gitio.REF_KIND["worktree"][1], chip)


class Classify(unittest.TestCase):
    def test_classify_worktree_sentinel(self) -> None:
        self.assertEqual(gitio.classify(DEMO_REPO, "."), "worktree")

    def test_classify_head_is_commit(self) -> None:
        self.assertEqual(gitio.classify(DEMO_REPO, "HEAD"), "commit")

    def test_classify_head_expr_is_commit(self) -> None:
        self.assertEqual(gitio.classify(DEMO_REPO, "HEAD~1"), "commit")


class Resolve(unittest.TestCase):
    def test_resolve_worktree_short_circuits(self) -> None:
        # Passing a non-existent repo path proves we never called git.
        self.assertEqual(gitio.resolve("/does/not/exist", "."), ".")

    def test_resolve_head_returns_sha(self) -> None:
        sha = gitio.resolve(DEMO_REPO, "HEAD")
        self.assertRegex(sha, r"^[0-9a-f]{40}$")


class WorktreeMutation:
    """Temporarily mutate a file in demo_repo; restore on exit.

    We snapshot the file's bytes and overwrite after the test. If the original
    didn't exist (pure untracked), we remove the file on exit.
    """

    def __init__(self, relpath: str, new_content: bytes) -> None:
        self.path = os.path.join(DEMO_REPO, relpath)
        self.new_content = new_content
        self._original: bytes | None = None
        self._existed: bool = False

    def __enter__(self) -> "WorktreeMutation":
        self._existed = os.path.exists(self.path)
        if self._existed:
            with open(self.path, "rb") as f:
                self._original = f.read()
        with open(self.path, "wb") as f:
            f.write(self.new_content)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._existed and self._original is not None:
            with open(self.path, "wb") as f:
                f.write(self._original)
        elif os.path.exists(self.path):
            os.remove(self.path)


class ListChangesWorktree(unittest.TestCase):
    def test_no_changes_when_clean(self) -> None:
        self.assertEqual(gitio.list_changes(DEMO_REPO, "HEAD", "."), [])

    def test_modified_file_detected(self) -> None:
        with WorktreeMutation("src/app.py", b"# totally different content\n"):
            changes = gitio.list_changes(DEMO_REPO, "HEAD", ".")
        self.assertEqual(len(changes), 1)
        status, old, new = changes[0]
        self.assertEqual(status, "M")
        self.assertEqual(old, "src/app.py")
        self.assertEqual(new, "src/app.py")

    def test_ref_vs_ref_still_works(self) -> None:
        # Sanity: non-worktree path unchanged.
        changes = gitio.list_changes(DEMO_REPO, "HEAD~1", "HEAD")
        self.assertTrue(len(changes) >= 1)


class ListUntracked(unittest.TestCase):
    def test_clean_repo_has_no_untracked(self) -> None:
        self.assertEqual(gitio.list_untracked(DEMO_REPO), [])

    def test_new_file_is_listed(self) -> None:
        with WorktreeMutation("new_untracked.txt", b"hello untracked\n"):
            paths = gitio.list_untracked(DEMO_REPO)
        self.assertIn("new_untracked.txt", paths)


class ShowWorktree(unittest.TestCase):
    def test_reads_tracked_file_from_disk(self) -> None:
        lines = gitio.show(DEMO_REPO, ".", "src/app.py")
        # Existing first line of demo_repo/src/app.py starts with a comment.
        self.assertTrue(lines)
        self.assertTrue(lines[0].startswith("#"))

    def test_reads_mutated_content(self) -> None:
        with WorktreeMutation("src/app.py", b"hello\nworld\n"):
            lines = gitio.show(DEMO_REPO, ".", "src/app.py")
        self.assertEqual(lines, ["hello\n", "world\n"])

    def test_missing_file_returns_sentinel(self) -> None:
        lines = gitio.show(DEMO_REPO, ".", "no/such/file.txt")
        self.assertEqual(lines, ["<File not found>\n"])

    def test_binary_file_detected(self) -> None:
        with WorktreeMutation("src/app.py", b"\x00\x01\x02binary"):
            lines = gitio.show(DEMO_REPO, ".", "src/app.py")
        self.assertEqual(lines, ["<Binary or non-UTF-8 file>\n"])

    def test_ref_path_still_works(self) -> None:
        # Sanity: ref-based show unchanged.
        lines = gitio.show(DEMO_REPO, "HEAD", "src/app.py")
        self.assertTrue(lines)


class AssetsLoaded(unittest.TestCase):
    """Ensure the packaged CSS/JS assets were loaded at import time."""

    def test_css_wrapped_in_style_tag(self) -> None:
        self.assertTrue(html_render.CSS_STYLES.startswith("<style>"))
        self.assertTrue(html_render.CSS_STYLES.endswith("</style>"))
        self.assertIn("table.diff", html_render.CSS_STYLES)

    def test_js_wrapped_in_script_tag(self) -> None:
        self.assertTrue(html_render.JS_SCRIPT.startswith("<script>"))
        self.assertTrue(html_render.JS_SCRIPT.endswith("</script>"))
        self.assertIn("setView", html_render.JS_SCRIPT)


if __name__ == "__main__":
    unittest.main()
