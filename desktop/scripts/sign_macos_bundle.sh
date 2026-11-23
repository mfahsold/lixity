#!/usr/bin/env bash
# Recursively sign every Mach-O binary/library inside Lixity.app (including the
# bundled python-build-standalone 3.12 runtime) and optionally notarize via notarytool.
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 /path/to/Lixity.app" >&2
    exit 2
fi

APP_BUNDLE="$1"
ENTITLEMENTS="$(cd "$(dirname "$0")/.." && pwd)/packaging/macos/Entitlements.plist"
IDENTITY="${APPLE_SIGNING_IDENTITY:-}"

if [ -z "$IDENTITY" ]; then
    echo "[ERR] APPLE_SIGNING_IDENTITY is not set." >&2
    exit 1
fi

if [ ! -d "$APP_BUNDLE" ]; then
    echo "[ERR] App bundle not found: $APP_BUNDLE" >&2
    exit 1
fi

echo "[1/3] Signing bundled dynamic libraries and Python executables..."
while IFS= read -r -d '' file; do
    codesign --force --options runtime --timestamp \
        --entitlements "$ENTITLEMENTS" \
        --sign "$IDENTITY" "$file"
done < <(find "$APP_BUNDLE/Contents/Resources/runtime" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -111 \) -print0)

echo "[2/3] Signing top-level Lixity.app bundle..."
codesign --force --options runtime --timestamp \
    --entitlements "$ENTITLEMENTS" \
    --sign "$IDENTITY" "$APP_BUNDLE"

echo "[3/3] Verifying signature integrity..."
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

if [ -n "${APPLE_NOTARY_PROFILE:-}" ]; then
    ZIP_TMP="$(mktemp -t lixity-notary).zip"
    trap 'rm -f "$ZIP_TMP"' EXIT
    ditto -c -k --keepParent "$APP_BUNDLE" "$ZIP_TMP"
    xcrun notarytool submit "$ZIP_TMP" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait
    xcrun stapler staple "$APP_BUNDLE"
    spctl --assess --type execute --verbose=4 "$APP_BUNDLE"
    echo "[OK] Signed, notarized, stapled and verified: $APP_BUNDLE"
else
    echo "[OK] Signed and verified (set APPLE_NOTARY_PROFILE to submit for notarization)."
fi
