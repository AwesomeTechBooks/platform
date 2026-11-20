#!/usr/bin/env bash
# Assemble the whole GitHub Pages site locally, in the same layout as online.
#
#   usage: build-site.sh WORKSPACE [OUT_DIR]
#
# WORKSPACE holds the book repositories and AwesomeTechBooks.github.io/.
# OUT_DIR defaults to WORKSPACE/_site (which may be replaced); any other
# existing directory is refused.  Books come from catalog.json.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    echo "usage: $0 WORKSPACE [OUT_DIR]" >&2
    exit 2
}

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage

if [ ! -d "$1" ]; then
    echo "error: workspace not found: $1" >&2
    exit 1
fi
WS="$(cd "$1" && pwd)"
CATALOG="$WS/AwesomeTechBooks.github.io/catalog.json"
if [ ! -f "$CATALOG" ]; then
    echo "error: catalog not found: $CATALOG" >&2
    exit 1
fi

if [ "$#" -eq 2 ]; then
    case "$2" in
        /*) OUT="$2" ;;
        *) OUT="$PWD/$2" ;;
    esac
    OUT="$(python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$OUT")"
else
    OUT="$WS/_site"
fi

# The default output directory belongs to this script; anything else must be
# new.  This is the same rule as the old single-repository build-site.sh.
if [ "$OUT" = "$WS/_site" ]; then
    rm -rf "$OUT"
elif [ -e "$OUT" ]; then
    echo "$OUT already exists; remove it or pick another directory" >&2
    exit 1
fi
mkdir -p "$OUT"

read_catalog() {
    python3 - "$CATALOG" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
except (OSError, ValueError) as exc:
    raise SystemExit(f"error: cannot read {path}: {exc}")

books = data.get("books") if isinstance(data, dict) else None
if not isinstance(books, list):
    raise SystemExit(f"error: {path}: expected a top-level 'books' list")

seen = set()
for index, book in enumerate(books, 1):
    if not isinstance(book, dict):
        raise SystemExit(f"error: {path}: books[{index}] is not an object")
    name = book.get("id")
    if not isinstance(name, str) or not name:
        raise SystemExit(f"error: {path}: books[{index}] has no id")
    if name in (".", "..") or "/" in name or "\\" in name:
        raise SystemExit(f"error: {path}: invalid book id: {name!r}")
    if name in seen:
        raise SystemExit(f"error: {path}: duplicate book id: {name}")
    seen.add(name)
    prebuilt = book.get("prebuilt") or ""
    if not isinstance(prebuilt, str):
        raise SystemExit(f"error: {path}: {name}: prebuilt must be a string")
    print(f"{name}\t{prebuilt}")
PY
}

if ! catalog_lines="$(read_catalog)"; then
    exit 1
fi

while IFS=$'\t' read -r book_id prebuilt; do
    [ -n "$book_id" ] || continue
    build_args=("$WS/$book_id" "$OUT/$book_id")
    if [ -n "$prebuilt" ]; then
        build_args+=(--prebuilt "$prebuilt")
    fi
    bash "$PLATFORM/tools/build-book.sh" "${build_args[@]}"
done <<< "$catalog_lines"

PORTAL="$PLATFORM/tools/build-portal.py"
if [ -f "$PORTAL" ]; then
    python3 "$PORTAL" "$CATALOG" --out "$OUT"
else
    echo "warning: $PORTAL not found; skipping the portal page" >&2
fi

printf '==> site written to %s\n' "$OUT"
