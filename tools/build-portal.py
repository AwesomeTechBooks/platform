#!/usr/bin/env python3
"""Build the AwesomeTechBooks portal homepage and refresh its book tables.

The catalog is data, the template is code: ``catalog.json`` lives in the
AwesomeTechBooks.github.io repository, while this script and
``platform/portal/index.html`` live in the platform repository.

Usage:
    python3 platform/tools/build-portal.py CATALOG --out OUT_DIR
    python3 platform/tools/build-portal.py CATALOG --readme README.md \
        --profile profile/README.md
    python3 platform/tools/build-portal.py CATALOG --readme README.md --check

``--check`` only compares the marked table(s) with what would be generated;
it never writes anything and exits 1 when a file is out of date.

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "portal" / "index.html"

CATALOG_START = "<!-- catalog:start -->"
CATALOG_END = "<!-- catalog:end -->"

DEFAULT_HOME_URL = "https://awesometechbooks.github.io/"
DEFAULT_REPO_URL = "https://github.com/AwesomeTechBooks"
DEFAULT_LANG = "zh-CN"

# Descriptions are plain text by default.  A small, explicit set of inline
# tags is kept so a description copied from the old hand-written page does not
# lose its emphasis; every text node and every attribute value is still
# escaped, and anything outside this list is shown literally.
ALLOWED_TAGS = {
    "a", "b", "br", "code", "em", "i", "kbd", "span", "strong", "sub", "sup",
}
ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "span": {"class"},
}
VOID_TAGS = {"br"}


def escape_text(value: object) -> str:
    """Escape text for an HTML text node."""
    return html.escape(str(value), quote=False)


def escape_attr(value: object) -> str:
    """Escape text for a quoted HTML attribute value."""
    return html.escape(str(value), quote=True)


class InlineHTML(HTMLParser):
    """Render a trusted-ish description, escaping text and unknown markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    @staticmethod
    def _safe_href(value: str) -> bool:
        value = value.strip()
        if not value:
            return False
        scheme = urlsplit(value).scheme.lower()
        return scheme in {"", "http", "https", "mailto"}

    def _start_tag(self, tag: str, attrs) -> str:
        pieces = [f"<{tag}"]
        allowed = ALLOWED_ATTRS.get(tag, set())
        for name, value in attrs:
            name = name.lower()
            if name not in allowed or value is None:
                continue
            if name == "href" and not self._safe_href(value):
                continue
            pieces.append(f' {name}="{escape_attr(value)}"')
        pieces.append(">")
        return "".join(pieces)

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.parts.append(escape_text(self.get_starttag_text() or f"<{tag}>"))
            return
        self.parts.append(self._start_tag(tag, attrs))

    def handle_startendtag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.parts.append(escape_text(self.get_starttag_text() or f"<{tag}/>"))
            return
        self.parts.append(self._start_tag(tag, attrs))
        if tag not in VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_endtag(self, tag):
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.parts.append(f"</{tag}>")
        elif tag not in ALLOWED_TAGS:
            self.parts.append(escape_text(f"</{tag}>"))

    def handle_data(self, data):
        self.parts.append(escape_text(data))

    def handle_comment(self, data):
        self.parts.append(escape_text(f"<!--{data}-->"))

    def handle_decl(self, decl):
        self.parts.append(escape_text(f"<!{decl}>"))

    def handle_pi(self, data):
        self.parts.append(escape_text(f"<?{data}>"))

    def unknown_decl(self, data):
        self.parts.append(escape_text(f"<![{data}]>"))


def rich_text(value: object) -> str:
    """Escape a description while preserving a small set of inline tags."""
    parser = InlineHTML()
    parser.feed(str(value))
    parser.close()
    return "".join(parser.parts)


def get_site(catalog: dict) -> dict:
    site = catalog.get("site")
    if not isinstance(site, dict):
        raise ValueError("catalog: 'site' must be an object")
    return site


def site_value(site: dict, dotted: str):
    value = site
    for key in dotted.split("."):
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"catalog: missing site.{dotted}")
        value = value[key]
    return value


def render_card(book: dict) -> str:
    accent = escape_attr(book["accent"])
    badge_style = book.get("badgeStyle")
    badge_attr = f' style="{escape_attr(badge_style)}"' if badge_style else ""

    lines = [
        f'      <article class="book" style="--accent: {accent}">',
        f'        <span class="lang" aria-hidden="true"{badge_attr}>'
        f'{escape_text(book["badge"])}</span>',
        f'        <h2>{escape_text(book["title"])}</h2>',
        f'        <p class="original">{escape_text(book["original"])}</p>',
        f'        <p class="desc">{rich_text(book["desc"])}</p>',
        '        <ul class="tags">',
    ]
    for tag in book.get("tags", []):
        lines.append(f"          <li>{escape_text(tag)}</li>")
    lines.append("        </ul>")
    lines.append('        <div class="actions">')
    for action in book.get("actions", []):
        classes = "btn primary" if action.get("primary") else "btn"
        lines.append(
            f'          <a class="{classes}" href="{escape_attr(action["href"])}">'
            f'{escape_text(action["label"])}</a>'
        )
    lines.append("        </div>")
    lines.append("      </article>")
    return "\n".join(lines)


def render_index(catalog: dict) -> str:
    site = get_site(catalog)
    books = catalog.get("books")
    if not isinstance(books, list):
        raise ValueError("catalog: 'books' must be an array")

    cards = "\n\n".join(render_card(book) for book in books if book.get("homepage", True))

    mapping = {
        "site.lang": site.get("lang", DEFAULT_LANG),
        "site.title": site_value(site, "title"),
        "site.description": site.get("description", ""),
        "site.header.title": site_value(site, "header.title"),
        "site.header.tagline": site.get("header", {}).get("tagline", ""),
        "site.footer.note": site.get("footer", {}).get("note", ""),
        "site.footer.repo_label": site.get("footer", {}).get("repo_label", "GitHub 仓库"),
        "site.footer.repo_url": site.get("footer", {}).get("repo_url", site.get("repo_url", DEFAULT_REPO_URL)),
        "books": cards,
    }

    template = TEMPLATE.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in mapping:
            raise ValueError(f"template: unknown placeholder {{{{ {key} }}}}")
        value = mapping[key]
        # Site fields are escaped for both text and attribute contexts; the
        # cards have already been rendered.
        return value if key == "books" else escape_attr(value)

    rendered = re.sub(r"\{\{([a-zA-Z0-9_.]+)\}\}", replace, template)
    if "{{" in rendered:
        raise ValueError("template: unexpanded placeholder remains")
    return rendered


def md_cell(value: object) -> str:
    """Make a value safe for one Markdown table cell."""
    text = " ".join(str(value).splitlines()).strip()
    return text.replace("|", "\\|")


def md_label(value: object) -> str:
    """Make a book title safe as a Markdown link label and table cell."""
    text = " ".join(str(value).splitlines()).strip()
    for char in ("\\", "[", "]", "|"):
        text = text.replace(char, "\\" + char)
    return text


def render_table(catalog: dict) -> str:
    site = get_site(catalog)
    home = str(site.get("home_url", DEFAULT_HOME_URL)).rstrip("/")
    repo = str(site.get("repo_url", DEFAULT_REPO_URL)).rstrip("/")

    lines = [
        "| 书名 | 说明 | 许可证 | 目录 |",
        "| --- | --- | --- | --- |",
    ]
    for book in catalog.get("books", []):
        book_id = str(book["id"])
        readme = book.get("readme") or {}
        summary = md_cell(readme.get("summary", ""))
        license_text = md_cell(readme.get("license", ""))
        lines.append(
            f"| [{md_label(book['title'])}]({home}/{book_id}/) "
            f"| {summary} "
            f"| {license_text} "
            f"| [`AwesomeTechBooks/{book_id}`]({repo}/{book_id}) |"
        )
    return "\n".join(lines)


def replace_marked(text: str, table: str, path: Path) -> str:
    start = text.find(CATALOG_START)
    if start < 0:
        raise ValueError(f"{path}: missing {CATALOG_START}")
    end = text.find(CATALOG_END, start + len(CATALOG_START))
    if end < 0:
        raise ValueError(f"{path}: missing {CATALOG_END}")
    return (
        text[: start + len(CATALOG_START)]
        + "\n"
        + table
        + "\n"
        + text[end:]
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def check_text(path: Path, expected: str) -> bool:
    try:
        actual = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: {path}: {exc}", file=sys.stderr)
        return False
    if actual == expected:
        print(f"ok: {path} is up to date")
        return True
    print(f"error: {path} is out of date; regenerate it", file=sys.stderr)
    diff = difflib.unified_diff(
        actual.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=str(path),
        tofile=f"{path} (generated)",
        n=2,
    )
    for i, line in enumerate(diff):
        if i >= 40:
            print("... diff truncated", file=sys.stderr)
            break
        print(line, end="", file=sys.stderr)
    return False


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the AwesomeTechBooks portal and book catalog tables.",
    )
    parser.add_argument("catalog", type=Path, help="path to catalog.json")
    parser.add_argument("--out", type=Path, help="output directory for index.html")
    parser.add_argument(
        "--readme", type=Path, help="README whose marked catalog table is rewritten"
    )
    parser.add_argument(
        "--profile", type=Path, help="organization profile README to rewrite"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare marked files only; never write; exit 1 if stale",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.check:
        if not (args.readme or args.profile):
            print("error: --check needs --readme and/or --profile", file=sys.stderr)
            return 2
    elif args.out is None:
        print("error: --out is required unless --check is used", file=sys.stderr)
        return 2

    try:
        data = json.loads(args.catalog.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("catalog: top level must be an object")
        table = render_table(data)
        index = None if args.check else render_index(data)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    targets = [p for p in (args.readme, args.profile) if p is not None]

    if args.check:
        ok = True
        for path in targets:
            try:
                expected = replace_marked(path.read_text(encoding="utf-8"), table, path)
            except (OSError, ValueError) as exc:
                print(f"error: {exc}", file=sys.stderr)
                ok = False
                continue
            if not check_text(path, expected):
                ok = False
        return 0 if ok else 1

    try:
        write_text(args.out / "index.html", index)
        print(f"wrote {args.out / 'index.html'}")
        for path in targets:
            expected = replace_marked(path.read_text(encoding="utf-8"), table, path)
            write_text(path, expected)
            print(f"wrote {path}")
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
