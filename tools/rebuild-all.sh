#!/usr/bin/env bash
# Trigger a fresh Pages build for every book in catalog.json, then the portal.
#
#   usage: rebuild-all.sh [--dry-run]
#
# The catalog defaults to the sibling AwesomeTechBooks.github.io repository;
# set CATALOG=/path/to/catalog.json to override it.  Requires gh, except in
# --dry-run mode, which only prints the commands.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CATALOG="${CATALOG:-$SCRIPT_DIR/../../AwesomeTechBooks.github.io/catalog.json}"

DRY_RUN=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            echo "usage: $0 [--dry-run]"
            exit 0
            ;;
        *)
            echo "usage: $0 [--dry-run]" >&2
            exit 2
            ;;
    esac
    shift
done

if [ ! -f "$CATALOG" ]; then
    echo "error: catalog not found: $CATALOG" >&2
    exit 1
fi

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
    print(name)
PY
}

if ! book_ids="$(read_catalog)"; then
    exit 1
fi

trigger() {
    local repo="$1"
    if $DRY_RUN; then
        printf 'gh workflow run pages.yml -R %s\n' "$repo"
    else
        gh workflow run pages.yml -R "$repo"
    fi
}

while IFS= read -r book_id; do
    [ -n "$book_id" ] || continue
    trigger "AwesomeTechBooks/$book_id"
done <<< "$book_ids"

trigger "AwesomeTechBooks/AwesomeTechBooks.github.io"
