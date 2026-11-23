#!/usr/bin/env bash
# Recursively sign every Mach-O binary/library inside Lixity.app (including the
# bundled python-build-standalone 3.12 runtime) and optionally notarize via notarytool.
# Pass --adhoc for unsigned local/CI verification builds without an Apple Developer ID.
set -euo pipefail

ADHOC=0
if [ "${1:-}" = "--adhoc" ]; then
    ADHOC=1
    shift
fi

if [ $# -lt 1 ]; then
    echo "Usage: $0 [--adhoc] /path/to/Lixity.app" >&2
    exit 2
fi

APP_BUNDLE="$1"
ENTITLEMENTS="$(cd "$(dirname "$0")/.." && pwd)/packaging/macos/Entitlements.plist"

if [ ! -d "$APP_BUNDLE" ]; then
    echo "[ERR] App bundle not found: $APP_BUNDLE" >&2
    exit 1
fi

if [ "$ADHOC" -eq 1 ]; then
    IDENTITY="-"
    SIGN_FLAGS=(--force --entitlements "$ENTITLEMENTS" --sign "-")
    echo "[INFO] Running ad-hoc macOS bundle signing (unsigned verification mode)."
else
    IDENTITY="${APPLE_SIGNING_IDENTITY:-}"
    if [ -z "$IDENTITY" ]; then
        echo "[ERR] APPLE_SIGNING_IDENTITY is not set (or pass --adhoc for local verification)." >&2
        exit 1
    fi
    SIGN_FLAGS=(--force --options runtime --timestamp --entitlements "$ENTITLEMENTS" --sign "$IDENTITY")
fi

echo "[1/3] Signing bundled Mach-O libraries and Python executables..."
if [ -d "$APP_BUNDLE/Contents/Resources/runtime" ]; then
    while IFS= read -r -d '' file; do
        if file -b "$file" | grep -q "Mach-O"; then
            codesign "${SIGN_FLAGS[@]}" "$file"
        fi
    done < <(find "$APP_BUNDLE/Contents/Resources/runtime" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -111 \) -print0)
fi

echo "[2/3] Signing top-level Lixity.app bundle..."
codesign "${SIGN_FLAGS[@]}" "$APP_BUNDLE"

echo "[3/3] Verifying signature integrity..."
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

if [ "$ADHOC" -eq 0 ] && [ -n "${APPLE_NOTARY_PROFILE:-}" ]; then
    ZIP_TMP="$(mktemp -t lixity-notary).zip"
    trap 'rm -f "$ZIP_TMP"' EXIT
    ditto -c -k --keepParent "$APP_BUNDLE" "$ZIP_TMP"
    xcrun notarytool submit "$ZIP_TMP" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait
    xcrun stapler staple "$APP_BUNDLE"
    spctl --assess --type execute --verbose=4 "$APP_BUNDLE"
    echo "[OK] Signed, notarized, stapled and verified: $APP_BUNDLE"
else
    echo "[OK] Signed and verified ($IDENTITY): $APP_BUNDLE"
fi
