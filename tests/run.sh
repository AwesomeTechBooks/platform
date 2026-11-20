#!/usr/bin/env bash
# Automated checks for the platform build tools.  Everything is written under
# a temporary directory; the real book repositories are never modified.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM="$(cd "$SCRIPT_DIR/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/atb-tests.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0

ok() {
    PASS=$((PASS + 1))
    printf 'PASS  %s\n' "$1"
}

bad() {
    FAIL=$((FAIL + 1))
    printf 'FAIL  %s\n' "$1"
}

tree_hash() {
    find "$1" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum \
        | cut -d' ' -f1
}

make_book() {
    local dir="$1"
    mkdir -p "$dir/src/sub" "$dir/theme"
    cp "$PLATFORM/components/base/custom.css" "$dir/theme/custom.css"
    cat > "$dir/book.toml" <<'EOF'
[book]
title = "Test Book"
language = "zh-CN"
src = "src"

[output.html]
additional-css = ["theme/custom.css"]

[output.html.search]
use-boolean-and = true
EOF
    cat > "$dir/src/SUMMARY.md" <<'EOF'
# Summary

- [Home](index.md)
- [Sub](sub/page.md)
EOF
    cat > "$dir/src/index.md" <<'EOF'
# Home
EOF
    cat > "$dir/src/sub/page.md" <<'EOF'
# Sub page
EOF
    printf 'test licence\n' > "$dir/LICENSE"
}

# ---------------------------------------------------------------- build-book
BOOK="$TMP/book"
make_book "$BOOK"
OUT="$TMP/out"

if build_output="$(bash "$PLATFORM/tools/build-book.sh" "$BOOK" "$OUT" 2>&1)"; then
    ok "build-book.sh builds a small book"
else
    bad "build-book.sh builds a small book"
    printf '%s\n' "$build_output"
fi

if [ -f "$OUT/_atb/reader/reader.js" ] && [ -f "$OUT/_atb/reader/reader.css" ]; then
    ok "reader assets are copied to _atb/reader/"
else
    bad "reader assets are copied to _atb/reader/"
fi

if grep -qF 'href="_atb/reader/reader.css"' "$OUT/index.html"; then
    ok "root page uses a root-relative reader path"
else
    bad "root page uses a root-relative reader path"
fi

if grep -qF 'href="../_atb/reader/reader.css"' "$OUT/sub/page.html"; then
    ok "subdirectory page uses ../_atb/reader/reader.css"
else
    bad "subdirectory page uses ../_atb/reader/reader.css"
fi

expected_pages="$(
    grep -rlF --include='*.html' 'id="mdbook-content"' "$OUT" \
        | grep -v '/_atb/' \
        | grep -vE '/(print|404)\.html$' \
        | wc -l
)"
injected_pages="$(
    grep -rlF --include='*.html' '_atb/reader/reader.css' "$OUT" \
        | grep -v '/_atb/' \
        | wc -l
)"
if [ "$expected_pages" -eq "$injected_pages" ] && [ "$expected_pages" -gt 0 ]; then
    ok "every reader page got exactly one injection ($injected_pages pages)"
else
    bad "every reader page got exactly one injection (expected $expected_pages, got $injected_pages)"
fi

if printf '%s\n' "$build_output" | grep -qE '(^|[^A-Za-z])(WARN|ERROR)([^A-Za-z]|$)'; then
    bad "small book build has no mdBook WARN/ERROR"
else
    ok "small book build has no mdBook WARN/ERROR"
fi

before_hash="$(tree_hash "$OUT")"
if second_output="$(python3 "$PLATFORM/tools/inject-reader.py" "$OUT" 2>&1)"; then
    ok "inject-reader.py succeeds on an already-injected directory"
else
    bad "inject-reader.py succeeds on an already-injected directory"
    printf '%s\n' "$second_output"
fi
after_hash="$(tree_hash "$OUT")"
if [ "$before_hash" = "$after_hash" ]; then
    ok "inject-reader.py is idempotent (second run changes nothing)"
else
    bad "inject-reader.py is idempotent (second run changes nothing)"
fi

NONEMPTY="$TMP/nonempty"
mkdir -p "$NONEMPTY"
printf 'keep\n' > "$NONEMPTY/keep"
if bash "$PLATFORM/tools/build-book.sh" "$BOOK" "$NONEMPTY" >/dev/null 2>&1; then
    bad "build-book.sh refuses a non-empty OUT_DIR"
else
    ok "build-book.sh refuses a non-empty OUT_DIR"
fi
if [ -f "$NONEMPTY/keep" ]; then
    ok "build-book.sh leaves a refused non-empty OUT_DIR untouched"
else
    bad "build-book.sh leaves a refused non-empty OUT_DIR untouched"
fi

EMPTYOUT="$TMP/emptyout"
mkdir -p "$EMPTYOUT"
if bash "$PLATFORM/tools/build-book.sh" "$BOOK" "$EMPTYOUT" >/dev/null 2>&1; then
    ok "build-book.sh accepts an existing empty OUT_DIR"
else
    bad "build-book.sh accepts an existing empty OUT_DIR"
fi

# ----------------------------------------------------------- check-components
if quiet_output="$(python3 "$PLATFORM/tools/check-components.py" "$BOOK" --quiet)"; then
    if [ -z "$quiet_output" ]; then
        ok "check-components --quiet is silent when everything matches"
    else
        bad "check-components --quiet is silent when everything matches"
    fi
else
    bad "check-components --quiet is silent when everything matches"
fi

if normal_output="$(python3 "$PLATFORM/tools/check-components.py" "$BOOK")"; then
    if printf '%s\n' "$normal_output" | grep -qF '与 platform 的 base 组件一致'; then
        ok "check-components reports matching files without --quiet"
    else
        bad "check-components reports matching files without --quiet"
    fi
else
    bad "check-components reports matching files without --quiet"
fi

CHECK="$TMP/check"
mkdir -p "$CHECK/theme"
cp "$PLATFORM/components/fig/fig.js" "$CHECK/theme/fig.js"
printf '\n// older copy\n' >> "$CHECK/theme/fig.js"
cp "$PLATFORM/components/fig/fig.css" "$CHECK/theme/fig.css"
cp "$PLATFORM/components/fig/fig_preprocess.py" "$CHECK/theme/fig_preprocess.py"

if diff_output="$(python3 "$PLATFORM/tools/check-components.py" "$CHECK" 2>&1)"; then
    bad "check-components exits 1 for a different component file"
else
    ok "check-components exits 1 for a different component file"
fi
if printf '%s\n' "$diff_output" | grep -qF 'theme/fig.js 和 platform 的 fig 组件不同'; then
    ok "check-components names the different fig.js"
else
    bad "check-components names the different fig.js"
fi

if sync_output="$(python3 "$PLATFORM/tools/check-components.py" "$CHECK" --sync 2>&1)"; then
    ok "check-components --sync updates a different file"
else
    bad "check-components --sync updates a different file"
fi
if cmp -s "$CHECK/theme/fig.js" "$PLATFORM/components/fig/fig.js"; then
    ok "check-components --sync copied the standard fig.js"
else
    bad "check-components --sync copied the standard fig.js"
fi

MISSING="$TMP/missing"
mkdir -p "$MISSING/theme"
cp "$PLATFORM/components/fig/fig.js" "$MISSING/theme/fig.js"
if missing_output="$(python3 "$PLATFORM/tools/check-components.py" "$MISSING" 2>&1)"; then
    bad "check-components exits 1 when a used component is incomplete"
else
    ok "check-components exits 1 when a used component is incomplete"
fi
if printf '%s\n' "$missing_output" | grep -qF 'theme/fig.css 缺失'; then
    ok "check-components reports the missing fig.css"
else
    bad "check-components reports the missing fig.css"
fi
if printf '%s\n' "$missing_output" | grep -qF 'theme/fig_preprocess.py 缺失'; then
    ok "check-components reports the missing fig_preprocess.py"
else
    bad "check-components reports the missing fig_preprocess.py"
fi

if python3 "$PLATFORM/tools/check-components.py" "$MISSING" --sync >/dev/null 2>&1; then
    ok "check-components --sync fills in missing component files"
else
    bad "check-components --sync fills in missing component files"
fi
if [ -f "$MISSING/theme/fig.css" ] \
    && cmp -s "$MISSING/theme/fig.css" "$PLATFORM/components/fig/fig.css" \
    && cmp -s "$MISSING/theme/fig_preprocess.py" "$PLATFORM/components/fig/fig_preprocess.py"; then
    ok "check-components --sync copied the missing standard files"
else
    bad "check-components --sync copied the missing standard files"
fi

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
