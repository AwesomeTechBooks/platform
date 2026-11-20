#!/usr/bin/env bash
# Create a new book repository from platform/template.
#
#   usage: new-book.sh NAME TITLE [DEST_PARENT]
#
# DEST_PARENT defaults to the directory that contains platform/.  The new
# repository is initialised with git init -b main but nothing is committed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE="$PLATFORM/template"

usage() {
    echo "usage: $0 NAME TITLE [DEST_PARENT]" >&2
    exit 2
}

[ "$#" -ge 2 ] && [ "$#" -le 3 ] || usage
NAME="$1"
TITLE="$2"

case "$NAME" in
    ""|"."|".."|*/*|*\\*)
        echo "error: invalid repository name: $NAME" >&2
        exit 1
        ;;
esac

if [ "$#" -eq 3 ]; then
    DEST_PARENT="$3"
else
    DEST_PARENT="$PLATFORM/.."
fi
mkdir -p "$DEST_PARENT"
DEST_PARENT="$(cd "$DEST_PARENT" && pwd)"
DEST="$DEST_PARENT/$NAME"

if [ -e "$DEST" ]; then
    echo "error: $DEST already exists" >&2
    exit 1
fi
if [ ! -d "$TEMPLATE" ]; then
    echo "error: template not found: $TEMPLATE" >&2
    exit 1
fi

cp -a "$TEMPLATE" "$DEST"

python3 - "$DEST" "$NAME" "$TITLE" <<'PY'
import sys
from pathlib import Path

dest = Path(sys.argv[1])
name = sys.argv[2].encode("utf-8")
title = sys.argv[3].encode("utf-8")

for path in sorted(dest.rglob("*")):
    if not path.is_file():
        continue
    data = path.read_bytes()
    replaced = data.replace(b"{{name}}", name).replace(b"{{title}}", title)
    if replaced != data:
        path.write_bytes(replaced)
PY

git init -b main "$DEST"
printf '==> created %s\n' "$DEST"
