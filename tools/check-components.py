#!/usr/bin/env python3
"""Compare a book's theme/ copies with the platform's standard components.

Usage: python3 tools/check-components.py BOOK_DIR [--sync] [--quiet]

A book uses a component when its theme/ contains at least one file with the
same relative path as a file in platform/components/<name>/.  Every standard
file of a used component is then checked.  A missing sibling file is reported
too, because it usually means the copy is out of date.

Exit status: 0 when everything matches (or --sync repaired it), 1 when at
least one file differs or is missing, 2 for a usage error.
"""

import shutil
import sys
from pathlib import Path


def component_files(platform: Path) -> dict[str, tuple[Path, list[tuple[str, Path]]]]:
    """Map component name -> (directory, [(relative path, source file)])."""
    root = platform / "components"
    if not root.is_dir():
        raise SystemExit(f"error: components directory not found: {root}")

    components: dict[str, tuple[Path, list[tuple[str, Path]]]] = {}
    for comp_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        files = []
        for src in sorted(p for p in comp_dir.rglob("*") if p.is_file()):
            files.append((src.relative_to(comp_dir).as_posix(), src))
        if files:
            components[comp_dir.name] = (comp_dir, files)
    return components


def usage(argv: list[str]) -> int:
    print(
        f"usage: {argv[0]} BOOK_DIR [--sync] [--quiet]",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str]) -> int:
    book = None
    sync = False
    quiet = False

    for arg in argv[1:]:
        if arg == "--sync":
            sync = True
        elif arg == "--quiet":
            quiet = True
        elif arg in ("-h", "--help"):
            print(f"usage: {argv[0]} BOOK_DIR [--sync] [--quiet]")
            return 0
        elif arg.startswith("-"):
            return usage(argv)
        elif book is None:
            book = arg
        else:
            return usage(argv)

    if book is None:
        return usage(argv)

    book_dir = Path(book).resolve()
    if not book_dir.is_dir():
        print(f"error: not a directory: {book}", file=sys.stderr)
        return 2

    platform = Path(__file__).resolve().parent.parent
    components = component_files(platform)
    theme = book_dir / "theme"
    theme_files = set()
    if theme.is_dir():
        theme_files = {
            p.relative_to(theme).as_posix()
            for p in theme.rglob("*")
            if p.is_file()
        }

    problems = 0
    copied = 0
    failed = False

    for name, (_comp_dir, files) in components.items():
        paths = {rel for rel, _src in files}
        if not paths & theme_files:
            # The book does not use this component at all.
            continue

        for rel, src in files:
            dest = theme / rel
            shown = f"theme/{rel}"
            if dest.is_file():
                if dest.read_bytes() == src.read_bytes():
                    if not quiet:
                        print(f"{shown} 与 platform 的 {name} 组件一致")
                    continue

                problems += 1
                if not sync:
                    print(
                        f"{shown} 和 platform 的 {name} 组件不同"
                        f"（--sync 可更新）"
                    )
                    continue
                try:
                    shutil.copy2(src, dest)
                except OSError as exc:
                    print(f"error: cannot update {shown}: {exc}", file=sys.stderr)
                    failed = True
                    continue
                copied += 1
                print(f"已更新 {shown}（来自 platform/components/{name}/{rel}）")
                continue

            problems += 1
            if not sync:
                print(
                    f"{shown} 缺失（platform 的 {name} 组件有，--sync 可补）"
                )
                continue
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            except OSError as exc:
                print(f"error: cannot create {shown}: {exc}", file=sys.stderr)
                failed = True
                continue
            copied += 1
            print(f"已补齐 {shown}（来自 platform/components/{name}/{rel}）")

    if failed:
        return 1
    if problems and not sync:
        return 1
    if sync and copied and not quiet:
        print(f"==> copied {copied} file(s) into {book_dir / 'theme'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
