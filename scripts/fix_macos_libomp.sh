#!/usr/bin/env bash
# XGBoost and LightGBM's macOS wheels link against @rpath/libomp.dylib and
# expect it at /opt/homebrew/opt/libomp/lib/libomp.dylib — i.e. they assume
# Homebrew. On a machine without Homebrew (like this one), pip install
# succeeds but `import xgboost`/`import lightgbm` fails at dlopen time.
#
# This machine already has libomp via its Anaconda install
# (/opt/anaconda3/lib/libomp.dylib), so instead of installing Homebrew just
# for one shared library, this repoints each package's compiled extension
# at that existing libomp directly with install_name_tool — no global
# DYLD_LIBRARY_PATH (which breaks numpy's Accelerate-framework linking),
# no Homebrew, no sudo.
#
# Re-run this after any `pip install --upgrade xgboost` / `lightgbm`,
# since reinstalling restores the original (broken-on-this-machine) path.
#
# Usage: scripts/fix_macos_libomp.sh [path-to-libomp.dylib]

set -euo pipefail

LIBOMP_PATH="${1:-/opt/anaconda3/lib/libomp.dylib}"
VENV_SITE_PACKAGES="$(dirname "$0")/../.venv/lib/python3.13/site-packages"

if [ ! -f "$LIBOMP_PATH" ]; then
    echo "libomp.dylib not found at $LIBOMP_PATH" >&2
    echo "Pass its location as an argument, e.g. via 'brew --prefix libomp' if you install Homebrew later." >&2
    exit 1
fi

patch_lib() {
    local lib_path="$1"
    if [ ! -f "$lib_path" ]; then
        echo "skip (not installed): $lib_path"
        return
    fi
    if otool -L "$lib_path" | grep -q "@rpath/libomp.dylib"; then
        install_name_tool -change "@rpath/libomp.dylib" "$LIBOMP_PATH" "$lib_path"
        codesign --force --sign - "$lib_path"
        echo "patched: $lib_path -> $LIBOMP_PATH"
    else
        echo "already patched or not linked against libomp: $lib_path"
    fi
}

patch_lib "$VENV_SITE_PACKAGES/xgboost/lib/libxgboost.dylib"
patch_lib "$VENV_SITE_PACKAGES/lightgbm/lib/lib_lightgbm.dylib"
