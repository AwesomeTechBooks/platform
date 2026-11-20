#!/usr/bin/env python3
"""Inject the shared reader assets into every page of one built book.

Usage: python3 tools/inject-reader.py <book-output-dir>

OUT_DIR is the root of a single book's build output.  Only *.html files
containing id="mdbook-content" are touched, and print.html and 404.html are
skipped, so redirect stubs, toc.html and sample HTML shipped with a book are
left alone.  The _atb/ directory is not scanned.

The script is idempotent: a page that already references the reader assets is
left unchanged, so running it twice is harmless.
"""

import os
import re
import sys
from pathlib import Path

MARKER = 'id="mdbook-content"'
HEAD_END = re.compile(r"[ \t]*</head>")
SKIP_NAMES = {"print.html", "404.html"}
SNIPPET = (
    '        <link rel="stylesheet" href="{rel}_atb/reader/reader.css">\n'
    '        <script src="{rel}_atb/reader/reader.js"></script>\n'
)


def already_injected(text: str) -> bool:
    """Whether this page already carries the reader tags."""
    return (
        "_atb/reader/reader.css" in text
        and "_atb/reader/reader.js" in text
    )


def inject(page: Path, root: Path) -> str:
    """Return "skip", "already" or "injected" for one page."""
    if page.name in SKIP_NAMES:
        return "skip"

    text = page.read_bytes().decode("utf-8")
    if MARKER not in text:
        return "skip"
    if already_injected(text):
        return "already"

    # Match the leading indent too, so the snippet gets head-child indent.
    head_end = HEAD_END.search(text)
    if head_end is None:
        raise ValueError(f"{page}: has {MARKER} but no </head>")

    depth = len(page.parent.relative_to(root).parts)
    rel = "../" * depth
    at = head_end.start()
    text = text[:at] + SNIPPET.format(rel=rel) + text[at:]
    page.write_bytes(text.encode("utf-8"))
    return "injected"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <book-output-dir>", file=sys.stderr)
        return 2

    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {argv[1]}", file=sys.stderr)
        return 2

    injected = 0
    already = 0
    found = 0
    failed = False

    for dirpath, dirnames, filenames in os.walk(root):
        # The shared assets live here; they are not book pages.
        dirnames[:] = sorted(d for d in dirnames if d != "_atb")
        for name in sorted(filenames):
            if not name.endswith(".html"):
                continue
            page = Path(dirpath) / name
            try:
                status = inject(page, root)
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                print(f"error: {exc}", file=sys.stderr)
                failed = True
                continue
            if status == "injected":
                found += 1
                injected += 1
            elif status == "already":
                found += 1
                already += 1

    if failed:
        return 1
    if found == 0:
        print(
            f"error: no reader pages found under {root}; is this the output "
            f"directory of one book?",
            file=sys.stderr,
        )
        return 1

    message = f"==> injected into {injected} page(s)"
    if already:
        message += f"; {already} page(s) already had the reader"
    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
