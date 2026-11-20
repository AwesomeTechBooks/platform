#!/usr/bin/env bash
# Build one book with the shared platform, then add the reader and licences.
#
#   usage: build-book.sh BOOK_DIR OUT_DIR [--prebuilt SUBDIR]
#
# BOOK_DIR is the book repository (or its checkout); OUT_DIR is the directory
# GitHub Pages will publish.  With --prebuilt, SUBDIR's contents are copied
# as-is instead of running mdBook.  OUT_DIR must not exist or must be empty.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    echo "usage: $0 BOOK_DIR OUT_DIR [--prebuilt SUBDIR]" >&2
    exit 2
}

[ "$#" -ge 2 ] || usage
BOOK_ARG="$1"
OUT_ARG="$2"
shift 2

PREBUILT=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --prebuilt)
            [ "$#" -ge 2 ] || usage
            [ -z "$PREBUILT" ] || usage
            PREBUILT="$2"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

if [ ! -d "$BOOK_ARG" ]; then
    echo "error: book directory not found: $BOOK_ARG" >&2
    exit 1
fi
BOOK="$(cd "$BOOK_ARG" && pwd)"

# Resolve OUT_DIR against the current directory, not the book or platform.
case "$OUT_ARG" in
    /*) OUT="$OUT_ARG" ;;
    *) OUT="$PWD/$OUT_ARG" ;;
esac

if [ -e "$OUT" ]; then
    if [ ! -d "$OUT" ]; then
        echo "error: output path is not a directory: $OUT" >&2
        exit 1
    fi
    if [ -n "$(ls -A "$OUT")" ]; then
        echo "error: output directory is not empty: $OUT" >&2
        exit 1
    fi
else
    mkdir -p "$OUT"
fi
OUT="$(cd "$OUT" && pwd)"

if [ -n "$PREBUILT" ]; then
    SRC="$BOOK/$PREBUILT"
    if [ ! -d "$SRC" ]; then
        echo "error: prebuilt directory not found: $SRC" >&2
        exit 1
    fi
    cp -a "$SRC/." "$OUT/"
else
    mdbook build "$BOOK" -d "$OUT"
fi

# The licence texts travel with the book, as its copyright page promises.
shopt -s nullglob
licences=("$BOOK"/LICENSE*)
if [ "${#licences[@]}" -eq 0 ]; then
    echo "error: no LICENSE* file in $BOOK" >&2
    exit 1
fi
for licence in "${licences[@]}"; do
    cp -a "$licence" "$OUT/"
done

# Shared reader assets: copy them in and inject them into every content page.
rm -rf "$OUT/_atb/reader"
mkdir -p "$OUT/_atb/reader"
cp -a "$PLATFORM/reader/." "$OUT/_atb/reader/"
python3 "$PLATFORM/tools/inject-reader.py" "$OUT"

# Component drift is a warning only; it must never fail the build.  A prebuilt
# book has no theme/ and is skipped.
if [ -d "$BOOK/theme" ]; then
    check_output="$(python3 "$PLATFORM/tools/check-components.py" "$BOOK" --quiet 2>&1 || true)"
    if [ -n "$check_output" ]; then
        while IFS= read -r line; do
            [ -n "$line" ] || continue
            if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
                # annotation paths are relative to the book repository root
                case "$line" in
                    theme/*) printf '::warning file=%s::%s\n' "${line%% *}" "$line" ;;
                    *) printf '::warning::%s\n' "$line" ;;
                esac
            else
                printf 'warning: %s\n' "$line" >&2
            fi
        done <<< "$check_output"
    fi
fi

file_count="$(find "$OUT" -type f | wc -l | tr -d ' ')"
size="$(du -sh "$OUT" | cut -f1)"
printf '==> %s (%s files, %s)\n' "$OUT" "$file_count" "$size"
