#!/usr/bin/env bash
# Package an ALREADY SIGNED Lixity.app bundle into a compressed UDZO macOS .dmg
# (with Applications symlink), optionally sign/notarize the .dmg, and verify the
# embedded Lixity.app signature by mounting the resulting .dmg read-only.
set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 /path/to/Lixity.app /path/to/output.dmg" >&2
    exit 2
fi

APP_BUNDLE="$1"
OUT_DMG="$2"

if [ ! -d "$APP_BUNDLE" ]; then
    echo "[ERR] App bundle not found: $APP_BUNDLE" >&2
    exit 1
fi

echo "[1/4] Verifying signed Lixity.app before DMG packaging..."
codesign --verify --deep --strict "$APP_BUNDLE"

STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/lixity-dmg-stage.XXXXXX")"
VERIFY_MNT="$(mktemp -d "${TMPDIR:-/tmp}/lixity-dmg-verify.XXXXXX")"
MOUNTED=0
cleanup() {
    if [ "$MOUNTED" -eq 1 ]; then
        hdiutil detach "$VERIFY_MNT" -force >/dev/null 2>&1 || true
    fi
    rm -rf "$STAGE_DIR" "$VERIFY_MNT"
}
trap cleanup EXIT

echo "[2/4] Staging signed Lixity.app with ditto and /Applications symlink..."
ditto "$APP_BUNDLE" "$STAGE_DIR/Lixity.app"
ln -s /Applications "$STAGE_DIR/Applications"

mkdir -p "$(dirname "$OUT_DMG")"
rm -f "$OUT_DMG"

echo "[3/4] Creating compressed UDZO DMG at $OUT_DMG..."
hdiutil create \
    -volname "Lixity" \
    -srcfolder "$STAGE_DIR" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "$OUT_DMG"

if [ -n "${APPLE_SIGNING_IDENTITY:-}" ]; then
    echo "[INFO] Signing DMG with Developer ID identity..."
    codesign --force --timestamp --sign "$APPLE_SIGNING_IDENTITY" "$OUT_DMG"
    if [ -n "${APPLE_NOTARY_PROFILE:-}" ]; then
        echo "[INFO] Submitting DMG for Apple notarization..."
        xcrun notarytool submit "$OUT_DMG" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait
        xcrun stapler staple "$OUT_DMG"
    fi
fi

echo "[4/4] Mounting DMG read-only to verify embedded Lixity.app signature..."
hdiutil attach -nobrowse -readonly -mountpoint "$VERIFY_MNT" "$OUT_DMG" >/dev/null
MOUNTED=1
codesign --verify --deep --strict --verbose=2 "$VERIFY_MNT/Lixity.app"
hdiutil detach "$VERIFY_MNT" >/dev/null
MOUNTED=0

echo "[OK] Packaged and verified macOS DMG: $OUT_DMG"
