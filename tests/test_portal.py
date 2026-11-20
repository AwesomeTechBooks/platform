#!/usr/bin/env python3
"""Tests for the portal generator and its catalog data."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

PLATFORM = Path(__file__).resolve().parents[1]
WORKSPACE = PLATFORM.parent
SCRIPT = PLATFORM / "tools" / "build-portal.py"
CATALOG = WORKSPACE / "AwesomeTechBooks.github.io" / "catalog.json"
README = WORKSPACE / "AwesomeTechBooks.github.io" / "README.md"
PROFILE = WORKSPACE / ".github" / "profile" / "README.md"
SNAPSHOT = WORKSPACE / "_migration" / "atb-snapshot" / "index.html"


def load_generator():
    spec = importlib.util.spec_from_file_location("build_portal", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


build_portal = load_generator()


def run(*args: str, cwd: Path = WORKSPACE) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=cwd,
        text=True,
        capture_output=True,
    )


def normalize(source: str) -> str:
    """Ignore formatting/indentation differences between two HTML files."""
    source = re.sub(r"\s+", " ", source)
    source = re.sub(r">\s+<", "><", source)
    return source.strip()


def replace_old_links(source: str) -> str:
    source = source.replace(
        "https://github.com/winterYANGWT/Awesome-Tech-Books/tree/main/books/",
        "https://github.com/AwesomeTechBooks/",
    )
    source = source.replace(
        "https://github.com/winterYANGWT/Awesome-Tech-Books/tree/main/rust-book-zh",
        "https://github.com/AwesomeTechBooks/rust-book-zh",
    )
    source = source.replace(
        "https://github.com/winterYANGWT/Awesome-Tech-Books",
        "https://github.com/AwesomeTechBooks",
    )
    source = source.replace(
        "https://winteryangwt.github.io/Awesome-Tech-Books/",
        "https://awesometechbooks.github.io/",
    )
    # Deliberate changes made when the site moved to the organisation:
    # the footer no longer talks about one repository's root LICENSE, and the
    # old CUDA edition stays on the archived site instead of moving.
    source = source.replace(
        "各书的许可证见对应目录中的 LICENSE 文件；仓库根目录的 LICENSE 仅适用于本站点自身。",
        "各书的许可证见各自仓库的 LICENSE 文件；本首页和共用的网页底层使用 MIT 许可证。",
    )
    source = source.replace(">GitHub 仓库<", ">GitHub 组织<")
    source = source.replace(
        'href="cuda-programming-zh-legacy/"',
        'href="https://winteryangwt.github.io/Awesome-Tech-Books/cuda-programming-zh-legacy/"',
    )
    return source


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value is not None:
                    self.hrefs.append(value)


class PortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in (SCRIPT, CATALOG, README, PROFILE):
            if not path.exists():
                raise unittest.SkipTest(f"workspace file missing: {path}")
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory(prefix="atb-portal-test-")
        cls.tmpdir = Path(cls.tmp.name)
        cls.out = cls.tmpdir / "site"
        result = run(CATALOG, "--out", cls.out)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        cls.generated = (cls.out / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_homepage_matches_snapshot(self):
        # One-off migration check against the old hand-written homepage; the
        # snapshot only exists in the local migration workspace.
        if not SNAPSHOT.exists():
            self.skipTest(f"migration snapshot not present: {SNAPSHOT}")
        expected = normalize(replace_old_links(SNAPSHOT.read_text(encoding="utf-8")))
        actual = normalize(self.generated)
        self.assertEqual(expected, actual)

    def test_homepage_skips_books_marked_off_homepage(self):
        # A book with "homepage": false gets no card but stays in the README table.
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        hidden = dict(catalog["books"][0], id="hidden-book-zh", title="不上首页的书", homepage=False)
        catalog["books"].append(hidden)
        path = self.tmpdir / "hidden-catalog.json"
        path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
        readme = self.tmpdir / "hidden-README.md"
        shutil.copy(README, readme)
        out = self.tmpdir / "hidden-site"
        result = run(path, "--out", out, "--readme", readme)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("<h2>不上首页的书</h2>", (out / "index.html").read_text(encoding="utf-8"))
        self.assertIn("hidden-book-zh", readme.read_text(encoding="utf-8"))

    def test_internal_links_point_at_catalog_ids(self):
        parser = Links()
        parser.feed(self.generated)
        ids = {book["id"] for book in self.catalog["books"]}
        internal = []
        for href in parser.hrefs:
            if re.match(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|#)", href):
                continue
            path = href.split("#", 1)[0].split("?", 1)[0]
            first = path.split("/", 1)[0]
            internal.append(href)
            self.assertIn(first, ids, f"internal link {href!r} is not under a catalog id")
            self.assertTrue(path.startswith(first + "/"), href)
        self.assertTrue(internal)
        expected = sum(
            1
            for book in self.catalog["books"]
            if book.get("homepage", True)
            for action in book.get("actions", [])
            if not re.match(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|#)", action["href"])
        )
        self.assertEqual(len(internal), expected, internal)

    def test_generated_tables_use_the_new_addresses(self):
        readme = README.read_text(encoding="utf-8")
        profile = PROFILE.read_text(encoding="utf-8")
        for text in (readme, profile):
            self.assertIn("<!-- catalog:start -->", text)
            self.assertIn("<!-- catalog:end -->", text)
            self.assertNotIn("winterYANGWT", text)
            self.assertNotIn("winteryangwt", text)
            self.assertIn("https://awesometechbooks.github.io/", text)
            for book in self.catalog["books"]:
                self.assertIn(
                    f"[`AwesomeTechBooks/{book['id']}`]"
                    f"(https://github.com/AwesomeTechBooks/{book['id']})",
                    text,
                )

    def test_check_accepts_fresh_tables_and_rejects_stale_ones(self):
        readme_copy = self.tmpdir / "README.md"
        profile_copy = self.tmpdir / "profile.md"
        shutil.copyfile(README, readme_copy)
        shutil.copyfile(PROFILE, profile_copy)

        result = run(
            CATALOG,
            "--readme", readme_copy,
            "--profile", profile_copy,
            "--check",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        original = readme_copy.read_text(encoding="utf-8")
        stale = original.replace("| MIT / Apache-2.0 |", "| MIT |", 1)
        self.assertNotEqual(original, stale)
        readme_copy.write_text(stale, encoding="utf-8")
        result = run(CATALOG, "--readme", readme_copy, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(readme_copy.read_text(encoding="utf-8"), stale,
                         "--check must not write")

        readme_copy.write_text(original, encoding="utf-8")
        result = run(
            CATALOG,
            "--readme", readme_copy,
            "--profile", profile_copy,
            "--check",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        profile_stale = profile_copy.read_text(encoding="utf-8").replace(
            "| MIT / Apache-2.0 |", "| MIT |", 1
        )
        profile_copy.write_text(profile_stale, encoding="utf-8")
        result = run(CATALOG, "--profile", profile_copy, "--check")
        self.assertEqual(result.returncode, 1)

    def test_descriptions_escape_text_and_keep_safe_inline_tags(self):
        mini = {
            "site": {
                "title": "T & <test>",
                "description": "d",
                "header": {"title": "H", "tagline": "t"},
                "footer": {"note": "n", "repo_url": "https://example.test"},
                "home_url": "https://example.test/",
                "repo_url": "https://example.test",
            },
            "books": [{
                "id": "one",
                "title": "<标题 & \"x\">",
                "original": "a & b",
                "desc": "<em>斜体</em> & <code>a &lt; b</code> <script>alert(1)</script>",
                "accent": "#123456",
                "badge": "<B>",
                "tags": ["<tag>"],
                "actions": [{"label": "<go>", "href": "one/?a=1&b=2", "primary": True}],
                "readme": {"summary": "s", "license": "l"},
            }],
        }
        catalog_path = self.tmpdir / "mini.json"
        catalog_path.write_text(json.dumps(mini, ensure_ascii=False), encoding="utf-8")
        out = self.tmpdir / "mini-site"
        result = run(catalog_path, "--out", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        page = (out / "index.html").read_text(encoding="utf-8")

        self.assertIn("<title>T &amp; &lt;test&gt;</title>", page)
        self.assertIn("<em>斜体</em>", page)
        self.assertIn("<code>a &lt; b</code>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;B&gt;", page)
        self.assertIn("&lt;go&gt;", page)
        self.assertIn('href="one/?a=1&amp;b=2"', page)

    def test_table_markdown_escapes_pipes(self):
        self.assertEqual(build_portal.md_cell("a | b\nc"), "a \\| b c")


if __name__ == "__main__":
    unittest.main()
